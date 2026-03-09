"""
Saha Node Soyutlama Katmanı — SAHA KATMANI

Her sera için tek bir donanım arabirimi.
Sistem geri kalanı (state machine, kontrol motoru, API) sadece
bu sınıfı görür — ESP32-S3 mi, STM32 mi bilmez.

config.yaml'da tek satır:
    saha_donanim: esp32_s3   →  ESP32S3Node devreye girer
    saha_donanim: mock       →  MockSahaNode devreye girer

Uygulanan sınıflar:
  - esp32_s3.py  → WiFi/MQTT üzerinden ESP32-S3 node
  - mock.py      → Test/demo, gerçek donanım gerektirmez

İleride eklenecekler:
  - stm32.py     → RS-485 üzerinden STM32 node
  - arduino.py   → USB Serial üzerinden Arduino Mega
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.models import Komut, SensorOkuma


class SahaNodeBase(ABC):
    """
    Tek bir sera için donanım soyutlama katmanı.

    Sözleşme:
      - baglan()       → bağlantı kur, True = başarılı
      - sensor_oku()   → SensorOkuma döner, başarısızsa IOError
      - komut_gonder() → True = onaylandı, IOError = iletişim hatası
      - kapat()        → kaynakları serbest bırak (finally bloğunda çağrılır)

    Implementasyon kuralı:
      Hiçbir iş mantığı (eşik, karar, log) burada olmaz.
      Sadece "donanımla konuş" sorumluluğu.
    """

    @abstractmethod
    def baglan(self) -> bool:
        """
        Donanıma bağlantı kur.
        Returns:
            True  → bağlantı başarılı
            False → bağlanamadı (uygulama devam edebilir, CB sayar)
        """
        ...

    @abstractmethod
    def sensor_oku(self, sera_id: str) -> "SensorOkuma":
        """
        Sensörden anlık okuma al.
        Args:
            sera_id: Hangi sera (MQTT topic routing için)
        Returns:
            SensorOkuma dataclass
        Raises:
            IOError: Donanım yanıt vermedi, timeout, bağlantı koptu
        """
        ...

    @abstractmethod
    def komut_gonder(self, komut: "Komut") -> bool:
        """
        Aktüatöre komut ilet.
        Args:
            komut: Komut enum değeri
        Returns:
            True  → komut onaylandı (donanım ACK döndü)
            False → komut reddedildi (güvenlik kilidi, geçersiz durum)
        Raises:
            IOError: İletişim hatası (timeout, bağlantı koptu)
        """
        ...

    @abstractmethod
    def kapat(self):
        """
        Bağlantıyı temiz kapat.
        Kaynakları serbest bırak (socket, serial port, vb.)
        finally bloğunda çağrılmak üzere tasarlandı.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
