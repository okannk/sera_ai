"""
Intelligence Katmanı — Aktüatör Karar Motoru

Şu an:
  KuralMotoru  — if/else deterministik (varsayılan, sklearn gerektirmez)
  MLOptimizer  — Gradient Boosting + IsolationForest + RandomForest (sklearn)
  RLAjan       — Tabular Q-Learning, KuralMotoru warm-start (numpy)
  MockOptimizer — test/demo için sabit değer

KontrolMotoru bu katmandan bağımsız:
    motor = KontrolMotoru(..., optimizer=None)           # KuralMotoru otomatik
    motor = KontrolMotoru(..., optimizer=MLOptimizer(.)) # ML ile
    motor = KontrolMotoru(..., optimizer=RLAjan(.))      # RL ile
"""
from .base import HedefDeger, OptimizerBase
from .kural_motoru import KuralMotoru
from .mock import MockOptimizer
from .ml_motor import MLOptimizer
from .rl_ajan import RLAjan, DURUM_SAYISI, EYLEM_SAYISI
from .feature_extractor import FeatureExtractor, FEATURE_BOYUTU

__all__ = [
    "HedefDeger", "OptimizerBase",
    "KuralMotoru", "MockOptimizer", "MLOptimizer", "RLAjan",
    "FeatureExtractor", "FEATURE_BOYUTU",
    "DURUM_SAYISI", "EYLEM_SAYISI",
]
