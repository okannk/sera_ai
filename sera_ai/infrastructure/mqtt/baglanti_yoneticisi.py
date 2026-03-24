"""
Bağlantı Yöneticisi — ESP32 Saha Node Bağlantı Takibi

Her cihaz periyodik kalp atışı (heartbeat) gönderir.
Bu sınıf son kalp atışına bakarak bağlantı durumunu hesaplar.

Durum eşikleri:
  CEVRIMICI  → son kalp atışı < 30 saniye önce
  GECIKMELI  → 30–90 saniye önce
  KOPUK      → 90 saniyeden eski veya hiç alınmamış

Yeniden bağlantı backoff: 5 → 15 → 30 → 60 saniye
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

# Bağlantı durum eşikleri (saniye)
_CEVRIMICI_ESIK  = 30
_GECIKMELI_ESIK  = 90
_KONTROL_INTERVAL = 10  # Her 10 saniyede bir durum güncellemesi

# Yeniden bağlantı backoff dizisi
_BACKOFF_SN = [5, 15, 30, 60]


class BaglantiYoneticisi:
    """
    ESP32 cihaz bağlantı durumlarını takip eder.

    MQTT on_connect/on_disconnect callback'lerini ve kalp atışı
    mesajlarını dinleyerek anlık durum tablosu tutar.

    Kullanım:
        ym = BaglantiYoneticisi()
        ym.baslat()
        ym.kalp_atisi_al("SERA-IST01-001")
        durum = ym.durum("SERA-IST01-001")  # "CEVRIMICI"
    """

    def __init__(self) -> None:
        # cihaz_id → son kalp atışı zamanı
        self._son_kalp: dict[str, datetime] = {}
        # cihaz_id → yeniden bağlanma denemesi sayısı
        self._deneme: dict[str, int] = {}
        self._lock     = threading.Lock()
        self._calisiyor = False
        self._thread: Optional[threading.Thread] = None

    def baslat(self) -> None:
        """Bağlantı denetim döngüsünü başlat (daemon thread)."""
        self._calisiyor = True
        self._thread = threading.Thread(
            target=self._denetim_dongusu,
            name="BaglantiDenetim",
            daemon=True,
        )
        self._thread.start()

    def durdur(self) -> None:
        """Denetim döngüsünü durdur."""
        self._calisiyor = False
        if self._thread:
            self._thread.join(timeout=5)

    def kalp_atisi_al(self, cihaz_id: str, zaman: Optional[datetime] = None) -> None:
        """
        Cihazdan kalp atışı alındığında çağır.
        Bağlantı durumunu CEVRIMICI'ya çeker, backoff sayacını sıfırlar.
        """
        with self._lock:
            self._son_kalp[cihaz_id] = zaman or datetime.now()
            self._deneme[cihaz_id]   = 0

    def kopuk_isle(self, cihaz_id: str) -> None:
        """
        Cihaz bağlantısı koptuğunda çağır.
        Backoff sayacını artırır.
        """
        with self._lock:
            sayac = self._deneme.get(cihaz_id, 0)
            self._deneme[cihaz_id] = min(sayac + 1, len(_BACKOFF_SN) - 1)

    def durum(self, cihaz_id: str) -> str:
        """Anlık bağlantı durumu: CEVRIMICI | GECIKMELI | KOPUK | BILINMIYOR"""
        with self._lock:
            son = self._son_kalp.get(cihaz_id)
        if son is None:
            return "BILINMIYOR"
        delta = (datetime.now() - son).total_seconds()
        if delta < _CEVRIMICI_ESIK:
            return "CEVRIMICI"
        if delta < _GECIKMELI_ESIK:
            return "GECIKMELI"
        return "KOPUK"

    def sonraki_deneme_sn(self, cihaz_id: str) -> int:
        """Bir sonraki yeniden bağlantı denemesine kadar beklenecek süre (saniye)."""
        with self._lock:
            i = self._deneme.get(cihaz_id, 0)
        return _BACKOFF_SN[min(i, len(_BACKOFF_SN) - 1)]

    def tum_durumlar(self) -> dict[str, str]:
        """Tüm takip edilen cihazların durum özeti."""
        with self._lock:
            ids = list(self._son_kalp.keys())
        return {cid: self.durum(cid) for cid in ids}

    # ── İç döngü ──────────────────────────────────────────────

    def _denetim_dongusu(self) -> None:
        """
        Periyodik denetim: KOPUK cihazları logla (ileride yeniden bağlanma tetikler).
        """
        while self._calisiyor:
            kopuklar = [
                cid for cid in list(self._son_kalp.keys())
                if self.durum(cid) == "KOPUK"
            ]
            if kopuklar:
                for cid in kopuklar:
                    bekleme = self.sonraki_deneme_sn(cid)
                    # Üretimde burada yeniden bağlantı isteği tetiklenebilir
                    _ = bekleme  # şimdilik kullanılmıyor
            time.sleep(_KONTROL_INTERVAL)
