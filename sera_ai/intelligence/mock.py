"""
Mock Optimizer — Test ve Demo İçin

Sabit HedefDeger döndürür.
Kural mantığından bağımsız aktüatör davranışı test etmek için kullanılır.

Kullanım:
    # Her adımda sulama açık, diğerleri kapalı
    optimizer = MockOptimizer(HedefDeger(sulama=True))
    motor = KontrolMotoru(..., optimizer=optimizer)

    # Tamamen pasif (hiçbir şey açma)
    optimizer = MockOptimizer()
"""
from __future__ import annotations

from ..domain.models import SensorOkuma
from ..domain.state_machine import Durum
from .base import HedefDeger, OptimizerBase


class MockOptimizer(OptimizerBase):
    """
    Test için sabit değer döndüren optimizer.

    Sensor ve durum parametrelerini yoksayar —
    sadece yapılandırılan sabit HedefDeger'i döndürür.
    """

    def __init__(self, sabit: HedefDeger | None = None) -> None:
        self.sabit = sabit if sabit is not None else HedefDeger()
        self.cagri_sayisi = 0  # Kaç kez çağrıldığını say — test assertion için

    def hedef_hesapla(self, sensor: SensorOkuma, durum: Durum) -> HedefDeger:
        self.cagri_sayisi += 1
        return self.sabit
