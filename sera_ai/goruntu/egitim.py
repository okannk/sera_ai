"""
Hastalık Tespiti Model Eğitimi

Sentetik özellik vektörleri oluşturur, RandomForest eğitir ve
models/hastalik_tespiti.pkl olarak kaydeder.

Gerçek kullanım için gerçek bitki görüntü veri seti kullanılmalı.
Bu modül: Raspberry Pi 5'te donanım yokken test ve demo için yeterli.

CLI:
    python -m sera_ai.goruntu.egitim --n 500 --cikti models/
    python -m sera_ai.goruntu.egitim --n 1000 --gosterge

Bağımlılıklar:
    numpy, scikit-learn (extras: ml)
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path


# ── Sınıf Merkezleri (sentetik veri parametreleri) ───────────────

# Her sınıf için 9 özelliğin (OZELLIK_ADLARI sırasıyla) beklenen
# merkez değeri ve standart sapması.
SINIF_PARAMETRELER: dict[str, dict] = {
    "saglikli": {
        "merkez": [0.60, 0.05, 0.05, 0.05, 0.04, 0.55, 0.10, 0.60, 0.12],
        "std":    [0.08, 0.03, 0.03, 0.03, 0.02, 0.08, 0.03, 0.08, 0.04],
    },
    "yaprak_sararmasi": {
        "merkez": [0.18, 0.42, 0.10, 0.06, 0.05, 0.62, 0.14, 0.38, 0.18],
        "std":    [0.07, 0.08, 0.04, 0.03, 0.03, 0.09, 0.04, 0.07, 0.05],
    },
    "kurtcuk": {
        "merkez": [0.33, 0.10, 0.28, 0.06, 0.10, 0.45, 0.18, 0.44, 0.22],
        "std":    [0.07, 0.04, 0.07, 0.03, 0.04, 0.08, 0.05, 0.07, 0.06],
    },
    "mantar": {
        "merkez": [0.22, 0.06, 0.10, 0.33, 0.06, 0.66, 0.12, 0.20, 0.16],
        "std":    [0.06, 0.03, 0.04, 0.08, 0.03, 0.07, 0.04, 0.06, 0.05],
    },
    "yaniklık": {
        "merkez": [0.14, 0.06, 0.24, 0.06, 0.38, 0.30, 0.22, 0.34, 0.28],
        "std":    [0.05, 0.03, 0.07, 0.03, 0.08, 0.07, 0.06, 0.07, 0.07],
    },
}


def _gauss_klip(ort: float, std: float) -> float:
    """Gauss gürültüsü + [0, 1] kırpma."""
    return max(0.0, min(1.0, random.gauss(ort, std)))


def sentetik_veri_olustur(n_per_sinif: int = 200, rastgele_tohum: int = 42):
    """
    Her sınıf için n_per_sinif örnekli sentetik veri seti oluştur.

    Returns:
        X: list[list[float]] — özellik matrisi
        y: list[str]         — etiket vektörü
    """
    random.seed(rastgele_tohum)
    X: list[list[float]] = []
    y: list[str]         = []

    for sinif, params in SINIF_PARAMETRELER.items():
        merkez = params["merkez"]
        std    = params["std"]
        for _ in range(n_per_sinif):
            ornek = [_gauss_klip(m, s) for m, s in zip(merkez, std)]
            X.append(ornek)
            y.append(sinif)

    return X, y


def model_egit(X, y, n_agac: int = 100, rastgele_tohum: int = 42):
    """RandomForest eğit ve döndür."""
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        print("[egitim] scikit-learn bulunamadı. pip install scikit-learn")
        sys.exit(1)

    try:
        import numpy as np
        X_np = np.array(X, dtype=float)
    except ImportError:
        print("[egitim] numpy bulunamadı. pip install numpy")
        sys.exit(1)

    model = RandomForestClassifier(
        n_estimators=n_agac,
        max_depth=8,
        min_samples_leaf=3,
        random_state=rastgele_tohum,
        n_jobs=-1,
    )
    model.fit(X_np, y)
    return model


def modeli_kaydet(model, cikti_dizin: str = "models") -> str:
    """Eğitilmiş modeli .pkl olarak kaydet."""
    import pickle
    dizin = Path(cikti_dizin)
    dizin.mkdir(parents=True, exist_ok=True)
    yol = dizin / "hastalik_tespiti.pkl"
    with open(yol, "wb") as f:
        pickle.dump(model, f)
    return str(yol)


def degerlendirme_goster(model, X, y) -> None:
    """Eğitim seti üzerinde sınıflandırma raporu yaz."""
    try:
        import numpy as np
        from sklearn.model_selection import cross_val_score
        from sklearn.metrics import classification_report

        X_np = np.array(X, dtype=float)
        skorlar = cross_val_score(model, X_np, y, cv=5, scoring="accuracy")
        print(f"\n  5-katlı çapraz doğrulama doğruluğu: {skorlar.mean():.3f} ± {skorlar.std():.3f}")

        tahminler = model.predict(X_np)
        print("\n  Sınıflandırma Raporu (eğitim seti):")
        print(classification_report(y, tahminler, target_names=list(SINIF_PARAMETRELER)))
    except Exception as e:
        print(f"  Değerlendirme hatası: {e}")


def egit(n_per_sinif: int = 200, cikti_dizin: str = "models", gosterge: bool = False) -> str:
    """
    Ana eğitim fonksiyonu.

    Args:
        n_per_sinif  — Her sınıf için örnek sayısı
        cikti_dizin  — Model kaydedilecek dizin
        gosterge     — Değerlendirme raporu göster

    Returns:
        str — Kaydedilen model yolu
    """
    toplam = n_per_sinif * len(SINIF_PARAMETRELER)
    print(f"[egitim] {len(SINIF_PARAMETRELER)} sınıf × {n_per_sinif} örnek = {toplam} toplam")

    print("[egitim] Sentetik veri oluşturuluyor...")
    X, y = sentetik_veri_olustur(n_per_sinif)

    print("[egitim] RandomForest(n_estimators=100) eğitiliyor...")
    model = model_egit(X, y)

    if gosterge:
        degerlendirme_goster(model, X, y)

    yol = modeli_kaydet(model, cikti_dizin)
    print(f"[egitim] Model kaydedildi: {yol}")
    return yol


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Sera bitki hastalığı tespiti model eğitimi"
    )
    ap.add_argument("--n",       type=int,  default=200,    help="Sınıf başına örnek sayısı")
    ap.add_argument("--cikti",   type=str,  default="models", help="Çıktı dizini")
    ap.add_argument("--gosterge", action="store_true",       help="Değerlendirme raporu göster")
    args = ap.parse_args()

    egit(n_per_sinif=args.n, cikti_dizin=args.cikti, gosterge=args.gosterge)
