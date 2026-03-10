"""
Unit Testler: RLAjan — Tabular Q-Learning Optimizer

Kapsam:
  - OptimizerBase sözleşme uyumu
  - Durum ayrıştırma tutarlılığı (30 durum)
  - Eylem kodlama / çözme dönüşümleri (16 eylem)
  - ACİL_DURDUR güvenlik kuralı
  - KuralMotoru warm-start
  - Online öğrenme (Q-güncelleme)
  - Ödül hesaplama mantığı
  - geri_bildirim() öğrenme döngüsü
  - Kalıcılık (kaydet/yukle)
  - KontrolMotoru DI + öğrenme döngüsü entegrasyonu
"""
import os
import tempfile
import pytest

from sera_ai.domain.models import BitkilProfili, SensorOkuma
from sera_ai.domain.state_machine import Durum
from sera_ai.intelligence.base import HedefDeger, OptimizerBase
from sera_ai.intelligence.kural_motoru import KuralMotoru
from sera_ai.intelligence.rl_ajan import (
    RLAjan, DURUM_SAYISI, EYLEM_SAYISI,
    _hedef_to_eylem, _eylem_to_hedef,
)


# ── Ortak yardımcılar ─────────────────────────────────────────

@pytest.fixture
def profil() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )


@pytest.fixture
def ajan(profil) -> RLAjan:
    return RLAjan(profil, epsilon=0.0)   # epsilon=0: saf sömürü (deterministik test)


def _sensor(profil, T=None, H=None, toprak_nem=500):
    return SensorOkuma(
        sera_id="test",
        T=T if T is not None else profil.opt_T,
        H=H if H is not None else 72.0,
        co2=950, isik=450, toprak_nem=toprak_nem, ph=6.5, ec=1.8,
    )


# ── OptimizerBase sözleşmesi ──────────────────────────────────

def test_rl_ajan_optimizer_base_alt_sinifi():
    assert issubclass(RLAjan, OptimizerBase)


def test_rl_ajan_hedef_hesapla_hedef_deger_donereder(ajan, profil):
    s = _sensor(profil)
    sonuc = ajan.hedef_hesapla(s, Durum.NORMAL)
    assert isinstance(sonuc, HedefDeger)


# ── ACİL_DURDUR güvenlik kuralı ───────────────────────────────

def test_acil_durdur_hepsi_kapali(ajan, profil):
    """ACİL_DURDUR → tüm aktüatörler kapalı (yüksek sıcaklık olsa bile)."""
    s = _sensor(profil, T=profil.opt_T + 15)
    h = ajan.hedef_hesapla(s, Durum.ACIL_DURDUR)
    assert h == HedefDeger()


# ── Eylem kodlama / çözme ─────────────────────────────────────

def test_hedef_to_eylem_hepsi_kapali():
    assert _hedef_to_eylem(HedefDeger()) == 0


def test_hedef_to_eylem_sulama():
    assert _hedef_to_eylem(HedefDeger(sulama=True)) == 1


def test_hedef_to_eylem_isitici():
    assert _hedef_to_eylem(HedefDeger(isitici=True)) == 2


def test_hedef_to_eylem_sogutma():
    assert _hedef_to_eylem(HedefDeger(sogutma=True)) == 4


def test_hedef_to_eylem_fan():
    assert _hedef_to_eylem(HedefDeger(fan=True)) == 8


def test_hedef_to_eylem_sogutma_fan():
    assert _hedef_to_eylem(HedefDeger(sogutma=True, fan=True)) == 12


def test_eylem_to_hedef_geri_donusum():
    """Tüm 16 eylem → HedefDeger → tekrar eylem tutarlı olmalı."""
    for i in range(EYLEM_SAYISI):
        h = _eylem_to_hedef(i)
        assert _hedef_to_eylem(h) == i


def test_eylem_hedef_donusum_tam_tur():
    """HedefDeger → eylem → HedefDeger tam tur tutarlı."""
    for sulama in (True, False):
        for isitici in (True, False):
            for sogutma in (True, False):
                for fan in (True, False):
                    h = HedefDeger(sulama=sulama, isitici=isitici,
                                   sogutma=sogutma, fan=fan)
                    assert _eylem_to_hedef(_hedef_to_eylem(h)) == h


