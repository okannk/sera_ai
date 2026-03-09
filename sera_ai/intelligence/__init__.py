"""
Intelligence Katmanı — Aktüatör Karar Motoru

Şu an: kural_motoru.py (if/else tabanlı)
İleride: ML modeli, RL ajanı — aynı OptimizerBase arayüzüyle DI ile eklenir.

KontrolMotoru bu katmandan bağımsız:
    motor = KontrolMotoru(..., optimizer=None)          # KuralMotoru otomatik
    motor = KontrolMotoru(..., optimizer=RLAjani(...))  # RL ajanı ile
"""
from .base import HedefDeger, OptimizerBase
from .kural_motoru import KuralMotoru
from .mock import MockOptimizer

__all__ = ["HedefDeger", "OptimizerBase", "KuralMotoru", "MockOptimizer"]
