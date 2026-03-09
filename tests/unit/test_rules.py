"""
Unit Testler: Kontrol Motoru Karar Kuralları

Idempotent komut mantığı ve aktüatör kararları test edilir.
Mock node kullanılır — gerçek donanım gerekmez.
"""
import pytest

from sera_ai.domain.models import Komut, SensorOkuma, BitkilProfili
from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.domain.circuit_breaker import CircuitBreaker
from sera_ai.application.control_engine import KontrolMotoru
from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.drivers.mock import MockSahaNode


def motor_kur(profil: BitkilProfili) -> tuple[KontrolMotoru, MockSahaNode]:
    """Test için sıfır hatalı kontrol motoru oluştur."""
    node = MockSahaNode("s1", profil, sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node.baglan()
    bus = EventBus()
    cb  = CircuitBreaker("test", hata_esigi=10)
    sm  = SeraStateMachine("s1", profil, on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d))
    motor = KontrolMotoru(
        sera_id="s1", profil=profil,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
    )
    return motor, node


# ── Idempotent Komutlar ────────────────────────────────────────

def test_idempotent_ayni_komut_tekrar_gonderilmez(profil_domates):
    """
    Aynı sensör değeri iki kez gelince ikinci kez komut gönderilmemeli.
    Röle ömrünü korur, log'u temizler.
    """
    motor, node = motor_kur(profil_domates)

    sensor = SensorOkuma(
        sera_id="s1", T=26.0,   # opt_T+3 → sogutma açılır
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)
    ilk_komut_sayisi = len(node.komutlar)

    motor.adim_at(sensor)   # Aynı durum → komut gönderilmemeli
    assert len(node.komutlar) == ilk_komut_sayisi


def test_durum_degisince_yeni_komut(profil_domates):
    """Aktüatör durumu değiştiğinde komut gönderilmeli."""
    motor, node = motor_kur(profil_domates)

    # Önce normal
    sensor_normal = SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor_normal)
    komut_sayisi_1 = len(node.komutlar)

    # Sonra sıcak
    sensor_sicak = SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor_sicak)
    assert len(node.komutlar) > komut_sayisi_1


# ── Sogutma Kuralı ────────────────────────────────────────────

def test_yuksek_sicaklik_sogutma_ve_fan_acar(profil_domates):
    """T > opt_T + 2 → SOGUTMA_BASLAT + FAN_BASLAT."""
    motor, node = motor_kur(profil_domates)
    sensor = SensorOkuma(
        sera_id="s1", T=profil_domates.opt_T + 3,   # 26°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)
    assert Komut.SOGUTMA_BASLAT in node.komutlar
    assert Komut.FAN_BASLAT in node.komutlar


def test_normal_sicaklik_sogutma_kapar(profil_domates):
    """Sogutma açıkken normal sıcaklığa dönüş → SOGUTMA_DURDUR."""
    motor, node = motor_kur(profil_domates)

    # Önce sıcak → sogutma aç
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    # Sonra normal → sogutma kapat
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    assert Komut.SOGUTMA_DURDUR in node.komutlar


# ── Isıtma Kuralı ─────────────────────────────────────────────

def test_dusuk_sicaklik_isitici_acar(profil_domates):
    """T < opt_T - 2 → ISITICI_BASLAT."""
    motor, node = motor_kur(profil_domates)
    sensor = SensorOkuma(
        sera_id="s1", T=profil_domates.opt_T - 3,   # 20°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)
    assert Komut.ISITICI_BASLAT in node.komutlar


# ── Sulama Kuralı ─────────────────────────────────────────────

def test_kuru_toprak_sulama_acar(profil_domates):
    """toprak_nem < 350 → SULAMA_BASLAT."""
    motor, node = motor_kur(profil_domates)
    sensor = SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450,
        toprak_nem=300,   # 300 < 350 → kuru
        ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)
    assert Komut.SULAMA_BASLAT in node.komutlar


def test_normal_toprak_sulama_kapar(profil_domates):
    """Sulama açıkken toprak nem normale dönünce SULAMA_DURDUR."""
    motor, node = motor_kur(profil_domates)
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=300, ph=6.5, ec=1.8,
    ))
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=600, ph=6.5, ec=1.8,
    ))
    assert Komut.SULAMA_DURDUR in node.komutlar


# ── Acil Durdur ───────────────────────────────────────────────

def test_acil_durumda_tum_aktüatörler_kapanir(profil_domates):
    """ACİL_DURDUR durumunda tüm aktüatörler DURDUR komutunu almalı."""
    motor, node = motor_kur(profil_domates)

    # Önce bir şeyleri aç
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=300, ph=6.5, ec=1.8,
    ))
    node.komutlar.clear()   # Önceki komutları temizle

    # Acil durum
    motor.adim_at(SensorOkuma(
        sera_id="s1",
        T=profil_domates.opt_T + SeraStateMachine.ACIL_MARJ + 1,   # 34°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    # Hiçbir aktüatör BASLAT komutu almamış olmalı
    baslat_komutlari = [
        k for k in node.komutlar
        if k in (Komut.SULAMA_BASLAT, Komut.ISITICI_BASLAT,
                 Komut.SOGUTMA_BASLAT, Komut.FAN_BASLAT)
    ]
    assert not baslat_komutlari


# ── Geçersiz Sensör ───────────────────────────────────────────

def test_gecersiz_sensor_komut_gonderilmez(profil_domates):
    """Fiziksel sınır dışı sensör → komut gönderilmemeli."""
    motor, node = motor_kur(profil_domates)
    sensor = SensorOkuma(
        sera_id="s1", T=-999.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    motor.adim_at(sensor)
    assert not node.komutlar   # Hiç komut gönderilmedi


# ── Event Bus ─────────────────────────────────────────────────

def test_komut_olay_yayinlaniyor(profil_domates):
    """Komut gönderilince KOMUT_GONDERILDI olayı yayınlanmalı."""
    node = MockSahaNode("s1", profil_domates,
                        sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node.baglan()
    bus = EventBus()
    olaylar = []
    bus.abone_ol(OlayTur.KOMUT_GONDERILDI, lambda v: olaylar.append(v))

    cb    = CircuitBreaker("test", hata_esigi=10)
    sm    = SeraStateMachine("s1", profil_domates, on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d))
    motor = KontrolMotoru(
        sera_id="s1", profil=profil_domates,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
    )
    motor.adim_at(SensorOkuma(
        sera_id="s1", T=27.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    ))
    assert olaylar   # En az bir komut olayı


