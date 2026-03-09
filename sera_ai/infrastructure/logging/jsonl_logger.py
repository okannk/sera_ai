"""
JSONL Dosya Logger — Promtail / Loki Uyumlu

Her log satırı bir JSON nesnesi → Grafana Loki Promtail bu formatı okur.

Özellikler:
  - Thread-safe: threading.Lock ile korunur
  - Dosya yoksa otomatik oluşturur
  - Encoding: UTF-8
  - Her satır: {"ts": "...", "seviye": "INFO", "olay": "...", ...}

Promtail ile kullanım:
  scrape_configs:
    - job_name: sera_ai
      static_configs:
        - targets: [localhost]
          labels:
            job: sera_ai
            __path__: /var/log/sera_system.jsonl
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .base import LogKayit, LogSeviye, LogYaziciBase


class JSONLLogger(LogYaziciBase):
    """
    JSONL formatında dosyaya yazar.

    Kullanım:
        logger = JSONLLogger("sera_system.jsonl")
        logger.yaz(LogKayit(LogSeviye.INFO, "DURUM_DEGISTI", {"yeni": "ALARM"}))
    """

    def __init__(self, dosya_yolu: str = "sera_system.jsonl") -> None:
        self._yol  = Path(dosya_yolu)
        self._lock = threading.Lock()
        # Dizin yoksa oluştur
        self._yol.parent.mkdir(parents=True, exist_ok=True)

    def yaz(self, kayit: LogKayit) -> None:
        satir = json.dumps(kayit.to_dict(), ensure_ascii=False)
        try:
            with self._lock:
                with open(self._yol, "a", encoding="utf-8") as f:
                    f.write(satir + "\n")
        except Exception as e:
            # Log hatası sistemi durdurmamalı
            print(f"[JSONLLogger] Yazma hatası: {e}")

    def satirlari_oku(self) -> list[dict]:
        """Test ve debug için tüm kayıtları döner."""
        if not self._yol.exists():
            return []
        kayitlar = []
        with self._lock:
            with open(self._yol, encoding="utf-8") as f:
                for satir in f:
                    satir = satir.strip()
                    if satir:
                        try:
                            kayitlar.append(json.loads(satir))
                        except json.JSONDecodeError:
                            pass
        return kayitlar

    def temizle(self) -> None:
        """Test teardown — dosyayı sıfırla."""
        with self._lock:
            if self._yol.exists():
                self._yol.unlink()

    @property
    def dosya_yolu(self) -> str:
        return str(self._yol)
