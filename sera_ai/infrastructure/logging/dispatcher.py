"""
Log Dispatcher — EventBus → Log Yazıcılar

EventBus olaylarını dinler, yapılandırılmış log kaydına dönüştürür,
tüm aktif log yazıcılara iletir.

Neden bu katman?
  KontrolMotoru, state machine — hiçbiri "loki'ye yaz" bilmez.
  EventBus'a olay yayınlarlar → dispatcher dinler → yazar.
  Log hedefi değişince (dosya → Loki → her ikisi) sadece bu değişir.

Olay → seviye eşlemesi:
  SENSOR_OKUMA      → DEBUG  (yüksek frekanslı, verbose)
  DURUM_DEGISTI     → INFO / UYARI (duruma göre)
  KOMUT_GONDERILDI  → INFO
  CB_ACILDI         → HATA
  CB_KAPANDI        → INFO
  SISTEM_HATASI     → HATA
"""
from __future__ import annotations

from sera_ai.application.event_bus import EventBus, OlayTur
from .base import LogKayit, LogSeviye, LogYaziciBase


# Durum adı → log seviyesi
_DURUM_SEVIYE: dict[str, LogSeviye] = {
    "NORMAL":      LogSeviye.INFO,
    "BAKIM":       LogSeviye.INFO,
    "BEKLEME":     LogSeviye.INFO,
    "UYARI":       LogSeviye.UYARI,
    "ALARM":       LogSeviye.HATA,
    "ACIL_DURDUR": LogSeviye.KRITIK,
}


class LogDispatcher:
    """
    EventBus → log yazıcılar köprüsü.

    Kullanım:
        dispatcher = LogDispatcher(
            yazicilar=[JSONLLogger("sera.jsonl"), MockLogger()],
            olay_bus=bus,
        )
        dispatcher.baslat()
        # Artık tüm EventBus olayları log'a düşer
        dispatcher.durdur()
    """

    def __init__(
        self,
        yazicilar: list[LogYaziciBase],
        olay_bus:  EventBus,
        sensor_log_aktif: bool = False,  # SENSOR_OKUMA çok sık → default kapalı
    ) -> None:
        self._yazicilar        = yazicilar
        self._olay_bus         = olay_bus
        self._sensor_log_aktif = sensor_log_aktif
        self._aktif            = False

    def baslat(self) -> None:
        """EventBus'a abone ol."""
        if self._sensor_log_aktif:
            self._olay_bus.abone_ol(OlayTur.SENSOR_OKUMA, self._sensor_okuma)
        self._olay_bus.abone_ol(OlayTur.DURUM_DEGISTI,    self._durum_degisti)
        self._olay_bus.abone_ol(OlayTur.KOMUT_GONDERILDI, self._komut_gonderildi)
        self._olay_bus.abone_ol(OlayTur.CB_ACILDI,        self._cb_acildi)
        self._olay_bus.abone_ol(OlayTur.CB_KAPANDI,       self._cb_kapandi)
        self._olay_bus.abone_ol(OlayTur.SISTEM_HATASI,    self._sistem_hatasi)
        self._aktif = True

    def durdur(self) -> None:
        """Yazıcıları kapat (buffer flush)."""
        self._aktif = False
        for w in self._yazicilar:
            try:
                w.kapat()
            except Exception:
                pass

    def manuel_yaz(self, kayit: LogKayit) -> None:
        """Dışarıdan doğrudan log kaydı eklemek için (örn. startup mesajı)."""
        self._ilet(kayit)

    # ── EventBus callback'leri ─────────────────────────────────

    def _sensor_okuma(self, veri: dict) -> None:
        self._ilet(LogKayit(
            seviye=LogSeviye.DEBUG,
            olay="SENSOR_OKUMA",
            sera_id=veri.get("sera_id", ""),
            veri={k: v for k, v in veri.items() if k != "sera_id"},
        ))

    def _durum_degisti(self, veri: dict) -> None:
        yeni = veri.get("yeni", "")
        seviye = _DURUM_SEVIYE.get(yeni, LogSeviye.INFO)
        self._ilet(LogKayit(
            seviye=seviye,
            olay="DURUM_DEGISTI",
            sera_id=veri.get("sera_id", ""),
            veri={"eski": veri.get("eski"), "yeni": yeni},
        ))

    def _komut_gonderildi(self, veri: dict) -> None:
        self._ilet(LogKayit(
            seviye=LogSeviye.INFO,
            olay="KOMUT_GONDERILDI",
            sera_id=veri.get("sera_id", ""),
            veri={"komut": veri.get("komut"), "basarili": veri.get("basarili")},
        ))

    def _cb_acildi(self, veri: dict) -> None:
        self._ilet(LogKayit(
            seviye=LogSeviye.HATA,
            olay="CB_ACILDI",
            sera_id=veri.get("sera_id", ""),
            veri=veri,
        ))

    def _cb_kapandi(self, veri: dict) -> None:
        self._ilet(LogKayit(
            seviye=LogSeviye.INFO,
            olay="CB_KAPANDI",
            sera_id=veri.get("sera_id", ""),
            veri=veri,
        ))

    def _sistem_hatasi(self, veri: dict) -> None:
        self._ilet(LogKayit(
            seviye=LogSeviye.HATA,
            olay="SISTEM_HATASI",
            sera_id=veri.get("sera_id", ""),
            veri={"hata": veri.get("hata"), "komut": veri.get("komut")},
        ))

    # ── İç yardımcı ───────────────────────────────────────────

    def _ilet(self, kayit: LogKayit) -> None:
        for yazici in self._yazicilar:
            try:
                yazici.yaz(kayit)
            except Exception as e:
                print(f"[LogDispatcher] Yazıcı hatası: {e}")
