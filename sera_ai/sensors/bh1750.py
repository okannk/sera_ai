"""
BH1750 — Işık Yoğunluğu Sensörü (I2C)

Donanım: ROHM BH1750FVI
İletişim: I2C (Fast Mode 400kHz destekler)
Adrés: 0x23 (ADDR pin LOW), 0x5C (ADDR pin HIGH)
Güç: 3.3V – 5V

Doğruluk: ±20%
Aralık: 1–65535 lux (yüksek çözünürlük modu: 0.5 lux hassasiyet)
Çözünürlük: 1 lux (varsayılan), 0.5 lux (yüksek çözünürlük)

RPi bağlantısı:
  SDA → GPIO 2 (pin 3)   [SHT31 ile aynı bus paylaşılabilir]
  SCL → GPIO 3 (pin 5)
  VCC → 3.3V
  GND → GND
  ADDR → GND (0x23 adres için)

Gereksinim: pip install smbus2
"""
from __future__ import annotations

import time

from .base import SensorBase

_ADRES_VARSAYILAN = 0x23

# Komutlar
_CMD_POWER_ON        = 0x01
_CMD_RESET           = 0x07
_CMD_CONT_H_RES      = 0x10   # Sürekli yüksek çözünürlük (1 lux, ~120ms)
_CMD_ONCE_H_RES      = 0x20   # Tek ölçüm yüksek çözünürlük
_OLCUM_SURESI_MS     = 0.180  # 120ms + güvenlik marjı


class BH1750Sensor(SensorBase):
    """
    BH1750 ışık yoğunluğu sensörü — I2C (smbus2).

    Tek ölçüm modunda çalışır — her oku() tam döngü yapar.
    """

    def __init__(self, adres: int = _ADRES_VARSAYILAN, bus_no: int = 1) -> None:
        self._adres  = adres
        self._bus_no = bus_no
        self._bus    = None

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset({"isik"})

    def baglan(self) -> bool:
        try:
            import smbus2
            self._bus = smbus2.SMBus(self._bus_no)
            self._bus.write_byte(self._adres, _CMD_POWER_ON)
            time.sleep(0.01)
            self._bus.write_byte(self._adres, _CMD_RESET)
            time.sleep(0.01)
            return True
        except ImportError:
            print("[BH1750] smbus2 kurulu değil: pip install smbus2")
            return False
        except Exception as e:
            print(f"[BH1750:0x{self._adres:02X}] Başlatma hatası: {e}")
            return False

    def oku(self) -> dict:
        if self._bus is None:
            raise IOError("[BH1750] baglan() çağrılmadı")

        try:
            # Tek ölçüm başlat
            self._bus.write_byte(self._adres, _CMD_ONCE_H_RES)
            time.sleep(_OLCUM_SURESI_MS)

            # 2 byte oku
            ham = self._bus.read_i2c_block_data(self._adres, 0x00, 2)
        except Exception as e:
            raise IOError(f"[BH1750:0x{self._adres:02X}] I2C okuma hatası: {e}") from e

        ham_deger = (ham[0] << 8) | ham[1]
        # BH1750 dönüşüm: ham / 1.2 = lux
        lux = int(ham_deger / 1.2)
        return {"isik": lux}

    def kapat(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