# ── Durum ayrıştırma ──────────────────────────────────────────

def test_durum_sayisi_2430(ajan, profil):
    """Tüm sensör kombinasyonları 0–2429 arasında indeks üretmeli."""
    for T_offset in (-6, -3, 0, 3, 6):
        for H_ofset in (-15, 0, 15):
            for toprak in (200, 600):
                s = _sensor(profil,
                            T=profil.opt_T + T_offset,
                            H=72.0 + H_ofset,
                            toprak_nem=toprak)
                idx = ajan._sensor_to_durum_idx(s)
                assert 0 <= idx < DURUM_SAYISI, f"idx={idx} T_offset={T_offset}"


def test_durum_ters_donusum_tutarliligi(ajan):
    """_durum_idx_to_ornek_sensor → _sensor_to_durum_idx aynı indeksi vermeli."""
    for idx in range(DURUM_SAYISI):
        sensor = ajan._durum_idx_to_ornek_sensor(idx)
        geri   = ajan._sensor_to_durum_idx(sensor)
        assert geri == idx, f"Ters dönüşüm tutarsız: idx={idx} → sensor → {geri}"


def test_optimal_durum_indeksi(ajan, profil):
    """Optimal T, H → orta bant; _sensor() değerleri de orta bantta → idx=1255."""
    s = _sensor(profil, T=profil.opt_T, H=(profil.min_H + profil.max_H) / 2,
                toprak_nem=600)
    # _sensor() helpers: co2=950 (opt=1000, ±25%=750-1250 → band 1),
    # isik=450 (min_isik=200 varsayılan, max_isik=50000 → band 1),
    # ph=6.5 (opt_pH=6.2 varsayılan, ph_high=(6.2+7.0)/2=6.6 → band 1),
    # ec=1.8 (opt_EC=1.8 varsayılan, ec_high=(1.8+3.5)/2=2.65 → band 1)
    # idx = 2×486 + 1×162 + 1×81 + 1×27 + 1×9 + 1×3 + 1 = 1255
    idx = ajan._sensor_to_durum_idx(s)
    assert idx == 2 * 486 + 1 * 162 + 1 * 81 + 1 * 27 + 1 * 9 + 1 * 3 + 1   # = 1255


# ── KuralMotoru warm-start ────────────────────────────────────

def test_warm_start_q_tablo_sifir_degil(ajan):
    """Warm-start sonrası Q-tablosunda en az bir sıfır-dışı değer olmalı."""
    import numpy as np
    assert np.any(ajan._q_tablo != 0)


def test_warm_start_kural_motoru_ile_uyumlu(ajan, profil):
    """
    Yüksek sıcaklık durumunda warm-start Q-tablosu KuralMotoru ile uyumlu
    eylem önermelidir (epsilon=0, argmax sömürü).
    """
    kural   = KuralMotoru(profil)
    s       = _sensor(profil, T=profil.opt_T + 5)   # çok sıcak → sogutma+fan
    kural_h = kural.hedef_hesapla(s, Durum.NORMAL)
    rl_h    = ajan.hedef_hesapla(s, Durum.NORMAL)
    assert rl_h == kural_h, f"warm-start uyuşmazlığı: kural={kural_h} rl={rl_h}"


# ── Online öğrenme ────────────────────────────────────────────

def test_ogren_adim_sayisi_artar(ajan):
    assert ajan.adim_sayisi == 0
    ajan.ogren(0, 0, -0.5, 1)
    assert ajan.adim_sayisi == 1
    ajan.ogren(1, 0, -0.2, 2)
    assert ajan.adim_sayisi == 2


