"""
MockSensor — Test ve Demo İçin Sanal Sensör

Gerçek donanım olmadan sensör davranışını simüle eder.
Her alanı ayrı ayrı yapılandırılabilir.

Kullanım:
    # Sabit değer
    s = MockSensor({"T": 23.0, "H": 72.0})
    s.oku()  # → {"T": 23.0, "H": 72.0}

    # Hata simülasyonu
    s = MockSensor({"co2": 950}, hata_orani=0.3)
    s.oku()  # 3'te 1 ihtimalle IOError fırlatır

    # Çok alanı tek sensör
    s = MockSensor({"T": 23.0, "H": 72.0, "isik": 500})
"""
from __future__ import annotations

import random

from .base import SensorBase


class MockSensor(SensorBase):
    """
    Test amaçlı sensör — donanım gerektirmez.

    Özellikler:
      - Sabit değer veya küçük gürültü (sapma_std > 0)
      - Ayarlanabilir hata oranı (oku() IOError fırlatır)
      - Çağrı sayacı (test assertion için)
    """

    def __init__(
        self,
        degerler: dict,
        sapma_std: float = 0.0,
        hata_orani: float = 0.0,
        tohum: int | None = None,
    ) -> None:
        """
        Args:
            degerler:   Döndürülecek ölçüm değerleri, örn: {"T": 23.0, "H": 70.0}
            sapma_std:  Gaussian gürültü standart sapması (0 = sabit değer)
            hata_orani: 0.0–1.0 arası IOError olasılığı
            tohum:      Tekrarlanabilir test için rastgele tohum
        """
        self._degerler   = dict(degerler)
        self._sapma_std  = sapma_std
        self._hata_orani = hata_orani
        self._rng        = random.Random(tohum)
        self.cagri_sayisi = 0
        self.hata_sayisi  = 0

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset(self._degerler.keys())

    def oku(self) -> dict:
        self.cagri_sayisi += 1

        if self._hata_orani > 0 and self._rng.random() < self._hata_orani:
            self.hata_sayisi += 1
            raise IOError(f"[MockSensor] Simüle edilmiş hata ({self.hata_sayisi})")

        if self._sapma_std > 0:
            return {
                k: v + self._rng.gauss(0, self._sapma_std)
                for k, v in self._degerler.items()
            }

        return dict(self._degerler)

    def deger_ayarla(self, **kwargs) -> None:
        """Test sırasında değerleri değiştir."""
        self._degerler.update(kwargs)
