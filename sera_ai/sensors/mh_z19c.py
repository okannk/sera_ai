"""
MH-Z19C — CO₂ Sensörü (UART / Kızılötesi Spektroskopi)

Donanım: Winsen MH-Z19C NDIR CO₂ sensörü
İletişim: UART (9600 baud, 8N1)
Güç: 5V (3.3V toleranslı TX/RX)
Ölçüm: 400–5000 ppm (varsayılan), 400–10000 ppm (geniş aralık modeli)

Doğruluk: ±(50ppm + 5% ölçüm değeri)
Isınma süresi: 3 dakika (ilk açılış)

RPi bağlantısı:
  TX (sensör) → RX (RPi GPIO 15, pin 10)
  RX (sensör) → TX (RPi GPIO 14, pin 8)
  VCC         → 5V (pin 2 veya 4)
  GND         → GND

ESP32-S3 bağlantısı:
  TX (sensör) → RX (GPIO 44 / UART0_RX)
  RX (sensör) → TX (GPIO 43 / UART0_TX)

RPi kurulum notu:
  /boot/config.txt → enable_uart=1
  /boot/cmdline.txt → console=serial0,115200 kaldır

Gereksinim: pip install pyserial
"""
from __future__ import annotations

import struct
import time

from .base import SensorBase

_BAUD_RATE   = 9600
_OKUMA_CMD   = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])
_TIMEOUT_SN  = 2.0


class MHZ19CSensor(SensorBase):
    """
    MH-Z19C CO₂ sensörü — UART (pyserial).

    ABC kalibrasyonu (ABC = Automatic Baseline Calibration):
      Varsayılan açık — 24 saatlik döngülerde taze hava (400ppm) varsayar.
      Kapalı ortamda devre dışı bırakılabilir (ABC kalibrasyon komutu ile).
    """

    def __init__(
        self,
        port: str = "/dev/ttyS0",
        baud: int = _BAUD_RATE,
        timeout_sn: float = _TIMEOUT_SN,
    ) -> None:
        self._port       = port
        self._baud       = baud
        self._timeout_sn = timeout_sn
        self._seri       = None

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset({"co2"})

    def baglan(self) -> bool:
        try:
            import serial
            self._seri = serial.Serial(
                self._port,
                baudrate=self._baud,
                timeout=self._timeout_sn,
            )
            return True
        except ImportError:
            print("[MH-Z19C] pyserial kurulu değil: pip install pyserial")
            return False
        except Exception as e:
            print(f"[MH-Z19C:{self._port}] Port açma hatası: {e}")
            return False

    def oku(self) -> dict:
        if self._seri is None or not self._seri.is_open:
            raise IOError(f"[MH-Z19C:{self._port}] baglan() çağrılmadı veya port kapalı")

        try:
            self._seri.write(_OKUMA_CMD)
            yanit = self._seri.read(9)
        except Exception as e:
            raise IOError(f"[MH-Z19C:{self._port}] UART okuma hatası: {e}") from e

        if len(yanit) != 9:
            raise IOError(
                f"[MH-Z19C:{self._port}] Eksik yanıt: {len(yanit)}/9 byte"
            )

        if yanit[0] != 0xFF or yanit[1] != 0x86:
            raise IOError(
                f"[MH-Z19C:{self._port}] Geçersiz yanıt başlığı: {yanit[:2].hex()}"
            )

        beklenen_crc = self._crc(yanit[1:8])
        if yanit[8] != beklenen_crc:
            raise IOError(
                f"[MH-Z19C:{self._port}] CRC hatası: "
                f"beklenen=0x{beklenen_crc:02X} gelen=0x{yanit[8]:02X}"
            )

        co2 = (yanit[2] << 8) | yanit[3]
        return {"co2": co2}

    def kapat(self) -> None:
        if self._seri and self._seri.is_open:
            self._seri.close()
            self._seri = None

    @staticmethod
    def _crc(veri: bytes) -> int:
        """MH-Z19 checksum: byte toplamının 256 modülü, tümleyen + 1."""
        return (~sum(veri) & 0xFF) + 1
