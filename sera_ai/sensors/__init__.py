"""
Sensör Soyutlama Katmanı

Kural: Yeni sensör eklemek = sadece bu dizine yeni dosya.
Başka hiçbir dosya değişmez.

Her sensör SensorBase'den türer ve oku() → dict döndürür.
SahaNode bu dict'leri birleştirerek SensorOkuma üretir.

Donanım bağımlılıkları (smbus2, serial, adafruit) lazy import edilir —
kurulu değilse ImportError yerine IOError döner.
"""
from .base import SensorBase
from .mock import MockSensor

__all__ = ["SensorBase", "MockSensor"]
