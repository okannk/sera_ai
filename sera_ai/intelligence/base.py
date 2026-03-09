"""
Intelligence Katmanı — Soyut Arayüz

OptimizerBase: Tek sorumluluk — sensör + durum → hedef aktüatör konumu.
HedefDeger:    Dört aktüatörün istenen konumu (açık/kapalı).

Neden ayrı bir katman?
  KontrolMotoru "ne yapılacağına" karar verirdi (if/else).
  Bu katman o kararı dışarı taşır:
    - KuralMotoru  → mevcut deterministik mantık (varsayılan)
    - MLOptimizer  → scikit-learn / ONNX model (ileride)
    - RLAjan       → reinforcement learning (ileride)
  KontrolMotoru hangisi geldiğini bilmez — sadece arayüzü çağırır.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.models import BitkilProfili, SensorOkuma
    from ..domain.state_machine import Durum


@dataclass
class HedefDeger:
    """
    Dört temel aktüatörün istenen konumu.

    True  → aktüatör açık olmalı
    False → aktüatör kapalı olmalı

    Idempotent semantik: "bu konumda ol" demek,
    "bu komutu gönder" değil.
    """
    sulama:  bool = False
    isitici: bool = False
    sogutma: bool = False
    fan:     bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


class OptimizerBase(ABC):
    """
    Aktüatör hedef hesaplama arayüzü.

    Implementasyonlar:
      KuralMotoru  → deterministik if/else (varsayılan)
      MockOptimizer → test için sabit değer
      MLOptimizer  → ileride: sklearn/onnx model
      RLAjan       → ileride: reinforcement learning
    """

    @abstractmethod
    def hedef_hesapla(self, sensor: "SensorOkuma", durum: "Durum") -> HedefDeger:
        """
        Sensör okuma ve sistem durumuna göre aktüatör hedeflerini hesapla.

        Args:
            sensor: Anlık sensör okuması
            durum:  Mevcut sera durumu (NORMAL, ALARM, vb.)

        Returns:
            HedefDeger — her aktüatörün olması gereken konumu
        """
        ...
