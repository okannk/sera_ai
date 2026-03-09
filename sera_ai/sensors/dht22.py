"""
DHT22 — Sıcaklık / Nem Sensörü (1-Wire Digital)

Donanım: AM2302 / DHT22
İletişim: Tek kablo dijital protokol (GPIO)
Güç: 3.3V – 5V

Doğruluk: ±0.5°C, ±2% RH  (SHT31'den düşük)
Aralık: -40–80°C, 0–100% RH
Örnekleme: En az 2 saniyede bir (firmware kısıtı)

UYARI: Bu eski donanım fallback'idir.
Yeni kurulumlar için SHT31 kullanın — daha doğru, I2C, CRC korumalı.

RPi bağlantısı:
  DATA → GPIO 4 (pin 7)  [10kΩ pull-up direnci VCC'ye]
  VCC  → 3.3V veya 5V
  GND  → GND

Gereksinim: pip install adafruit-circuitpython-dht RPi.GPIO
"""
from __future__ import annotations

import time

from .base import SensorBase


class DHT22Sensor(SensorBase):
    """
    DHT22 / AM2302 sıcaklık/nem sensörü.

    adafruit_dht kütüphanesini kullanır.
    Yavaş örnekleme (2s min) nedeniyle arka plan thread'de okunması önerilir.
    """

    def __init__(self, pin: int = 4) -> None:
        """
        Args:
            pin: BCM GPIO numarası (varsayılan: 4)
        """
        self._pin    = pin
        self._cihaz  = None

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset({"T", "H"})

    def baglan(self) -> bool:
        try:
            import adafruit_dht
            import board
            gpio_pin = getattr(board, f"D{self._pin}")
            self._cihaz = adafruit_dht.DHT22(gpio_pin, use_pulseio=False)
            return True
        except ImportError:
            print("[DHT22] adafruit-circuitpython-dht kurulu değil")
            return False
        except Exception as e:
            print(f"[DHT22:GPIO{self._pin}] Başlatma hatası: {e}")
            return False

    def oku(self) -> dict:
        if self._cihaz is None:
            raise IOError("[DHT22] baglan() çağrılmadı")

        # DHT22 zaman zaman okuma hatası verir — 3 deneme
        son_hata = None
        for _ in range(3):
            try:
                T = self._cihaz.temperature
                H = self._cihaz.humidity
                if T is not None and H is not None:
                    return {"T": round(float(T), 2), "H": round(float(H), 1)}
            except Exception as e:
                son_hata = e
                time.sleep(0.5)

        raise IOError(f"[DHT22:GPIO{self._pin}] 3 denemede okuma başarısız: {son_hata}")

    def kapat(self) -> None:
        if self._cihaz:
            try:
                self._cihaz.exit()
            except Exception:
                pass
            self._cihaz = None
