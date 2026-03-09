"""
Unit Testler: SeraStateMachine

Her test bağımsız — fixture inject edilir, dış bağımlılık yok.
"""
import pytest

from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.domain.models import SensorOkuma, BitkilProfili
from sera_ai.application.event_bus import EventBus, OlayTur


# ── Temel Durum Geçişleri ──────────────────────────────────────

def test_baslangic_durumu(state_machine):
    """Yeni oluşturulan state machine BASLATILAMADI durumunda olmalı."""
    assert state_machine.durum == Durum.BASLATILAMADI


def test_normal_okuma_normal_duruma_gecer(state_machine, sensor_normal):
    """Optimal banttaki sensör → NORMAL durumu."""
    yeni = state_machine.guncelle(sensor_normal)
    assert yeni == Durum.NORMAL


def test_yuksek_sicaklik_uyari(state_machine, profil_domates):
    """opt_T + 4°C → UYARI (marj=3°C)."""
    sensor = SensorOkuma(
        sera_id="s1",
        T=profil_domates.opt_T + 4,   # 27°C → 4 > UYARI_MARJ(3)
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.UYARI


def test_max_T_alarm(state_machine, profil_domates):
    """max_T aşılınca ALARM."""
    sensor = SensorOkuma(
        sera_id="s1",
        T=profil_domates.max_T + 1,   # 31°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.ALARM


def test_kritik_sicaklik_acil_durdur(state_machine, profil_domates):
    """opt_T + 10°C aşılınca ACİL_DURDUR."""
    sensor = SensorOkuma(
        sera_id="s1",
        T=profil_domates.opt_T + SeraStateMachine.ACIL_MARJ + 1,  # 34°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.ACIL_DURDUR


def test_dusuk_sicaklik_uyari(state_machine, profil_domates):
    """min_T altına düşünce ALARM."""
    sensor = SensorOkuma(
        sera_id="s1",
        T=profil_domates.min_T - 1,   # 14°C
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.ALARM


# ── Nem Kuralları ──────────────────────────────────────────────

def test_yuksek_nem_uyari(state_machine, profil_domates):
    """max_H üstünde nem → UYARI."""
    sensor = SensorOkuma(
        sera_id="s1", T=23.0,
        H=profil_domates.max_H + 5,   # 90%
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.UYARI


def test_kritik_yuksek_nem_alarm(state_machine):
    """%95+ nem → ALARM."""
    sensor = SensorOkuma(
        sera_id="s1", T=23.0, H=97.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    yeni = state_machine.guncelle(sensor)
    assert yeni == Durum.ALARM


# ── Manuel Kontrol ─────────────────────────────────────────────

def test_manuel_kontrol_gecisi(state_machine, sensor_normal):
    """Manuel devralmadan sonra otomatik geçiş yapılmamalı."""
    state_machine.guncelle(sensor_normal)   # NORMAL'e geç
    state_machine.manuel_devral("Test")
    assert state_machine.durum == Durum.MANUEL_KONTROL

    # Alarm seviyesi sensör gelse bile durum değişmemeli
    sensor_kotu = SensorOkuma(
        sera_id="s1", T=40.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    state_machine.guncelle(sensor_kotu)
    assert state_machine.durum == Durum.MANUEL_KONTROL


def test_otomatiğe_donuş(state_machine, sensor_normal):
    """Manuel kontrolden otomatiğe dönüş."""
    state_machine.manuel_devral("Test")
    state_machine.otomatiğe_don(sensor_normal)
    assert state_machine.durum == Durum.NORMAL


# ── Geçiş Kaydı ───────────────────────────────────────────────

def test_gecmis_kayit_edilir(state_machine, sensor_normal, sensor_alarm_sicaklik):
    """Durum değişikliği geçmişe kaydedilmeli."""
    state_machine.guncelle(sensor_normal)
    state_machine.guncelle(sensor_alarm_sicaklik)
    assert len(state_machine.gecmis) >= 2


def test_gecmis_sebep_iceriyor(state_machine, profil_domates):
    """Geçiş kaydında sebep bilgisi olmalı."""
    sensor = SensorOkuma(
        sera_id="s1", T=profil_domates.max_T + 1,
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    state_machine.guncelle(sensor)
    assert state_machine.gecmis
    assert state_machine.gecmis[-1].sebep


# ── Event Bus Entegrasyonu ─────────────────────────────────────

def test_durum_degisince_olay_yayinlar(profil_domates):
    """Durum değiştiğinde DURUM_DEGISTI olayı yayınlanmalı."""
    bus = EventBus()
    alınan_olaylar = []
    bus.abone_ol(OlayTur.DURUM_DEGISTI, lambda v: alınan_olaylar.append(v))

    sm = SeraStateMachine("s1", profil_domates, olay_bus=bus)
    sensor = SensorOkuma(
        sera_id="s1", T=profil_domates.max_T + 2,
        H=72.0, co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    sm.guncelle(sensor)

    assert len(alınan_olaylar) >= 1
    assert alınan_olaylar[0]["sera_id"] == "s1"
    assert "yeni" in alınan_olaylar[0]


def test_ayni_durum_olay_yayinlamaz(profil_domates):
    """Durum değişmezse olay yayınlanmamalı."""
    bus = EventBus()
    alınan_olaylar = []
    bus.abone_ol(OlayTur.DURUM_DEGISTI, lambda v: alınan_olaylar.append(v))

    sm = SeraStateMachine("s1", profil_domates, olay_bus=bus)
    sensor = SensorOkuma(
        sera_id="s1", T=23.0, H=72.0,
        co2=950, isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )
    sm.guncelle(sensor)   # NORMAL
    olaylar_sonra_ilk = len(alınan_olaylar)
    sm.guncelle(sensor)   # Hâlâ NORMAL
    assert len(alınan_olaylar) == olaylar_sonra_ilk