def test_ogren_q_deger_guncellenir(ajan):
    """Q-güncelleme Bellman denklemi ile doğru çalışmalı."""
    import numpy as np
    alfa, gama = ajan.alfa, ajan.gama
    s, a, r, s_ = 5, 3, -0.5, 10

    onceki_q = float(ajan._q_tablo[s, a])
    maks_q_  = float(np.max(ajan._q_tablo[s_]))
    beklenen = onceki_q + alfa * (r + gama * maks_q_ - onceki_q)

    ajan.ogren(s, a, r, s_)
    assert abs(float(ajan._q_tablo[s, a]) - beklenen) < 1e-9


def test_ogren_diger_durumlar_degismez(ajan):
    """Bir Q güncelleme diğer (durum, eylem) çiftlerini etkilememelidir."""
    import numpy as np
    onceki = ajan._q_tablo.copy()
    ajan.ogren(5, 3, -0.5, 10)
    onceki[5, 3] = ajan._q_tablo[5, 3]   # sadece bunu güncelle
    assert np.allclose(ajan._q_tablo, onceki)


# ── Son durum / eylem erişimi ─────────────────────────────────

def test_son_durum_eylem_idx_guncellenir(ajan, profil):
    assert ajan.son_durum_idx is None
    assert ajan.son_eylem_idx is None
    s = _sensor(profil)
    ajan.hedef_hesapla(s, Durum.NORMAL)
    assert ajan.son_durum_idx is not None
    assert ajan.son_eylem_idx is not None
    assert 0 <= ajan.son_durum_idx < DURUM_SAYISI
    assert 0 <= ajan.son_eylem_idx < EYLEM_SAYISI


# ── Ödül hesaplama ────────────────────────────────────────────

def test_odul_optimal_kosulda_sifir(ajan, profil):
    """Tüm 7 değer optimal → ödül = 0."""
    h_opt = (profil.min_H + profil.max_H) / 2
    s = SensorOkuma(
        sera_id="test",
        T=profil.opt_T,
        H=h_opt,
        co2=profil.opt_CO2,
        isik=profil.opt_isik,
        toprak_nem=600,
        ph=profil.opt_pH,
        ec=profil.opt_EC,
    )
    odul = ajan.odul_hesapla(s)
    assert odul == pytest.approx(0.0, abs=1e-6)


def test_odul_kotu_kosulda_negatif(ajan, profil):
    """Kötü koşullar (yüksek T, kuru toprak) → negatif ödül."""
    s = _sensor(profil, T=profil.max_T + 5, toprak_nem=100)
    odul = ajan.odul_hesapla(s)
    assert odul < -0.5


def test_odul_kuru_toprak_cezasi(ajan, profil):
    """Kuru toprak (toprak_nem < 350) → ıslak toprağa göre daha düşük ödül."""
    s_kuru  = _sensor(profil, toprak_nem=200)
    s_islak = _sensor(profil, toprak_nem=600)
    assert ajan.odul_hesapla(s_kuru) < ajan.odul_hesapla(s_islak)


# ── Kalıcılık ─────────────────────────────────────────────────

def test_kaydet_yukle_q_tablo_esit(profil):
    """kaydet() + yukle() → Q-tablo bit-bit aynı olmalı."""
    import numpy as np
    ajan = RLAjan(profil, epsilon=0.0)
    # Birkaç güncelleme yap
    ajan.ogren(0, 1, -0.3, 5)
    ajan.ogren(5, 4, -0.1, 10)

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        yol = f.name

    try:
        ajan.kaydet(yol)
        ajan2 = RLAjan.yukle(yol, profil, epsilon=0.0)
        assert np.allclose(ajan._q_tablo, ajan2._q_tablo)
        assert ajan.adim_sayisi == ajan2.adim_sayisi
    finally:
        os.unlink(yol)


def test_kaydet_yukle_karar_ayni(profil):
    """Kaydedip yüklenen ajan aynı kararı vermeli."""
    ajan = RLAjan(profil, epsilon=0.0)
    s    = _sensor(profil, T=profil.opt_T + 5)
    h_onceki = ajan.hedef_hesapla(s, Durum.NORMAL)

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        yol = f.name

    try:
        ajan.kaydet(yol)
        ajan2 = RLAjan.yukle(yol, profil, epsilon=0.0)
        h_sonraki = ajan2.hedef_hesapla(s, Durum.NORMAL)
        assert h_onceki == h_sonraki
    finally:
        os.unlink(yol)


