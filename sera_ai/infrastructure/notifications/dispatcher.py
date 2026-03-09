"""
Bildirim Dispatcher — EventBus → Kanallar

Neden bu katman?
  KontrolMotoru, state machine — hiçbiri "telegram'a mesaj gönder" bilmez.
  EventBus'a DURUM_DEGISTI / SISTEM_HATASI yayınlarlar.
  Dispatcher bunları dinler, BildirimKonfig'e göre mesaj oluşturur,
  aktif kanallara iletir.

Bastırma (rate limiting):
  Aynı sera için aynı öncelikteki mesaj tekrar göndermeden önce
  BildirimKonfig.bastirma_dk dakika beklenir.
  Kritik mesajlar (ACİL_DURDUR) bastırılmaz.

Durum → öncelik eşlemesi:
  NORMAL, BAKIM, BEKLEME → bildirim yok
  UYARI                  → BildirimOncelik.UYARI
  ALARM                  → BildirimOncelik.ALARM
  ACİL_DURDUR           → BildirimOncelik.KRITIK (bastırılmaz)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.domain.models import BildirimKonfig
from .base import Bildirim, BildirimKanalBase, BildirimOncelik


# State machine durum adı → bildirim önceliği
# None → bildirim gönderilmez
_DURUM_ONCELIK: dict[str, Optional[BildirimOncelik]] = {
    "NORMAL":      None,
    "BAKIM":       None,
    "BEKLEME":     None,
    "UYARI":       BildirimOncelik.UYARI,
    "ALARM":       BildirimOncelik.ALARM,
    "ACIL_DURDUR": BildirimOncelik.KRITIK,
}


class BildirimDispatcher:
    """
    EventBus olaylarını dinler → uygun kanallara bildirim gönderir.

    Kullanım:
        dispatcher = BildirimDispatcher(
            kanallar=[TelegramKanal(...), MockBildirimKanal()],
            konfig=sistem_konfig.bildirim,
            olay_bus=bus,
        )
        dispatcher.baslat()   # EventBus'a abone olur
        # ...
        dispatcher.durdur()   # Abonelikleri kaldırır
    """

    def __init__(
        self,
        kanallar: list[BildirimKanalBase],
        konfig:   BildirimKonfig,
        olay_bus: EventBus,
    ) -> None:
        self._kanallar  = kanallar
        self._konfig    = konfig
        self._olay_bus  = olay_bus
        self._aktif     = False

        # Bastırma takibi: (sera_id, öncelik) → son gönderim zamanı
        self._son_gonderim: dict[tuple[str, BildirimOncelik], datetime] = {}

        # İstatistik
        self.gonderilen_sayisi:  int = 0
        self.bastirilmis_sayisi: int = 0

    def baslat(self) -> None:
        """EventBus'a abone ol."""
        self._olay_bus.abone_ol(OlayTur.DURUM_DEGISTI, self._durum_degisti)
        self._olay_bus.abone_ol(OlayTur.SISTEM_HATASI, self._sistem_hatasi)
        self._olay_bus.abone_ol(OlayTur.CB_ACILDI,     self._cb_acildi)
        self._aktif = True

    def durdur(self) -> None:
        self._aktif = False

    def gunluk_rapor_gonder(self, ozet: dict) -> None:
        """
        Sabah raporu — dışarıdan (scheduler) çağrılır.
        ozet: {"toplam_sera": 3, "alarm_sayisi": 0, ...}
        """
        satirlar = [f"🌱 <b>Günlük Sera Raporu</b>"]
        for k, v in ozet.items():
            satirlar.append(f"• {k}: {v}")
        bildirim = Bildirim(
            baslik="Günlük Rapor",
            mesaj="\n".join(satirlar),
            oncelik=BildirimOncelik.BILGI,
        )
        self._ilet(bildirim)

    # ── EventBus callback'leri ─────────────────────────────────

    def _durum_degisti(self, veri: dict) -> None:
        yeni_durum = veri.get("yeni", "")
        sera_id    = veri.get("sera_id", "")
        eski_durum = veri.get("eski", "")

        oncelik = _DURUM_ONCELIK.get(yeni_durum)
        if oncelik is None:
            return

        baslik = f"Sera {sera_id}: {yeni_durum}"
        mesaj  = f"{eski_durum} → {yeni_durum}"

        bildirim = Bildirim(
            baslik=baslik,
            mesaj=mesaj,
            oncelik=oncelik,
            sera_id=sera_id,
        )
        self._ilet_bastirarak(bildirim)

    def _sistem_hatasi(self, veri: dict) -> None:
        sera_id = veri.get("sera_id", "")
        hata    = veri.get("hata", "Bilinmeyen hata")
        bildirim = Bildirim(
            baslik=f"Sistem Hatası — Sera {sera_id}",
            mesaj=hata,
            oncelik=BildirimOncelik.ALARM,
            sera_id=sera_id,
        )
        self._ilet_bastirarak(bildirim)

    def _cb_acildi(self, veri: dict) -> None:
        sera_id = veri.get("sera_id", "")
        bildirim = Bildirim(
            baslik=f"Circuit Breaker Açıldı — Sera {sera_id}",
            mesaj="Bağlantı hata eşiğini aştı. Sistem güvenli moda geçti.",
            oncelik=BildirimOncelik.KRITIK,
            sera_id=sera_id,
        )
        # CB açılması kritik → bastırılmaz
        self._ilet(bildirim)

    # ── İç yardımcılar ────────────────────────────────────────

    def _ilet_bastirarak(self, bildirim: Bildirim) -> None:
        """Kritik dışı mesajları bastırma kuralına göre ilet."""
        if bildirim.oncelik == BildirimOncelik.KRITIK:
            self._ilet(bildirim)
            return

        anahtar = (bildirim.sera_id, bildirim.oncelik)
        son = self._son_gonderim.get(anahtar)
        if son is not None:
            gecen = datetime.now() - son
            sinir = timedelta(minutes=self._konfig.bastirma_dk)
            if gecen < sinir:
                self.bastirilmis_sayisi += 1
                return

        self._ilet(bildirim)
        self._son_gonderim[anahtar] = datetime.now()

    def _ilet(self, bildirim: Bildirim) -> None:
        """Aktif tüm kanallara gönder."""
        for kanal in self._kanallar:
            if kanal.aktif_mi:
                try:
                    basarili = kanal.gonder(bildirim)
                    if basarili:
                        self.gonderilen_sayisi += 1
                except Exception as e:
                    print(f"[Dispatcher] {kanal.kanal_adi} hatası: {e}")
