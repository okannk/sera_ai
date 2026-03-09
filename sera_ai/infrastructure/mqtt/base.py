"""
MQTT İstemci Soyut Temel Sınıfı

Neden ABC?
  broker.py: gerçek Mosquitto (paho-mqtt, RPi üzerinde)
  mock.py  : in-process test broker (paho gerekmez)

  KontrolMotoru, ESP32Simulatoru — her ikisi de bu arayüzü kullanır.
  Broker değişince → sadece concrete sınıf değişir.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

# Callback tipi: (topic, payload) → None
# payload her zaman bytes — JSON/string dönüşümü çağıran tarafa ait
MesajCallback = Callable[[str, bytes], None]


class MQTTIstemciBase(ABC):
    """
    Minimal MQTT istemci arayüzü.

    Sözleşme:
      - baglan() → True ise yayinla/abone_ol güvenle çağrılabilir
      - yayinla() → başarı True, başarısızlık False (istisna fırlatmaz)
      - abone_ol() → aynı topic'e birden fazla callback eklenebilir
      - Wildcard: '+' (tek seviye), '#' (çok seviye) desteklenmeli
    """

    @abstractmethod
    def baglan(self) -> bool:
        """Broker'a bağlan. Başarıda True döner."""

    @abstractmethod
    def kes(self) -> None:
        """Bağlantıyı temiz kapat. Tüm abonelikler silinir."""

    @abstractmethod
    def yayinla(self, topic: str, payload: str | bytes, qos: int = 0) -> bool:
        """
        Mesaj yayınla. str payload otomatik encode edilir.
        Başarıda True, bağlı değilse veya hata olursa False döner.
        """

    @abstractmethod
    def abone_ol(self, topic: str, callback: MesajCallback) -> None:
        """
        topic'e abone ol (wildcard destekli).
        Aynı topic'e birden fazla callback eklenebilir.
        """

    @abstractmethod
    def abonelikten_cik(self, topic: str) -> None:
        """topic aboneliğini kaldır (tüm callback'ler dahil)."""

    @property
    @abstractmethod
    def bagli_mi(self) -> bool:
        """Aktif bağlantı var mı?"""
