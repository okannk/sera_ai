"""
Offline Eğitim Scripti — Sentetik Veri → Sklearn Modelleri

Gerçek saha verisi yokken bitki fizyolojisi sınırları içinde sentetik
veri üretir, KuralMotoru ile etiketler ve 4 modeli eğitir.

Kullanım:
    python -m sera_ai.intelligence.egitim --bitki Domates
    python -m sera_ai.intelligence.egitim --bitki Biber --n 1000
    python -m sera_ai.intelligence.egitim --bitki Marul --model-dizin /data/models

Çıktı:
    models/<Bitki>_yield.pkl    — GradientBoostingRegressor (verim tahmini)
    models/<Bitki>_anomaly.pkl  — IsolationForest (anomali tespiti)
    models/<Bitki>_growth.pkl   — RandomForestRegressor (büyüme hızı)
    models/<Bitki>_stress.pkl   — RandomForestClassifier (stres sınıfı)
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ..domain.models import BitkilProfili, SensorOkuma, VARSAYILAN_PROFILLER
from ..domain.state_machine import Durum
from .base import HedefDeger
from .feature_extractor import FeatureExtractor
from .kural_motoru import KuralMotoru

if TYPE_CHECKING:
    pass


# ── Stres Sınıfları ───────────────────────────────────────────
# 0: Normal    → eylem yok
# 1: Soğuk     → isitici
# 2: Sıcak     → sogutma + fan
# 3: Nemli     → fan
# 4: Kuru      → sulama

STRES_HEDEF: dict[int, HedefDeger] = {
    0: HedefDeger(),
    1: HedefDeger(isitici=True),
    2: HedefDeger(sogutma=True, fan=True),
    3: HedefDeger(fan=True),
    4: HedefDeger(sulama=True),
}


def hedef_to_stres(hedef: HedefDeger) -> int:
    """HedefDeger → stres sınıf indeksi (öncelik sıralı)."""
    if hedef.sogutma:
        return 2
    if hedef.isitici:
        return 1
    if hedef.sulama:
        return 4
    if hedef.fan:
        return 3
    return 0


def verim_skoru(sensor: SensorOkuma, profil: BitkilProfili) -> float:
    """
    Fizik tabanlı verim skoru (0–100).

    Sıcaklık ve nem sapması verimliliği düşürür;
    yüksek CO₂ yüksek fotosentez → verim artışı.
    """
    T_stres = max(0.0, abs(sensor.T - profil.opt_T) - 2.0) / 10.0
    H_merkez = (profil.min_H + profil.max_H) / 2.0
    H_stres = max(0.0, abs(sensor.H - H_merkez) - 5.0) / 25.0
    co2_bonus = min(1.0, sensor.co2 / max(profil.opt_CO2, 1))
    skor = 100.0 * (1.0 - 0.5 * T_stres - 0.3 * H_stres) * co2_bonus
    return float(max(0.0, min(100.0, skor)))


def buyume_skoru(sensor: SensorOkuma, profil: BitkilProfili) -> float:
    """Büyüme hızı (0–1) — verim skorunun normalize hali."""
    return verim_skoru(sensor, profil) / 100.0


def _rastgele_sensor(profil: BitkilProfili, rng: random.Random) -> SensorOkuma:
    """
    Fizyolojik sınırlar içinde rastgele sensör okuma.
    Tüm durum sınıflarının eşit temsil edilmesi için geniş aralık.
    """
    T_min = profil.min_T - 8.0
    T_max = profil.max_T + 12.0
    return SensorOkuma(
        sera_id="egitim",
        T=rng.uniform(T_min, T_max),
        H=rng.uniform(20.0, 99.0),
        co2=rng.randint(300, 2500),
        isik=rng.randint(0, 80000),
        toprak_nem=rng.randint(50, 950),
        ph=rng.uniform(4.0, 8.5),
        ec=rng.uniform(0.1, 8.0),
    )


def sentetik_veri_uret(
    profil: BitkilProfili,
    n: int = 500,
    tohum: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Sentetik eğitim verisi üret.

    Returns:
        X          — (n, FEATURE_BOYUTU) float32 feature matrix
        y_stress   — (n,) int   stres sınıfı (0–4)
        y_yield    — (n,) float verim skoru (0–100)
        y_growth   — (n,) float büyüme hızı (0–1)
    """
    rng = random.Random(tohum)
    extractor = FeatureExtractor(profil)
    kural = KuralMotoru(profil)

    sensorler: list[SensorOkuma] = []
    y_stress: list[int] = []
    y_yield: list[float] = []
    y_growth: list[float] = []

    # Her stres sınıfından en az n//10 örnek garanti et
    siniflar_sayisi = {i: 0 for i in range(5)}
    min_sinif = max(10, n // 10)

    for _ in range(n * 3):          # Fazla üret, filtrele
        if len(sensorler) >= n:
            break

        s = _rastgele_sensor(profil, rng)
        hedef = kural.hedef_hesapla(s, Durum.NORMAL)
        sinif = hedef_to_stres(hedef)

        # Aşırı temsil edilen sınıfı geç (dengeli veri seti için)
        if siniflar_sayisi[sinif] >= n * 0.7 and not all(
            v >= min_sinif for v in siniflar_sayisi.values()
        ):
            continue

        sensorler.append(s)
        y_stress.append(sinif)
        y_yield.append(verim_skoru(s, profil))
        y_growth.append(buyume_skoru(s, profil))
        siniflar_sayisi[sinif] += 1

    # Yeterli örnek yoksa doldur
    while len(sensorler) < n:
        s = _rastgele_sensor(profil, rng)
        hedef = kural.hedef_hesapla(s, Durum.NORMAL)
        sensorler.append(s)
        y_stress.append(hedef_to_stres(hedef))
        y_yield.append(verim_skoru(s, profil))
        y_growth.append(buyume_skoru(s, profil))

    X = extractor.toplu_cikart(sensorler)
    return (
        X,
        np.array(y_stress,  dtype=np.int32),
        np.array(y_yield,   dtype=np.float32),
        np.array(y_growth,  dtype=np.float32),
    )


def modelleri_egit(
    X: np.ndarray,
    y_stress: np.ndarray,
    y_yield: np.ndarray,
    y_growth: np.ndarray,
) -> dict:
    """
    4 sklearn modeli eğit ve döndür.

    Returns:
        {
          "yield":   GradientBoostingRegressor,
          "anomaly": IsolationForest,
          "growth":  RandomForestRegressor,
          "stress":  RandomForestClassifier,
        }
    """
    from sklearn.ensemble import (
        GradientBoostingRegressor,
        IsolationForest,
        RandomForestClassifier,
        RandomForestRegressor,
    )

    yield_model = GradientBoostingRegressor(
        n_estimators=100, max_depth=4, random_state=42,
    )
    yield_model.fit(X, y_yield)

    # IsolationForest: sadece etiket kullanmaz, tüm X üzerinde eğitilir
    anomaly_model = IsolationForest(
        n_estimators=100, contamination=0.05, random_state=42,
    )
    anomaly_model.fit(X)

    growth_model = RandomForestRegressor(
        n_estimators=100, max_depth=6, random_state=42,
    )
    growth_model.fit(X, y_growth)

    stress_model = RandomForestClassifier(
        n_estimators=100, max_depth=6, random_state=42,
    )
    stress_model.fit(X, y_stress)

    return {
        "yield":   yield_model,
        "anomaly": anomaly_model,
        "growth":  growth_model,
        "stress":  stress_model,
    }


def egit_ve_kaydet(
    profil: BitkilProfili,
    model_dizin: str = "models",
    n: int = 500,
    tohum: int = 42,
) -> None:
    """Eğit ve .pkl olarak kaydet."""
    import joblib

    dizin = Path(model_dizin)
    dizin.mkdir(parents=True, exist_ok=True)

    print(f"[Eğitim] {profil.isim} — {n} örnek üretiliyor...")
    X, y_stress, y_yield, y_growth = sentetik_veri_uret(profil, n=n, tohum=tohum)

    print(f"[Eğitim] Modeller eğitiliyor...")
    modeller = modelleri_egit(X, y_stress, y_yield, y_growth)

    for isim, model in modeller.items():
        yol = dizin / f"{profil.isim}_{isim}.pkl"
        joblib.dump(model, yol)
        print(f"[Eğitim] Kaydedildi: {yol}")

    print(f"[Eğitim] {profil.isim} tamamlandı.")


# ── CLI ───────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sera AI — ML model eğitimi (sentetik veri)"
    )
    parser.add_argument(
        "--bitki",
        choices=list(VARSAYILAN_PROFILLER.keys()),
        default="Domates",
        help="Eğitilecek bitki profili",
    )
    parser.add_argument(
        "--n", type=int, default=500,
        help="Sentetik örnek sayısı (varsayılan: 500)",
    )
    parser.add_argument(
        "--model-dizin", default="models",
        help="Model kayıt dizini (varsayılan: models/)",
    )
    parser.add_argument(
        "--tohum", type=int, default=42,
        help="Rastgelelik tohumu (varsayılan: 42)",
    )
    parser.add_argument(
        "--hepsi", action="store_true",
        help="Tüm bitki profilleri için eğit",
    )
    args = parser.parse_args()

    profiller = (
        list(VARSAYILAN_PROFILLER.values())
        if args.hepsi
        else [VARSAYILAN_PROFILLER[args.bitki]]
    )

    for profil in profiller:
        egit_ve_kaydet(
            profil,
            model_dizin=args.model_dizin,
            n=args.n,
            tohum=args.tohum,
        )


if __name__ == "__main__":
    main()
