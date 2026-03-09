"""
ML Optimizer — Gradient Boosting + Isolation Forest + Random Forest

4 model:
  yield_model   — GradientBoostingRegressor : verim tahmini (0–100)
  anomaly_model — IsolationForest           : anomali tespiti
  growth_model  — RandomForestRegressor     : büyüme hızı (0–1)
  stress_model  — RandomForestClassifier    : stres sınıfı → HedefDeger

Başlatma davranışı:
  1. models/<Bitki>_*.pkl varsa → yükle
  2. Yoksa → sentetik veriyle otomatik eğit + kaydet

sklearn yüklü değilse → KuralMotoru'na devre dışı bırakılır (sessiz).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..domain.models import BitkilProfili, SensorOkuma
from ..domain.state_machine import Durum
from .base import HedefDeger, OptimizerBase
from .egitim import STRES_HEDEF, hedef_to_stres
from .feature_extractor import FeatureExtractor
from .kural_motoru import KuralMotoru

if TYPE_CHECKING:
    pass

try:
    import numpy as np
    import joblib
    from sklearn.base import BaseEstimator
    _SKLEARN_VAR = True
except ImportError:
    _SKLEARN_VAR = False


class MLOptimizer(OptimizerBase):
    """
    Sklearn tabanlı aktüatör optimizer.

    Anomali tespit edilirse → KuralMotoru'na fallback (güvenli mod).
    ACİL_DURDUR durumunda → hepsi kapalı (kural > ML, her zaman).

    Ek metotlar (API / dashboard için):
      verim_tahmini(sensor)    → float 0–100
      buyume_hizi_tahmini(sensor) → float 0–1
      anomali_mi(sensor)       → bool
    """

    def __init__(
        self,
        profil: BitkilProfili,
        model_dizin: str = "models",
    ) -> None:
        self.profil      = profil
        self.model_dizin = Path(model_dizin)
        self.extractor   = FeatureExtractor(profil)
        self._fallback   = KuralMotoru(profil)

        self._yield_model:   object = None
        self._anomaly_model: object = None
        self._growth_model:  object = None
        self._stress_model:  object = None

        if _SKLEARN_VAR:
            self._modeller_yukle_veya_egit()
        else:
            print(
                "[MLOptimizer] scikit-learn bulunamadı → KuralMotoru aktif. "
                "(pip install scikit-learn numpy joblib)"
            )

    # ── Yükleme / Eğitim ──────────────────────────────────────

    def _model_yolu(self, isim: str) -> Path:
        return self.model_dizin / f"{self.profil.isim}_{isim}.pkl"

    def _tum_modeller_mevcut(self) -> bool:
        return all(
            self._model_yolu(isim).exists()
            for isim in ("yield", "anomaly", "growth", "stress")
        )

    def _modeller_yukle_veya_egit(self) -> None:
        if self._tum_modeller_mevcut():
            self._yield_model   = joblib.load(self._model_yolu("yield"))
            self._anomaly_model = joblib.load(self._model_yolu("anomaly"))
            self._growth_model  = joblib.load(self._model_yolu("growth"))
            self._stress_model  = joblib.load(self._model_yolu("stress"))
        else:
            self._egit_ve_kaydet()

    def _egit_ve_kaydet(self) -> None:
        """İlk çalıştırmada sentetik veriyle eğit, kaydet."""
        from .egitim import sentetik_veri_uret, modelleri_egit

        print(f"[MLOptimizer] {self.profil.isim} modeli bulunamadı → otomatik eğitiliyor...")
        X, y_stress, y_yield, y_growth = sentetik_veri_uret(self.profil, n=500)
        modeller = modelleri_egit(X, y_stress, y_yield, y_growth)

        self._yield_model   = modeller["yield"]
        self._anomaly_model = modeller["anomaly"]
        self._growth_model  = modeller["growth"]
        self._stress_model  = modeller["stress"]

        self.model_dizin.mkdir(parents=True, exist_ok=True)
        for isim, model in modeller.items():
            joblib.dump(model, self._model_yolu(isim))
            print(f"[MLOptimizer] Kaydedildi: {self._model_yolu(isim)}")

    # ── OptimizerBase arayüzü ─────────────────────────────────

    def hedef_hesapla(self, sensor: SensorOkuma, durum: Durum) -> HedefDeger:
        """
        Ana karar metodu.

        ACİL_DURDUR → hepsi kapalı (güvenlik kuralı — ML'e danışılmaz).
        sklearn yok veya anomali → KuralMotoru fallback.
        Aksi → stress_model tahmininden HedefDeger.
        """
        if durum == Durum.ACIL_DURDUR:
            return HedefDeger()

        if self._stress_model is None:
            return self._fallback.hedef_hesapla(sensor, durum)

        X = self.extractor.cikart(sensor).reshape(1, -1)

        # Anomali → güvenli fallback
        if self._anomaly_model is not None and self.anomali_mi(sensor):
            return self._fallback.hedef_hesapla(sensor, durum)

        stres_sinif = int(self._stress_model.predict(X)[0])
        return STRES_HEDEF.get(stres_sinif, HedefDeger())

    # ── Ek tahmin metotları ───────────────────────────────────

    def verim_tahmini(self, sensor: SensorOkuma) -> float:
        """Tahmini verim skoru: 0–100."""
        if self._yield_model is None:
            return 0.0
        import numpy as np
        X = self.extractor.cikart(sensor).reshape(1, -1)
        return float(np.clip(self._yield_model.predict(X)[0], 0.0, 100.0))

    def buyume_hizi_tahmini(self, sensor: SensorOkuma) -> float:
        """Tahmini büyüme hızı: 0–1."""
        if self._growth_model is None:
            return 0.0
        import numpy as np
        X = self.extractor.cikart(sensor).reshape(1, -1)
        return float(np.clip(self._growth_model.predict(X)[0], 0.0, 1.0))

    def anomali_mi(self, sensor: SensorOkuma) -> bool:
        """IsolationForest: sensör okuması anomali mi? (-1 = anomali)"""
        if self._anomaly_model is None:
            return False
        X = self.extractor.cikart(sensor).reshape(1, -1)
        return int(self._anomaly_model.predict(X)[0]) == -1
