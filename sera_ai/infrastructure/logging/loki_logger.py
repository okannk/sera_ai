"""
Loki HTTP Push API İstemcisi

Grafana Loki'ye doğrudan log gönderir — Promtail gerekmez.

Loki push format:
  POST /loki/api/v1/push
  Content-Type: application/json
  {
    "streams": [{
      "stream": {"job": "sera_ai", "sera_id": "s1", "seviye": "ALARM"},
      "values": [["<timestamp_ns>", "<log_line>"]]
    }]
  }

Batch özelliği:
  Her yaz() çağrısında HTTP istek yapmak yerine buffer'da biriktirir.
  flush() veya buffer_boyut dolunca toplu gönderir.
  Bu şekilde Loki'ye ağ yükü azalır.

Kurulum:
    pip install httpx
"""
from __future__ import annotations

import json
import threading
import time
from typing import Optional

from .base import LogKayit, LogYaziciBase


class LokiLogger(LogYaziciBase):
    """
    Loki HTTP push API ile log gönderir.

    httpx kurulu değilse sessizce devre dışı kalır.
    Loki erişilemezse buffer drop edilir — kritik sistemlerin log için
    bloke olmaması sağlanır.

    Kullanım:
        logger = LokiLogger(
            loki_url="http://localhost:3100",
            is_etiketi="sera_ai",
            buffer_boyut=50,
        )
        logger.yaz(kayit)
        logger.flush()  # Manuel flush
    """

    TIMEOUT_SN = 3.0

    def __init__(
        self,
        loki_url:    str = "http://localhost:3100",
        is_etiketi:  str = "sera_ai",
        buffer_boyut: int = 50,
        aktif:       bool = True,
    ) -> None:
        self._url         = loki_url.rstrip("/") + "/loki/api/v1/push"
        self._is_etiketi  = is_etiketi
        self._buffer_boyut = buffer_boyut
        self._aktif       = aktif
        self._buffer: list[LogKayit] = []
        self._lock = threading.Lock()

    def yaz(self, kayit: LogKayit) -> None:
        if not self._aktif:
            return
        with self._lock:
            self._buffer.append(kayit)
            if len(self._buffer) >= self._buffer_boyut:
                self._flush_locked()

    def flush(self) -> bool:
        """Buffer'daki tüm kayıtları Loki'ye gönder. Başarıda True döner."""
        with self._lock:
            return self._flush_locked()

    def kapat(self) -> None:
        self.flush()

    def buffer_boyutu(self) -> int:
        """Bekleyen kayıt sayısı (test için)."""
        with self._lock:
            return len(self._buffer)

    # ── İç yardımcılar ────────────────────────────────────────

    def _flush_locked(self) -> bool:
        """Lock tutuluyken çağrılır."""
        if not self._buffer:
            return True

        try:
            import httpx
        except ImportError:
            self._buffer.clear()
            return False

        payload = self._payload_olustur(self._buffer)
        try:
            yanit = httpx.post(
                self._url,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=self.TIMEOUT_SN,
            )
            if yanit.status_code in (200, 204):
                self._buffer.clear()
                return True
            print(f"[Loki] Push hatası: {yanit.status_code} — {yanit.text[:100]}")
            self._buffer.clear()  # Başarısız buffer'ı da temizle
            return False
        except Exception as e:
            print(f"[Loki] Bağlantı hatası: {e}")
            self._buffer.clear()
            return False

    def _payload_olustur(self, kayitlar: list[LogKayit]) -> dict:
        """
        Loki push formatı:
        Kayıtları seviye+sera_id etiket kombinasyonuna göre stream'lere gruplar.
        """
        streamler: dict[tuple, list] = {}

        for kayit in kayitlar:
            anahtar = (kayit.seviye.value, kayit.sera_id)
            if anahtar not in streamler:
                streamler[anahtar] = []
            # Loki timestamp: nanosecond string
            ts_ns = str(int(kayit.zaman.timestamp() * 1e9))
            satir = json.dumps(kayit.to_dict(), ensure_ascii=False)
            streamler[anahtar].append([ts_ns, satir])

        return {
            "streams": [
                {
                    "stream": {
                        "job":     self._is_etiketi,
                        "seviye":  seviye,
                        "sera_id": sera_id or "sistem",
                    },
                    "values": degerler,
                }
                for (seviye, sera_id), degerler in streamler.items()
            ]
        }
