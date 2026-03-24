"""
Hastalık Tespiti Modeli — RandomForest Renk Histogramı

Özellik vektörü (9 boyut, tümü 0.0–1.0):
  yesil_oran        — Yeşil piksel oranı (sağlıklı yaprak göstergesi)
  sari_oran         — Sarı piksel oranı (yaprak sararmasi)
  kahverengi_oran   — Kahverengi piksel oranı (yanıklık / kurtcuk)
  gri_oran          — Gri/beyaz piksel oranı (fungal)
  koyu_oran         — Koyu piksel oranı (yanıklık)
  parlaklik_ort     — Ortalama parlaklık (0–1)
  parlaklik_std     — Parlaklık std (doku zenginliği)
  doygunluk_ort     — Ortalama doygunluk
  renk_std          — Renk çeşitliliği

Görüntü işleme:
  PIL mevcut → JPEG decode → 64×64 RGB → renk analizi (doğru)
  PIL yok    → byte istatistikleri → yaklaşık özellikler (fallback)

Model:
  RandomForest(n_estimators=100) — sklearn
  sklearn yok → KuralTespiti (renk eşiği tabanlı, fallback)

Kullanım:
    model = HastalikModeli("models/hastalik_tespiti.pkl")
    sonuc = model.tespit_et(jpeg_bytes, "s1")
"""
from __future__ import annotations

import math
from typing import Optional

from .base import (
    GorüntuServisi,
    HastalikTespitBase,
    HASTALIK_SINIFLARI,
    TespitSonucu,
    VARSAYILAN_GUVEN_ESIGI,
)


# ── Özellik Çıkarım ──────────────────────────────────────────────

OZELLIK_ADLARI = [
    "yesil_oran",
    "sari_oran",
    "kahverengi_oran",
    "gri_oran",
    "koyu_oran",
    "parlaklik_ort",
    "parlaklik_std",
    "doygunluk_ort",
    "renk_std",
]
OZELLIK_SAYISI = len(OZELLIK_ADLARI)  # 9


def ozellik_cikar(goruntu_bytes: bytes) -> list[float]:
    """
    JPEG bytes → 9 boyutlu özellik vektörü.

    PIL mevcut → gerçek renk analizi.
    PIL yok    → byte tabanlı yaklaşık analiz (fallback).

    Returns:
        list[float] — 9 değer, her biri [0.0, 1.0]
    """
    try:
        return _pil_ozellik_cikar(goruntu_bytes)
    except ImportError:
        return _byte_ozellik_cikar(goruntu_bytes)
    except Exception:
        return _byte_ozellik_cikar(goruntu_bytes)


def _pil_ozellik_cikar(goruntu_bytes: bytes) -> list[float]:
    """PIL ile JPEG decode → renk histogramı analizi."""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(goruntu_bytes)).convert("RGB")
    img = img.resize((64, 64), Image.BILINEAR)

    piksel_sayisi = 64 * 64
    pikseller = list(img.getdata())  # [(R, G, B), ...]

    yesil = sari = kahverengi = gri = koyu = 0
    parlaklik_toplam = parlaklik_kare_toplam = 0.0
    doygunluk_toplam = 0.0
    r_toplam = g_toplam = b_toplam = 0.0

    for r, g, b in pikseller:
        parlak = (r + g + b) / 3.0
        parlaklik_toplam       += parlak
        parlaklik_kare_toplam  += parlak * parlak
        r_toplam += r; g_toplam += g; b_toplam += b

        maks = max(r, g, b)
        min_ = min(r, g, b)
        doygunluk = (maks - min_) / (maks + 1.0)
        doygunluk_toplam += doygunluk

        # Renk sınıflandırma
        if g > r + 20 and g > b + 20 and g > 80:
            yesil += 1
        elif r > 150 and g > 150 and b < 100:
            sari += 1
        elif r > 90 and g < 75 and b < 60:
            kahverengi += 1
        elif abs(r - g) < 25 and abs(g - b) < 25 and r > 150:
            gri += 1
        elif maks < 60:
            koyu += 1

    n = piksel_sayisi
    parlak_ort = parlaklik_toplam / (n * 255.0)
    parlak_kare_ort = parlaklik_kare_toplam / (n * 255.0 * 255.0)
    parlak_std = math.sqrt(max(0.0, parlak_kare_ort - parlak_ort ** 2))

    r_ort = r_toplam / (n * 255.0)
    g_ort = g_toplam / (n * 255.0)
    b_ort = b_toplam / (n * 255.0)
    renk_std = math.sqrt(
        ((r_ort - parlak_ort)**2 + (g_ort - parlak_ort)**2 + (b_ort - parlak_ort)**2) / 3.0
    )

    return [
        yesil       / n,
        sari        / n,
        kahverengi  / n,
        gri         / n,
        koyu        / n,
        parlak_ort,
        parlak_std,
        doygunluk_toplam / n,
        renk_std,
    ]


