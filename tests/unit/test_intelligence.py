"""
Unit Testler: Intelligence Katmanı

KuralMotoru, MockOptimizer ve KontrolMotoru DI entegrasyonu.
"""
import pytest

from sera_ai.domain.models import BitkilProfili, Komut, SensorOkuma
from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.domain.circuit_breaker import CircuitBreaker
from sera_ai.application.control_engine import KontrolMotoru
from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.drivers.mock import MockSahaNode
from sera_ai.intelligence.base import HedefDeger, OptimizerBase
from sera_ai.intelligence.kural_motoru import KuralMotoru
from sera_ai.intelligence.mock import MockOptimizer


# ── HedefDeger ────────────────────────────────────────────────

def test_hedef_deger_varsayilan_hepsi_kapali():
    """Varsayılan HedefDeger: tüm aktüatörler kapalı."""
    h = HedefDeger()
    assert h.sulama  is False
    assert h.isitici is False
    assert h.sogutma is False
    assert h.fan     is False


def test_hedef_deger_to_dict():
    """to_dict() tüm dört alanı döndürmeli."""
    h = HedefDeger(sulama=True, fan=True)
    d = h.to_dict()
    assert d == {"sulama": True, "isitici": False, "sogutma": False, "fan": True}


# ── KuralMotoru ───────────────────────────────────────────────

@pytest.fixture
def profil() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )


@pytest.fixture
def kural(profil) -> KuralMotoru:
    return KuralMotoru(profil)


def _sensor(profil, T=None, H=None, toprak_nem=500):
    return SensorOkuma(
        sera_id="s1",
        T=T if T is not None else profil.opt_T,
        H=H if H is not None else 72.0,
        co2=950, isik=450, toprak_nem=toprak_nem, ph=6.5, ec=1.8,
    )


def test_kural_normal_durum_hepsi_kapali(kural, profil):
    """Normal koşullar → tüm aktüatörler kapalı."""
    s = _sensor(profil)
    h = kural.hedef_hesapla(s, Durum.NORMAL)
    assert h == HedefDeger()


def test_kural_yuksek_sicaklik_sogutma_fan(kural, profil):
    """opt_T + 3°C → sogutma + fan açık."""
    s = _sensor(profil, T=profil.opt_T + 3)
    h = kural.hedef_hesapla(s, Durum.UYARI)
    assert h.sogutma is True
    assert h.fan     is True
    assert h.isitici is False


def test_kural_dusuk_sicaklik_isitici(kural, profil):
    """opt_T - 3°C → ısıtıcı açık."""
    s = _sensor(profil, T=profil.opt_T - 3)
    h = kural.hedef_hesapla(s, Durum.UYARI)
    assert h.isitici is True
    assert h.sogutma is False


def test_kural_yuksek_nem_fan(kural, profil):
    """max_H üstü nem → fan açık."""
    s = _sensor(profil, H=profil.max_H + 5)
    h = kural.hedef_hesapla(s, Durum.NORMAL)
    assert h.fan is True


def test_kural_dusuk_nem_sulama(kural, profil):
    """min_H altı nem → sulama açık."""
    s = _sensor(profil, H=profil.min_H - 5)
    h = kural.hedef_hesapla(s, Durum.NORMAL)
    assert h.sulama is True


def test_kural_kuru_toprak_sulama(kural, profil):
    """toprak_nem < 350 → sulama açık."""
    s = _sensor(profil, toprak_nem=300)
    h = kural.hedef_hesapla(s, Durum.NORMAL)
    assert h.sulama is True


def test_kural_acil_durdur_hepsi_kapali(kural, profil):
    """ACİL_DURDUR → tüm aktüatörler kapalı (yüksek sıcaklık olsa bile)."""
    s = _sensor(profil, T=profil.opt_T + 10)
    h = kural.hedef_hesapla(s, Durum.ACIL_DURDUR)
    assert h == HedefDeger()


def test_kural_optimizer_base_alt_sinifi():
    """KuralMotoru, OptimizerBase'den türemeli."""
    assert issubclass(KuralMotoru, OptimizerBase)


# ── MockOptimizer ─────────────────────────────────────────────

def test_mock_optimizer_varsayilan_kapali(profil):
    """MockOptimizer varsayılan: tüm aktüatörler kapalı."""
    m = MockOptimizer()
    s = _sensor(profil)
    h = m.hedef_hesapla(s, Durum.NORMAL)
    assert h == HedefDeger()


def test_mock_optimizer_sabit_deger(profil):
    """MockOptimizer yapılandırılan sabit değeri döndürmeli."""
    sabit = HedefDeger(sulama=True, fan=True)
    m = MockOptimizer(sabit)
    s = _sensor(profil)
    h = m.hedef_hesapla(s, Durum.ALARM)
    assert h.sulama is True
    assert h.fan    is True


def test_mock_optimizer_cagri_sayar(profil):
    """MockOptimizer kaç kez çağrıldığını saymalı."""
    m = MockOptimizer()
    s = _sensor(profil)
    m.hedef_hesapla(s, Durum.NORMAL)
    m.hedef_hesapla(s, Durum.ALARM)
    assert m.cagri_sayisi == 2


def test_mock_optimizer_optimizer_base_alt_sinifi():
    """MockOptimizer, OptimizerBase'den türemeli."""
    assert issubclass(MockOptimizer, OptimizerBase)


# ── KontrolMotoru DI Entegrasyonu ────────────────────────────

def _motor_kur(profil, optimizer=None):
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
        optimizer=optimizer,
    )
    return motor, node, bus


def test_kontrol_motoru_varsayilan_kural_motoru(profil):
    """optimizer=None → KuralMotoru otomatik oluşturulmalı."""
    motor, _, _ = _motor_kur(profil)
    assert isinstance(motor.optimizer, KuralMotoru)


def test_kontrol_motoru_mock_optimizer_kullanir(profil):
    """Verilen optimizer kullanılmalı, KuralMotoru değil."""
    mock = MockOptimizer(HedefDeger(sulama=True))
    motor, _, _ = _motor_kur(profil, optimizer=mock)
    assert motor.optimizer is mock


def test_mock_optimizer_adim_ati_cagrilir(profil):
    """adim_at() çağrılınca optimizer.hedef_hesapla() çağrılmalı."""
    mock  = MockOptimizer()
    motor, node, _ = _motor_kur(profil, optimizer=mock)
    s = _sensor(profil)
    motor.adim_at(s)
    assert mock.cagri_sayisi == 1


def test_mock_optimizer_acil_durdur_gormezden_gelmez(profil):
    """
    MockOptimizer ACİL_DURDUR durumunu gormezden gelip sabit değeri döndürür.
    Bu, kural motorundan farklı davranışı test eder.
    """
    # Mock: yüksek sıcaklıkta bile sogutma açık (ACİL_DURDUR yok sayılır)
    mock  = MockOptimizer(HedefDeger(sogutma=True))
    motor, _, _ = _motor_kur(profil, optimizer=mock)
    s = _sensor(profil, T=profil.opt_T + 15)  # ACİL_DURDUR eşiği
    motor.adim_at(s)
    # Mock döndürdü → komut gönderildi, CB saymadı
    assert mock.cagri_sayisi == 1