# ── baslangic_yukle / kapatma_kaydet lifecycle ────────────────

def test_baslangic_yukle_dosya_yoksa_sessiz(profil):
    """Model dosyası yoksa baslangic_yukle() hata vermemeli."""
    ajan = RLAjan(profil, epsilon=0.0)
    ajan.baslangic_yukle("modeller_yok_dizin", "s1")   # sessiz geçmeli


def test_kapatma_kaydet_ve_baslangic_yukle_dongusu(profil):
    """kapatma_kaydet + baslangic_yukle → Q-tablo ve adim_sayisi korunmalı."""
    import numpy as np
    ajan = RLAjan(profil, epsilon=0.0)
    ajan.ogren(0, 1, -0.5, 3)
    ajan.ogren(5, 4, -0.1, 8)
    adim_sayisi_onceki = ajan.adim_sayisi

    with tempfile.TemporaryDirectory() as tmpdir:
        ajan.kapatma_kaydet(tmpdir, "s_test")

        ajan2 = RLAjan(profil, epsilon=0.0)
        ajan2.baslangic_yukle(tmpdir, "s_test")

        assert ajan2.adim_sayisi == adim_sayisi_onceki
        assert np.allclose(ajan._q_tablo, ajan2._q_tablo)


def test_kural_motoru_lifecycle_noop(profil):
    """KuralMotoru.baslangic_yukle() ve kapatma_kaydet() hata vermemeli (no-op)."""
    kural = KuralMotoru(profil)
    kural.baslangic_yukle("herhangi_dizin", "s1")
    kural.kapatma_kaydet("herhangi_dizin", "s1")


# ── geri_bildirim() öğrenme döngüsü ──────────────────────────

def test_geri_bildirim_adim_sayisi_artar(ajan, profil):
    """İki geçerli sensörle geri_bildirim() → adim_sayisi 1 artmalı."""
    s1 = _sensor(profil, T=profil.opt_T + 3)
    s2 = _sensor(profil, T=profil.opt_T + 1)
    ajan.hedef_hesapla(s1, Durum.NORMAL)   # durum + eylem kaydet
    assert ajan.adim_sayisi == 0
    ajan.geri_bildirim(s1, s2)
    assert ajan.adim_sayisi == 1


def test_geri_bildirim_q_degeri_degisir(ajan, profil):
    """geri_bildirim() çağrısı sonrası ilgili Q değeri değişmeli."""
    import numpy as np
    s1 = _sensor(profil, T=profil.opt_T + 5)  # çok sıcak
    ajan.hedef_hesapla(s1, Durum.NORMAL)

    d_idx = ajan.son_durum_idx
    a_idx = ajan.son_eylem_idx
    onceki_q = float(ajan._q_tablo[d_idx, a_idx])

    s2 = _sensor(profil, T=profil.opt_T + 3)
    ajan.geri_bildirim(s1, s2)

    assert float(ajan._q_tablo[d_idx, a_idx]) != onceki_q


def test_geri_bildirim_onceki_karar_yoksa_sessiz(ajan, profil):
    """hedef_hesapla() çağrılmadan geri_bildirim() → hata vermemeli."""
    s1 = _sensor(profil)
    s2 = _sensor(profil, T=profil.opt_T + 1)
    ajan.geri_bildirim(s1, s2)   # sessiz geçmeli
    assert ajan.adim_sayisi == 0


def test_geri_bildirim_kural_motoru_noop(profil):
    """KuralMotoru.geri_bildirim() hata vermemeli (no-op)."""
    kural = KuralMotoru(profil)
    s1 = _sensor(profil)
    s2 = _sensor(profil, T=profil.opt_T + 1)
    kural.geri_bildirim(s1, s2)   # no-op, hata yok


# ── KontrolMotoru öğrenme döngüsü entegrasyonu ───────────────

