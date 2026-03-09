"""
Feature Extractor — SensorOkuma → numpy feature vector

Her model aynı vektörü görür; normalizasyon burada yapılır.
Profil bağımlı: Domates ve Marul için farklı T_norm aralıkları.

Feature vector (FEATURE_BOYUTU = 9):
  0  T_norm        — sıcaklık, profil min/max'a göre normalize
  1  H_norm        — nem, profil min/max'a göre normalize
  2  co2_norm      — CO₂ / 5000
  3  isik_norm     — lux / 100_000
  4  toprak_norm   — ADC / 1023
  5  ph_norm       — pH / 9.0
  6  ec_norm       — EC / 10.0
  7  T_sapma_norm  — (T - opt_T) / 15  (sıcaklık sapması)
  8  H_merkez_norm — nem, profil bandının merkezine göre sapma
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..domain.models import BitkilProfili, SensorOkuma

FEATURE_BOYUTU = 9


class FeatureExtractor:
    """
    Bitki profiline bağlı feature dönüşümü.

    Aynı T değeri Domates ve Marul için farklı normalize edilir
    çünkü optimal aralıklar farklı.
    """

    def __init__(self, profil: "BitkilProfili") -> None:
        self.profil = profil
        # Sıfıra bölmeyi önle
        self._T_aralik = max(profil.max_T - profil.min_T, 1.0)
        self._H_aralik = max(profil.max_H - profil.min_H, 1.0)
        self._H_merkez = (profil.min_H + profil.max_H) / 2.0

    def cikart(self, sensor: "SensorOkuma") -> np.ndarray:
        """
        Tek sensör okuma → (FEATURE_BOYUTU,) float32 array.
        Değerler [0, 1] dışına çıkabilir (aşırı değerler için bilinçli karar).
        """
        p = self.profil
        return np.array([
            (sensor.T          - p.min_T)        / self._T_aralik,
            (sensor.H          - p.min_H)        / self._H_aralik,
            sensor.co2         / 5000.0,
            sensor.isik        / 100_000.0,
            sensor.toprak_nem  / 1023.0,
            sensor.ph          / 9.0,
            sensor.ec          / 10.0,
            (sensor.T          - p.opt_T)        / 15.0,
            (sensor.H          - self._H_merkez) / self._H_aralik,
        ], dtype=np.float32)

    def toplu_cikart(self, sensorler: "list[SensorOkuma]") -> np.ndarray:
        """
        Sensör listesi → (n, FEATURE_BOYUTU) array.
        Eğitim verisi üretimi için kullanılır.
        """
        return np.stack([self.cikart(s) for s in sensorler])
