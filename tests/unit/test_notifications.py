"""
Bildirim Altyapısı Testleri

Kapsam:
  - MockBildirimKanal yaşam döngüsü
  - BildirimDispatcher EventBus entegrasyonu
  - Durum → öncelik eşlemesi
  - Bastırma (rate limiting) mantığı
  - Kritik mesajlar bastırılmaz
  - CB açılma bildirimi
  - Sistem hatası bildirimi
  - Pasif kanal mesaj almaz
  - TelegramKanal aktiflik kontrolü (token olmadan)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.domain.models import BildirimKonfig
from sera_ai.infrastructure.notifications import (
    Bildirim,
    BildirimDispatcher,
    BildirimOncelik,
    MockBildirimKanal,
    TelegramKanal,
)


# ── Fixture'lar ───────────────────────────────────────────────────

@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def konfig() -> BildirimKonfig:
    return BildirimKonfig(bastirma_dk=10)


@pytest.fixture
def kanal() -> MockBildirimKanal:
    return MockBildirimKanal()


@pytest.fixture
def dispatcher(kanal, konfig, bus) -> BildirimDispatcher:
    d = BildirimDispatcher([kanal], konfig, bus)
    d.baslat()
    return d


# ── MockBildirimKanal ─────────────────────────────────────────────

class TestMockBildirimKanal:

    def test_her_zaman_aktif(self, kanal):
        assert kanal.aktif_mi

    def test_gonder_kaydeder(self, kanal):
        b = Bildirim("Test", "mesaj", BildirimOncelik.BILGI)
        assert kanal.gonder(b)
        assert len(kanal.gonderilen) == 1
        assert kanal.gonderilen[0].baslik == "Test"

    def test_temizle(self, kanal):
        kanal.gonder(Bildirim("T", "m", BildirimOncelik.BILGI))
        kanal.temizle()
        assert kanal.gonderilen == []
        assert kanal.hata_sayisi == 0

    def test_hata_orani_1_hic_gondermez(self):
        kanal = MockBildirimKanal(hata_orani=1.0)
        assert not kanal.gonder(Bildirim("T", "m", BildirimOncelik.BILGI))
        assert kanal.hata_sayisi == 1
        assert kanal.gonderilen == []


# ── BildirimDispatcher — Temel ────────────────────────────────────

class TestBildirimDispatcher:

    def test_baslat_abone_olur(self, bus, dispatcher):
        # DURUM_DEGISTI, SISTEM_HATASI, CB_ACILDI
        assert bus.abone_sayisi(OlayTur.DURUM_DEGISTI) >= 1
        assert bus.abone_sayisi(OlayTur.SISTEM_HATASI) >= 1
        assert bus.abone_sayisi(OlayTur.CB_ACILDI) >= 1

    def test_normal_durum_bildirim_yok(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "BEKLEME", "yeni": "NORMAL"
        })
        assert kanal.gonderilen == []

    def test_uyari_durumu_bildirim_gonderir(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "UYARI"
        })
        assert len(kanal.gonderilen) == 1
        assert kanal.gonderilen[0].oncelik == BildirimOncelik.UYARI
        assert kanal.gonderilen[0].sera_id == "s1"

    def test_alarm_durumu_alarm_onceligi(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "UYARI", "yeni": "ALARM"
        })
        assert kanal.gonderilen[0].oncelik == BildirimOncelik.ALARM

    def test_acil_durdur_kritik_oncelik(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "ALARM", "yeni": "ACIL_DURDUR"
        })
        assert kanal.gonderilen[0].oncelik == BildirimOncelik.KRITIK

    def test_sistem_hatasi_bildirim_gonderir(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.SISTEM_HATASI, {
            "sera_id": "s1", "hata": "Sensör timeout"
        })
        assert len(kanal.gonderilen) == 1
        assert "s1" in kanal.gonderilen[0].baslik

    def test_cb_acildi_bildirim_gonderir(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s2"})
        assert len(kanal.gonderilen) == 1
        assert kanal.gonderilen[0].oncelik == BildirimOncelik.KRITIK

    def test_gonderilen_sayisi_artar(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "ALARM"
        })
        assert dispatcher.gonderilen_sayisi == 1


# ── Bastırma (Rate Limiting) ──────────────────────────────────────

class TestBastirma:

    def test_ayni_mesaj_ikinci_kez_bastirilir(self, bus, kanal, konfig, dispatcher):
        olay = {"sera_id": "s1", "eski": "NORMAL", "yeni": "UYARI"}
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)  # bastırılmalı
        assert len(kanal.gonderilen) == 1
        assert dispatcher.bastirilmis_sayisi == 1

    def test_farkli_sera_ayri_takip(self, bus, kanal, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "UYARI"
        })
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s2", "eski": "NORMAL", "yeni": "UYARI"
        })
        # Farklı seralar → ikisi de gitmeli
        assert len(kanal.gonderilen) == 2
        assert dispatcher.bastirilmis_sayisi == 0

    def test_kritik_bastirma_uygulanmaz(self, bus, kanal, dispatcher):
        """ACİL_DURDUR hiç bastırılmaz."""
        olay = {"sera_id": "s1", "eski": "ALARM", "yeni": "ACIL_DURDUR"}
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        assert len(kanal.gonderilen) == 3
        assert dispatcher.bastirilmis_sayisi == 0

    def test_bastirma_suresi_dolunca_tekrar_gonderir(self, bus, kanal, konfig):
        """bastirma_dk=0 → her seferinde gönderir."""
        konfig_sifir = BildirimKonfig(bastirma_dk=0)
        d = BildirimDispatcher([kanal], konfig_sifir, bus)
        d.baslat()

        olay = {"sera_id": "s1", "eski": "NORMAL", "yeni": "UYARI"}
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        bus.yayinla(OlayTur.DURUM_DEGISTI, olay)
        assert len(kanal.gonderilen) == 2

    def test_cb_acildi_bastirma_uygulanmaz(self, bus, kanal, dispatcher):
        """CB açılması her seferinde iletilir."""
        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s1"})
        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s1"})
        assert len(kanal.gonderilen) == 2


# ── Pasif Kanal ───────────────────────────────────────────────────

class TestPasifKanal:

    def test_pasif_kanal_mesaj_almaz(self, bus, konfig):
        class PasifKanal(MockBildirimKanal):
            @property
            def aktif_mi(self) -> bool:
                return False

        pasif = PasifKanal()
        d = BildirimDispatcher([pasif], konfig, bus)
        d.baslat()

        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "ALARM"
        })
        assert pasif.gonderilen == []
        assert d.gonderilen_sayisi == 0

    def test_karisik_kanallar_sadece_aktif_gonderir(self, bus, konfig):
        aktif   = MockBildirimKanal()
        class PasifKanal(MockBildirimKanal):
            @property
            def aktif_mi(self): return False
        pasif = PasifKanal()

        d = BildirimDispatcher([aktif, pasif], konfig, bus)
        d.baslat()

        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "ALARM"
        })
        assert len(aktif.gonderilen) == 1
        assert len(pasif.gonderilen) == 0


# ── Günlük Rapor ──────────────────────────────────────────────────

class TestGunlukRapor:

    def test_gunluk_rapor_bilgi_onceligi(self, dispatcher, kanal):
        dispatcher.gunluk_rapor_gonder({"toplam_sera": 3, "alarm_sayisi": 0})
        assert len(kanal.gonderilen) == 1
        assert kanal.gonderilen[0].oncelik == BildirimOncelik.BILGI
        assert kanal.gonderilen[0].baslik == "Günlük Rapor"


# ── TelegramKanal Yapı Testleri ───────────────────────────────────

class TestTelegramKanalYapi:
    """Token olmadan sadece yapı/aktiflik testi."""

    def test_konfig_false_ise_aktif_degil(self):
        kanal = TelegramKanal(aktif=False)
        assert not kanal.aktif_mi

    def test_konfig_true_token_yok_aktif_degil(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        kanal = TelegramKanal(aktif=True)
        assert not kanal.aktif_mi

    def test_konfig_true_token_var_aktif(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100999")
        kanal = TelegramKanal(aktif=True)
        assert kanal.aktif_mi

    def test_aktif_degil_gonder_false(self):
        kanal = TelegramKanal(aktif=False)
        assert not kanal.gonder(Bildirim("T", "m", BildirimOncelik.ALARM))

    def test_kanal_adi(self):
        assert TelegramKanal().kanal_adi == "Telegram"

    def test_abc_uyum(self):
        from sera_ai.infrastructure.notifications.base import BildirimKanalBase
        assert issubclass(TelegramKanal, BildirimKanalBase)
        assert issubclass(MockBildirimKanal, BildirimKanalBase)
