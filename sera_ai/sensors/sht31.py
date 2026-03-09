"""
SHT31 — Sıcaklık / Nem Sensörü (I2C)

Donanım: Sensirion SHT31-D
İletişim: I2C
Varsayılan adres: 0x44 (ADDR pin GND), 0x45 (ADDR pin VCC)
Güç: 3.3V / 5V toleranslı

Doğruluk: ±0.3°C, ±2% RH
Aralık: -40–125°C, 0–100% RH

RPi bağlantısı:
  SDA → GPIO 2 (pin 3)
  SCL → GPIO 3 (pin 5)
  VCC → 3.3V (pin 1)
  GND → GND (pin 6)

ESP32-S3 bağlantısı:
  SDA → GPIO 8 (varsayılan I2C)
  SCL → GPIO 9

Gereksinim: pip install smbus2
"""
from __future__ import annotations

import struct
import time

from .base import SensorBase

_ADRES_VARSAYILAN = 0x44

# SHT31 komutları
_CMD_TEK_YUKSEK  = [0x24, 0x00]   # Tek ölçüm, yüksek tekrarlanabilirlik
_CMD_SOFT_RESET  = [0x30, 0xA2]


class SHT31Sensor(SensorBase):
    """
    SHT31-D sıcaklık/nem sensörü — I2C (smbus2).

    Tek ölçüm modunda çalışır: her oku() tam bir ölçüm döngüsü yapar.
    Sürekli mod yerine tek ölçüm tercih edilir — ESP32'de uyku modunu destekler.
    """

    def __init__(self, adres: int = _ADRES_VARSAYILAN, bus_no: int = 1) -> None:
        self._adres  = adres
        self._bus_no = bus_no
        self._bus    = None

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset({"T", "H"})

    def baglan(self) -> bool:
        try:
            import smbus2
            self._bus = smbus2.SMBus(self._bus_no)
            # Soft reset — önceki hatalı durumu temizle
            self._bus.write_i2c_block_data(self._adres, _CMD_SOFT_RESET[0], [_CMD_SOFT_RESET[1]])
            time.sleep(0.02)   # Reset süresi: 1.5ms min, 20ms ile güvenli
            return True
        except ImportError:
            print("[SHT31] smbus2 kurulu değil: pip install smbus2")
            return False
        except Exception as e:
            print(f"[SHT31:0x{self._adres:02X}] Başlatma hatası: {e}")
            return False

    def oku(self) -> dict:
        if self._bus is None:
            raise IOError("[SHT31] baglan() çağrılmadı")

        try:
            # Ölçüm başlat
            self._bus.write_i2c_block_data(
                self._adres, _CMD_TEK_YUKSEK[0], [_CMD_TEK_YUKSEK[1]]
            )
            time.sleep(0.02)   # Ölçüm süresi: ~15ms

            # 6 byte oku: T_MSB T_LSB T_CRC H_MSB H_LSB H_CRC
            ham = self._bus.read_i2c_block_data(self._adres, 0x00, 6)
        except Exception as e:
            raise IOError(f"[SHT31:0x{self._adres:02X}] I2C okuma hatası: {e}") from e

        self._crc_kontrol(ham[:2], ham[2])
        self._crc_kontrol(ham[3:5], ham[5])

        T_ham = (ham[0] << 8) | ham[1]
        H_ham = (ham[3] << 8) | ham[4]

        T = -45.0 + 175.0 * T_ham / 65535.0
        H = 100.0 * H_ham / 65535.0

        return {"T": round(T, 2), "H": round(H, 1)}

    def kapat(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None

    @staticmethod
    def _crc_kontrol(veri: list[int], beklenen: int) -> None:
        """SHT31 CRC-8 doğrulama (polinom: 0x31)."""
        crc = 0xFF
        for bayt in veri:
            crc ^= bayt
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        if crc != beklenen:
            raise IOError(f"[SHT31] CRC hatası: beklenen=0x{beklenen:02X} hesaplanan=0x{crc:02X}")
