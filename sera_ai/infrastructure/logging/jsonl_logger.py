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

    def __init__(
        self,
        dosya_yolu:   str = "sera_system.jsonl",
        max_mb:       int = 10,
        yedek_sayisi: int = 3,
    ) -> None:
        self._yol          = Path(dosya_yolu)
        self._lock         = threading.Lock()
        self._max_boyut    = max_mb * 1024 * 1024 if max_mb > 0 else 0
        self._yedek_sayisi = yedek_sayisi
        self._yol.parent.mkdir(parents=True, exist_ok=True)

    def yaz(self, kayit: LogKayit) -> None:
        satir = json.dumps(kayit.to_dict(), ensure_ascii=False)
        try:
            with self._lock:
                self._rotate_eger_gerekli()
                with open(self._yol, "a", encoding="utf-8") as f:
                    f.write(satir + "\n")
        except Exception as e:
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

    def _rotate_eger_gerekli(self) -> None:
        """Lock alındıktan sonra çağrılmalı. Boyut aşımında rotate başlatır."""
        if not self._max_boyut:
            return
        if not self._yol.exists():
            return
        if self._yol.stat().st_size < self._max_boyut:
            return
        self._rotate()

    def _rotate(self) -> None:
        """
        Eski dosyaları öteleyerek yeni log için yer aç.

        sera_system.jsonl      → sera_system.1.jsonl
        sera_system.1.jsonl    → sera_system.2.jsonl
        sera_system.2.jsonl    → sera_system.3.jsonl  (yedek_sayisi=3)
        sera_system.3.jsonl    → silindi
        """
        parent = self._yol.parent
        stem   = self._yol.stem
        suffix = self._yol.suffix

        # En eski yedek silinir
        en_eski = parent / f"{stem}.{self._yedek_sayisi}{suffix}"
        if en_eski.exists():
            en_eski.unlink()

        # Yedekleri ötele (.2→.3, .1→.2)
        for i in range(self._yedek_sayisi - 1, 0, -1):
            src = parent / f"{stem}.{i}{suffix}"
            dst = parent / f"{stem}.{i + 1}{suffix}"
            if src.exists():
                src.rename(dst)

        # Aktif dosyayı .1'e taşı
        if self._yol.exists():
            self._yol.rename(parent / f"{stem}.1{suffix}")

    def temizle(self) -> None:
        """Test teardown — dosyayı sıfırla."""
        with self._lock:
            if self._yol.exists():
                self._yol.unlink()

    @property
    def dosya_yolu(self) -> str:
        return str(self._yol)
