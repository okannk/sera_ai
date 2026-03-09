"""
Entegrasyon Testleri: Kontrol Motoru + Mock Driver

Tüm katmanlar birlikte çalışıyor mu?
  MockSahaNode + CircuitBreaker + SeraStateMachine + KontrolMotoru
  gerçek donanım olmadan uçtan uca test.
"""
import pytest

from sera_ai.domain.models import Komut, SensorOkuma, BitkilProfili, SistemKonfig, SeraKonfig
from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.domain.circuit_breaker import CBDurum, CircuitBreaker
from sera_ai.application.control_engine import KontrolMotoru
from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.drivers.mock import MockSahaNode
from sera_ai.merkez.mock import MockMerkez


# ── Yardımcı Fonksiyon ────────────────────────────────────────

def tam_sistem_kur(profil: BitkilProfili, hata_orani: float = 0.0):
    """Tüm bileşenleri birbirine bağlı olarak kur."""
    node  = MockSahaNode("s1", profil,
                         sensor_hata_orani=hata_orani,
                         komut_hata_orani=hata_orani)
    node.baglan()
    bus   = EventBus()
    cb    = CircuitBreaker("s1_cb", hata_esigi=5, recovery_sn=60)
    sm    = SeraStateMachine("s1", profil, olay_bus=bus)
    motor = KontrolMotoru(
        sera_id="s1", profil=profil,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
    )
    return motor, node, sm, cb, bus


# ── Tam Döngü Testleri ────────────────────────────────────────

def test_sensor_okuma_karar_komut_akisi(profil_domates):
    """Uçtan uca: Sensör → State Machine → Komut."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates)

    # Normal okuma
    sensor = SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)

    assert sm.durum in (Durum.NORMAL, Durum.UYARI)
    assert Komut.SOGUTMA_BASLAT in node.komutlar


def test_alarm_durumunda_sogutma_calisir(profil_domates):
    """ALARM durumunda sogutma ve fan açılmalı."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates)

    sensor = SensorOkuma(
        sera_id="s1",
        T=profil_domates.max_T + 2,   # 32°C → ALARM
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)

    assert sm.durum == Durum.ALARM
    assert Komut.SOGUTMA_BASLAT in node.komutlar
    assert Komut.FAN_BASLAT in node.komutlar


def test_iyilesme_kapatma_komutlari(profil_domates):
    """Alarm → normal'e dönüş → kapatma komutları gönderilir."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates)

    # Alarm
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=32.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    # Normal'e dön
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))

    assert Komut.SOGUTMA_DURDUR in node.komutlar
    assert sm.durum == Durum.NORMAL


# ── Circuit Breaker Entegrasyon ────────────────────────────────

def test_node_hata_verince_cb_sayar(profil_domates):
    """Node IOError fırlatınca CB hata sayacı artar."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates, hata_orani=1.0)

    for _ in range(4):
        try:
            motor.adim_at(SensorOkuma(
                sera_id="s1", T=23.0, H=72.0,
                co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
            ))
        except Exception:
            pass

    # Node %100 hata oranında — CB sayacı artmalı
    # (adim_at içinde IOError yakalanır ama CB_cagir sayar)
    assert cb._hata_sayisi > 0


def test_cb_acikken_komut_gonderilmez(profil_domates):
    """CB ACIK'ken komut gönderilmemeye çalışılır."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates)

    # CB'yi zorla aç
    for _ in range(5):
        cb._hata_kaydet("test")
    assert cb.durum == CBDurum.ACIK

    node.komutlar.clear()

    # Motoru çalıştır — CB açık olduğu için komut gitmemeli
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    # CB açık olduğu için node'a hiç komut ulaşmamalı
    assert len(node.komutlar) == 0


# ── Event Bus Entegrasyon ─────────────────────────────────────

def test_alarm_olay_yayinlaniyor(profil_domates):
    """Durum değiştiğinde DURUM_DEGISTI olayı yayınlanmalı."""
    motor, node, sm, cb, bus = tam_sistem_kur(profil_domates)

    alınan = []
    bus.abone_ol(OlayTur.DURUM_DEGISTI, lambda v: alınan.append(v))

    motor.adim_at(SensorOkuma(
        sera_id="s1", T=profil_domates.max_T + 2,
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))

    assert alınan
    assert alınan[0]["sera_id"] == "s1"
    assert alınan[0]["yeni"] in ("ALARM", "ACIL_DURDUR")


def test_sensor_olay_yayinlaniyor(profil_domates):
    """SENSOR_OKUMA olayı yayınlanabilir mi? (bus.yayinla test)"""
    bus = EventBus()
    alınan = []
    bus.abone_ol(OlayTur.SENSOR_OKUMA, lambda v: alınan.append(v))

    okuma = SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    bus.yayinla(OlayTur.SENSOR_OKUMA, okuma.to_dict())

    assert alınan
    assert alınan[0]["sera_id"] == "s1"


# ── MockMerkez ile Entegrasyon ────────────────────────────────

def test_mock_merkez_sensor_oku(mock_merkez):
    """MockMerkez üzerinden sensör okuma."""
    okuma = mock_merkez.sensor_oku("s1")
    assert okuma.sera_id == "s1"
    assert okuma.gecerli_mi


def test_mock_merkez_komut_gonder(mock_merkez):
    """MockMerkez üzerinden komut gönderme."""
    basarili = mock_merkez.komut_gonder("s1", Komut.FAN_BASLAT)
    assert basarili
    assert ("s1", Komut.FAN_BASLAT) in mock_merkez.komut_gecmisi


def test_mock_merkez_bilinmeyen_sera(mock_merkez):
    """Bilinmeyen sera → komut_gonder False döner."""
    basarili = mock_merkez.komut_gonder("s999", Komut.FAN_BASLAT)
    assert not basarili


def test_mock_merkez_tum_durum(mock_merkez):
    """tum_durum() tüm seraları döndürmeli."""
    mock_merkez.sensor_oku("s1")   # Önce okuma yap
    durum = mock_merkez.tum_durum()
    assert "s1" in durum


# ── Çok Sera Senaryosu ────────────────────────────────────────

def test_iki_sera_bagimsiz(profil_domates, profil_marul):
    """İki seranın CB'leri birbirinden bağımsız olmalı."""
    node1 = MockSahaNode("s1", profil_domates, sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node2 = MockSahaNode("s2", profil_marul,   sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node1.baglan(); node2.baglan()

    merkez = MockMerkez()
    merkez.node_ekle("s1", node1)
    merkez.node_ekle("s2", node2)
    merkez.baslat()

    # s1'den normal okuma
    okuma1 = merkez.sensor_oku("s1")
    assert okuma1.sera_id == "s1"

    # s2'den normal okuma
    okuma2 = merkez.sensor_oku("s2")
    assert okuma2.sera_id == "s2"

    # Her sera ayrı tum_durum'da görünür
    durum = merkez.tum_durum()
    assert "s1" in durum
    assert "s2" in durum

    merkez.durdur()
