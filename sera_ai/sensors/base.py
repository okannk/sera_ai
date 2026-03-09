"""
SensorBase — Sensör Soyutlama Arayüzü

Mimari karar:
  Her fiziksel sensör bu sınıftan türer.
  SahaNode hangi sensör markasının kullanıldığını bilmez —
  sadece oku() çağırır ve dict alır.

  DHT22 → SHT31 değiştirmek:
    config.yaml'da tek satır: tip: sht31
    Python kodunda hiçbir şey değişmez.

oku() sözleşmesi:
  - Her zaman dict döndürür
  - Dict, olcum_alanlari'nda belirtilen tüm key'leri içerir
  - Sensör yanıt vermezse IOError fırlatır (None döndürmez)
  - Değerler fiziksel birimde: °C, %, ppm, lux, ADC

Lifecycle:
  baglan() → oku() → oku() → ... → kapat()
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SensorBase(ABC):
    """
    Tek fiziksel sensör için okuma arayüzü.

    Her implementasyon:
      - olcum_alanlari: frozenset — hangi SensorOkuma alanlarını doldurur
      - oku()         : dict     — ölçüm sonuçları
      - baglan()      : bool     — donanım başlatma (opsiyonel override)
      - kapat()       : None     — kaynak serbest bırakma (opsiyonel override)
    """

    @property
    @abstractmethod
    def olcum_alanlari(self) -> frozenset[str]:
        """
        Bu sensörün doldurduğu SensorOkuma alan adları.

        Örnekler:
          SHT31    → frozenset({"T", "H"})
          MH-Z19C  → frozenset({"co2"})
          BH1750   → frozenset({"isik"})
          Kapasitif → frozenset({"toprak_nem"})
        """
        ...

    @abstractmethod
    def oku(self) -> dict:
        """
        Sensörden anlık ölçüm al.

        Returns:
            dict — olcum_alanlari key'lerini içeren ölçüm sonuçları
            Örn: {"T": 23.4, "H": 68.2}

        Raises:
            IOError: Sensör yanıt vermedi, timeout, I2C/UART hatası
        """
        ...

    def baglan(self) -> bool:
        """
        Sensör donanımını başlat (I2C init, UART aç, vb.)

        Varsayılan: donanımsız sensörler için True döner.
        I2C/UART kullananlar override eder.

        Returns:
            True  → hazır
            False → başlatılamadı (sistem devam eder, CB sayar)
        """
        return True

    def kapat(self) -> None:
        """
        Kaynakları serbest bırak.
        finally bloğunda çağrılmak üzere tasarlandı.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.olcum_alanlari)})"
