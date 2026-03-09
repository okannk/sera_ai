"""
Log Yazıcı Soyut Temel Sınıfı

Neden ABC?
  jsonl_logger.py  → dosyaya yazar, Promtail okur → Loki
  loki_logger.py   → doğrudan Loki HTTP push API
  mock.py          → bellekte tutar, test için

  Dispatcher hangisini kullandığını bilmez.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LogSeviye(Enum):
    DEBUG = "DEBUG"
    INFO  = "INFO"
    UYARI = "UYARI"
    HATA  = "HATA"
    KRITIK = "KRITIK"


@dataclass
class LogKayit:
    """Kanaldan bağımsız log kaydı."""
    seviye:  LogSeviye
    olay:    str                    # OlayTur.name veya serbest string
    veri:    dict = field(default_factory=dict)
    sera_id: str  = ""
    zaman:   datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "ts":      self.zaman.isoformat(),
            "seviye":  self.seviye.value,
            "olay":    self.olay,
            "sera_id": self.sera_id,
            **self.veri,
        }


class LogYaziciBase(ABC):
    """
    Log yazıcı arayüzü.

    Sözleşme:
      - yaz() → başarısız olursa sessizce geçer (istisna fırlatmaz)
      - Çağıran thread'den güvenle çağrılabilir
    """

    @abstractmethod
    def yaz(self, kayit: LogKayit) -> None:
        """Log kaydını hedefe ilet."""

    def kapat(self) -> None:
        """Kaynakları serbest bırak (buffer flush vb.). Opsiyonel."""
