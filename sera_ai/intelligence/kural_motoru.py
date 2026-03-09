"""
Kural Motoru — Deterministik Aktüatör Kararları

Mevcut if/else mantığı KontrolMotoru'ndan buraya taşındı.
ML/RL katmanı eklenene kadar varsayılan optimizer budur.

Kural öncelik sırası:
  1. ACİL_DURDUR → her şeyi kapat (güvenlik)
  2. Sıcaklık   → soğutma/ısıtıcı
  3. Nem        → fan/sulama
  4. Toprak nemi → sulama
"""
from __future__ import annotations

from ..domain.models import BitkilProfili, SensorOkuma
from ..domain.state_machine import Durum
from .base import HedefDeger, OptimizerBase


class KuralMotoru(OptimizerBase):
    """
    Bitki profiline dayalı deterministik kural motoru.

    Profil eşiklerini (opt_T, max_H, vb.) doğrudan kullanır.
    Yeni bitki eklemek → config.yaml değişikliği, kod değil.
    """

    def __init__(self, profil: BitkilProfili) -> None:
        self.profil = profil

    def hedef_hesapla(self, sensor: SensorOkuma, durum: Durum) -> HedefDeger:
        if durum == Durum.ACIL_DURDUR:
            # Acil: tüm aktüatörleri kapat
            return HedefDeger()

        p = self.profil
        hedef = HedefDeger()

        # Sıcaklık kontrolü
        if sensor.T > p.opt_T + 2:
            hedef.sogutma = True
            hedef.fan     = True
        elif sensor.T < p.opt_T - 2:
            hedef.isitici = True

        # Nem kontrolü
        if sensor.H > p.max_H:
            hedef.fan = True
        if sensor.H < p.min_H:
            hedef.sulama = True

        # Toprak nemi (ADC < 350 → kuru toprak → sula)
        if sensor.toprak_nem < 350:
            hedef.sulama = True

        return hedef