def _motor_rl_kur(profil, epsilon=0.0):
    from sera_ai.application.control_engine import KontrolMotoru
    from sera_ai.application.event_bus import EventBus, OlayTur
    from sera_ai.domain.circuit_breaker import CircuitBreaker
    from sera_ai.domain.state_machine import SeraStateMachine
    from sera_ai.drivers.mock import MockSahaNode

    ajan  = RLAjan(profil, epsilon=epsilon)
    node  = MockSahaNode("s1", profil, sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node.baglan()
    bus   = EventBus()
    cb    = CircuitBreaker("test", hata_esigi=10)
    sm    = SeraStateMachine(
        "s1", profil,
        on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d),
    )
    motor = KontrolMotoru(
        sera_id="s1", profil=profil,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
        optimizer=ajan,
    )
    return motor, ajan


def test_rl_ajan_kontrol_motoru_di(profil):
    """RLAjan, KontrolMotoru'na optimizer= olarak verilebilmeli."""
    motor, ajan = _motor_rl_kur(profil)
    assert motor.optimizer is ajan
    s = _sensor(profil)
    motor.adim_at(s)   # hata fırlatmamalı


def test_kontrol_motoru_ilk_adimda_ogrenme_yok(profil):
    """İlk adim_at() → geri_bildirim yok, adim_sayisi=0 kalmalı."""
    motor, ajan = _motor_rl_kur(profil)
    motor.adim_at(_sensor(profil))
    assert ajan.adim_sayisi == 0


def test_kontrol_motoru_ikinci_adimda_ogrenme_baslar(profil):
    """İki adim_at() → ikincisinde geri_bildirim çağrılır, adim_sayisi=1."""
    motor, ajan = _motor_rl_kur(profil)
    motor.adim_at(_sensor(profil, T=profil.opt_T + 3))
    motor.adim_at(_sensor(profil, T=profil.opt_T + 1))
    assert ajan.adim_sayisi == 1


def test_kontrol_motoru_n_adim_ogrenme(profil):
    """N adim_at() → (N-1) Q-güncelleme yapılmalı."""
    motor, ajan = _motor_rl_kur(profil)
    n = 10
    for i in range(n):
        motor.adim_at(_sensor(profil, T=profil.opt_T + (i % 3)))
    assert ajan.adim_sayisi == n - 1


def test_gecersiz_sensor_ogrenme_zinciri_sifirlaniyor(profil):
    """Geçersiz sensör → zincir sıfırlanır, sonraki geçerli sensörde öğrenme olmaz."""
    motor, ajan = _motor_rl_kur(profil)

    # Geçerli sensör → zincir başlar
    motor.adim_at(_sensor(profil))
    assert motor._onceki_sensor is not None

    # Geçersiz sensör → zincir sıfırlanır
    gecersiz = SensorOkuma(
        sera_id="s1", T=-999, H=72, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(gecersiz)
    assert motor._onceki_sensor is None
    assert ajan.adim_sayisi == 0  # geçersiz sensörde geri_bildirim olmadı

    # Tekrar geçerli → önceki sensor yok, öğrenme yok
    motor.adim_at(_sensor(profil))
    assert ajan.adim_sayisi == 0


def test_kontrol_motoru_kural_motoru_ogrenme_yok(profil):
    """KuralMotoru ile çalışan KontrolMotoru adim_at() hata vermemeli."""
    from sera_ai.application.control_engine import KontrolMotoru
    from sera_ai.application.event_bus import EventBus, OlayTur
    from sera_ai.domain.circuit_breaker import CircuitBreaker
    from sera_ai.domain.state_machine import SeraStateMachine
    from sera_ai.drivers.mock import MockSahaNode
    from sera_ai.intelligence.kural_motoru import KuralMotoru as KM

    node  = MockSahaNode("s1", profil, sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node.baglan()
    bus   = EventBus()
    cb    = CircuitBreaker("test", hata_esigi=10)
    sm    = SeraStateMachine("s1", profil,
                             on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d))
    motor = KontrolMotoru(
        sera_id="s1", profil=profil,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
        optimizer=KM(profil),
    )
    for _ in range(5):
        motor.adim_at(_sensor(profil))   # hata vermemeli
