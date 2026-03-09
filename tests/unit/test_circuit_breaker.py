"""
Unit Testler: CircuitBreaker

Zaman bağımlı testler için monkeypatch kullanılır.
"""
import time
import pytest

from sera_ai.domain.circuit_breaker import CBDurum, CircuitBreaker


def basarili_fn():
    return "OK"

def basarisiz_fn():
    raise IOError("Donanım yanıt vermedi")


# ── Başlangıç Durumu ───────────────────────────────────────────

def test_kapali_baslar():
    """Yeni CB KAPALI durumda olmalı."""
    cb = CircuitBreaker("test", hata_esigi=5)
    assert cb.durum == CBDurum.KAPALI


def test_sifir_hata_kapali_kaliyor():
    """Hiç hata yokken KAPALI kalmalı."""
    cb = CircuitBreaker("test", hata_esigi=3)
    cb.cagir(basarili_fn)
    assert cb.durum == CBDurum.KAPALI


# ── Açılma Koşulu ─────────────────────────────────────────────

def test_esik_kadar_hatayla_acilir():
    """5 hata → ACIK."""
    cb = CircuitBreaker("test", hata_esigi=5)
    for _ in range(5):
        with pytest.raises(IOError):
            cb.cagir(basarisiz_fn)
    assert cb.durum == CBDurum.ACIK


def test_esik_altinda_kapali_kaliyor():
    """4 hata (eşik 5) → KAPALI kalmalı."""
    cb = CircuitBreaker("test", hata_esigi=5)
    for _ in range(4):
        with pytest.raises(IOError):
            cb.cagir(basarisiz_fn)
    assert cb.durum == CBDurum.KAPALI


def test_acik_durumda_cagrilmaz():
    """CB ACIK'ken fn çağrılmamalı, RuntimeError fırlatılmalı."""
    cb = CircuitBreaker("test", hata_esigi=1, recovery_sn=999)
    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)
    assert cb.durum == CBDurum.ACIK

    çağrıldı = []
    with pytest.raises(RuntimeError):
        cb.cagir(lambda: çağrıldı.append(True))
    assert not çağrıldı   # fn hiç çağrılmadı


# ── Recovery ──────────────────────────────────────────────────

def test_recovery_sonrasi_yari_acik(monkeypatch):
    """recovery_sn geçince YARI_ACIK'a geçmeli."""
    cb = CircuitBreaker("test", hata_esigi=1, recovery_sn=1)
    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)
    assert cb.durum == CBDurum.ACIK

    # Zamanı ilerlet
    ilk_zaman = cb._acilis_zaman
    monkeypatch.setattr(time, "time", lambda: ilk_zaman + 2)
    assert cb.durum == CBDurum.YARI_ACIK


def test_yari_acikta_basarili_kapatir(monkeypatch):
    """YARI_ACIK → başarılı çağrı → KAPALI."""
    cb = CircuitBreaker("test", hata_esigi=1, recovery_sn=1)
    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)

    ilk_zaman = cb._acilis_zaman
    monkeypatch.setattr(time, "time", lambda: ilk_zaman + 2)
    assert cb.durum == CBDurum.YARI_ACIK

    cb.cagir(basarili_fn)
    assert cb.durum == CBDurum.KAPALI


def test_yari_acikta_basarisiz_tekrar_acar(monkeypatch):
    """YARI_ACIK → başarısız → tekrar ACIK."""
    cb = CircuitBreaker("test", hata_esigi=1, recovery_sn=1)
    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)

    ilk_zaman = cb._acilis_zaman
    monkeypatch.setattr(time, "time", lambda: ilk_zaman + 2)
    assert cb.durum == CBDurum.YARI_ACIK

    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)
    # time.time hâlâ mocklı ama acilis_zaman güncellendi
    # Yeniden CB açıldı mı kontrol et
    cb2_zaman = cb._acilis_zaman
    monkeypatch.setattr(time, "time", lambda: cb2_zaman + 0.5)
    assert cb.durum == CBDurum.ACIK


# ── Sıfırlama ─────────────────────────────────────────────────

def test_manuel_sifirlama():
    """sifirla() → KAPALI ve sayaç sıfır."""
    cb = CircuitBreaker("test", hata_esigi=3)
    for _ in range(3):
        with pytest.raises(IOError):
            cb.cagir(basarisiz_fn)
    assert cb.durum == CBDurum.ACIK

    cb.sifirla()
    assert cb.durum == CBDurum.KAPALI
    assert cb._hata_sayisi == 0


# ── Başarı Geri Besleme ────────────────────────────────────────

def test_basarili_hata_sayacini_dusuror():
    """Başarılar hata sayacını yavaşça düşürür."""
    cb = CircuitBreaker("test", hata_esigi=5)
    for _ in range(3):
        with pytest.raises(IOError):
            cb.cagir(basarisiz_fn)
    assert cb._hata_sayisi == 3

    cb.cagir(basarili_fn)   # 3 → 2
    assert cb._hata_sayisi == 2


# ── repr ───────────────────────────────────────────────────────

def test_repr():
    cb = CircuitBreaker("sera_s1", hata_esigi=5)
    r = repr(cb)
    assert "sera_s1" in r
    assert "KAPALI" in r


# ── Kalan Süre ────────────────────────────────────────────────

def test_kalan_sn_acikta_hesaplanir(monkeypatch):
    """ACIK durumda kalan_sn doğru hesaplanmalı."""
    cb = CircuitBreaker("test", hata_esigi=1, recovery_sn=60)
    with pytest.raises(IOError):
        cb.cagir(basarisiz_fn)

    ilk_zaman = cb._acilis_zaman
    monkeypatch.setattr(time, "time", lambda: ilk_zaman + 10)
    assert cb.kalan_sn == 50