def _byte_ozellik_cikar(goruntu_bytes: bytes) -> list[float]:
    """
    Fallback: PIL olmadan byte istatistikleri.
    JPEG header/compression nedeniyle gerçek renk bilgisi yok,
    ama model eğitimi tutarlı versiyon kullandığında çalışır.
    """
    if len(goruntu_bytes) < 4:
        return [0.0] * OZELLIK_SAYISI

    b = goruntu_bytes[:512] if len(goruntu_bytes) > 512 else goruntu_bytes
    n = len(b)

    toplam    = sum(b)
    ort       = toplam / n / 255.0
    kare_ort  = sum(x * x for x in b) / n / (255.0 * 255.0)
    std       = math.sqrt(max(0.0, kare_ort - ort ** 2))

    # Dört çeyrek istatistikleri — kabaca renk dağılımı
    c1 = sum(b[:n//4]) / max(n // 4, 1) / 255.0
    c2 = sum(b[n//4:n//2]) / max(n // 4, 1) / 255.0
    c3 = sum(b[n//2:3*n//4]) / max(n // 4, 1) / 255.0
    c4 = sum(b[3*n//4:]) / max(n // 4, 1) / 255.0

    return [
        max(0.0, c2 - 0.3),   # yesil_oran (yaklaşık)
        max(0.0, (c1+c2)/2 - 0.4),   # sari_oran
        max(0.0, c1 - 0.4),          # kahverengi_oran
        max(0.0, c4 - 0.5),          # gri_oran
        max(0.0, 0.3 - ort),         # koyu_oran
        ort,                          # parlaklik_ort
        std,                          # parlaklik_std
        max(0.0, std - 0.1),          # doygunluk_ort
        abs(c1 - c3),                 # renk_std
    ]


# ── Kural Tabanlı Fallback Tespiti ───────────────────────────────

class KuralTespiti(HastalikTespitBase):
    """
    sklearn olmadan çalışan eşik tabanlı tespit.
    HastalikModeli sklearn yükleyemezse bu devreye girer.
    """

    ESIKLER: dict[str, dict[str, float]] = {
        "saglikli":         {"yesil_oran": 0.40},
        "yaprak_sararmasi": {"sari_oran":  0.25},
        "kurtcuk":          {"kahverengi_oran": 0.20},
        "mantar":           {"gri_oran":   0.25},
        "yaniklık":         {"koyu_oran":  0.30},
    }

    def tespit_et(self, goruntu: bytes, sera_id: str) -> TespitSonucu:
        ozellikler = ozellik_cikar(goruntu)
        v = dict(zip(OZELLIK_ADLARI, ozellikler))

        # En yüksek puan alan sınıf
        en_iyi = "saglikli"
        en_iyi_skor = 0.0

        for sinif, esikler in self.ESIKLER.items():
            skor = sum(
                max(0.0, v.get(alan, 0.0) - esik)
                for alan, esik in esikler.items()
            )
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi      = sinif

        # Güven: normalize edilmiş skor
        guven = min(0.85, 0.55 + en_iyi_skor * 2.0)

        return TespitSonucu(sera_id=sera_id, hastalik=en_iyi, guven=round(guven, 3))


# ── ML Model ─────────────────────────────────────────────────────

class HastalikModeli(HastalikTespitBase):
    """
    RandomForest tabanlı hastalık tespiti.

    modeli_yukle(yol) ile .pkl dosyasından yüklenir.
    sklearn veya model dosyası yoksa → KuralTespiti fallback.

    Args:
        model_yolu — .pkl dosyasının yolu
    """

    def __init__(self, model_yolu: Optional[str] = None):
        self.model_yolu = model_yolu
        self._model     = None
        self._fallback  = KuralTespiti()
        self._hazir     = False

        if model_yolu:
            self.modeli_yukle(model_yolu)

    def modeli_yukle(self, yol: str) -> None:
        """Eğitilmiş RandomForest modelini .pkl'den yükle."""
        try:
            import pickle
            from pathlib import Path
            dosya = Path(yol)
            if not dosya.exists():
                print(f"[HastalikModeli] Model bulunamadı: {yol} → KuralTespiti")
                return
            with open(dosya, "rb") as f:
                self._model = pickle.load(f)
            self._hazir = True
            print(f"[HastalikModeli] Model yüklendi: {yol}")
        except ImportError:
            print("[HastalikModeli] pickle yok? → KuralTespiti fallback")
        except Exception as e:
            print(f"[HastalikModeli] Yükleme hatası: {e} → KuralTespiti fallback")

    def tespit_et(self, goruntu: bytes, sera_id: str) -> TespitSonucu:
        if not self._hazir or self._model is None:
            return self._fallback.tespit_et(goruntu, sera_id)

        try:
            return self._ml_tespit(goruntu, sera_id)
        except Exception as e:
            print(f"[HastalikModeli] Inference hatası: {e} → KuralTespiti")
            return self._fallback.tespit_et(goruntu, sera_id)

    def _ml_tespit(self, goruntu: bytes, sera_id: str) -> TespitSonucu:
        import numpy as np

        ozellikler = ozellik_cikar(goruntu)
        X = np.array(ozellikler, dtype=float).reshape(1, -1)

        tahmin = self._model.predict(X)[0]

        # predict_proba varsa güven skoru al
        if hasattr(self._model, "predict_proba"):
            proba   = self._model.predict_proba(X)[0]
            siniflar = list(self._model.classes_)
            idx     = siniflar.index(tahmin) if tahmin in siniflar else 0
            guven   = float(proba[idx])
        else:
            guven = 0.75  # varsayılan

        return TespitSonucu(
            sera_id  = sera_id,
            hastalik = str(tahmin),
            guven    = round(guven, 3),
        )

    def __repr__(self) -> str:
        durum = "hazır" if self._hazir else "KuralFallback"
        return f"HastalikModeli({durum}, yol={self.model_yolu!r})"
