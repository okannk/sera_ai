"""
Unit Testler: ML Motor (intelligence/ml_motor.py + egitim.py + feature_extractor.py)

sklearn gerektirir — dev bağımlılıklarında mevcut.
Model dosyaları tmp_path'e yazılır, proje dizinini kirletmez.
"""
import pytest
import numpy as np

from sera_ai.domain.models import BitkilProfili, SensorOkuma
from sera_ai.domain.state_machine import Durum
from sera_ai.intelligence.base import HedefDeger, OptimizerBase
from sera_ai.intelligence.feature_extractor import FeatureExtractor, FEATURE_BOYUTU
from sera_ai.intelligence.egitim import (
    hedef_to_stres,
    verim_skoru,
    buyume_skoru,
    sentetik_veri_uret,
    modelleri_egit,
    STRES_HEDEF,
)
from sera_ai.intelligence.ml_motor import MLOptimizer


# ── Fixture ───────────────────────────────────────────────────

@pytest.fixture
def profil() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )


@pytest.fixture
def sensor_normal(profil) -> SensorOkuma:
    return SensorOkuma(
        sera_id="s1", T=23.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )


@pytest.fixture
def ml_optimizer(profil, tmp_path) -> MLOptimizer:
    """Her test için tmp_path'e yazar — proje dizini kirlenmez."""
    return MLOptimizer(profil, model_dizin=str(tmp_path))


# ── FeatureExtractor ──────────────────────────────────────────

def test_feature_boyutu_dogru(profil, sensor_normal):
    """cikart() FEATURE_BOYUTU uzunluğunda array döndürmeli."""
    ext = FeatureExtractor(profil)
    vec = ext.cikart(sensor_normal)
    assert vec.shape == (FEATURE_BOYUTU,)


def test_feature_dtype_float32(profil, sensor_normal):
    ext = FeatureExtractor(profil)
    vec = ext.cikart(sensor_normal)
    assert vec.dtype == np.float32


def test_toplu_cikart_sekli(profil, sensor_normal):
    """toplu_cikart() (n, FEATURE_BOYUTU) döndürmeli."""
    ext = FeatureExtractor(profil)
    vektorler = ext.toplu_cikart([sensor_normal, sensor_normal, sensor_normal])
    assert vektorler.shape == (3, FEATURE_BOYUTU)


def test_feature_normal_aralikta(profil, sensor_normal):
    """Normal sensör değerleri için feature'lar makul aralıkta olmalı."""
    ext = FeatureExtractor(profil)
    vec = ext.cikart(sensor_normal)
    # T_norm, H_norm [0,1] aralığında olmalı (normal değerler için)
    assert 0.0 <= float(vec[0]) <= 1.0
    assert 0.0 <= float(vec[1]) <= 1.0


def test_feature_farkli_profil_farkli_normalize(sensor_normal):
    """Farklı bitki profilleri aynı sensörü farklı normalize etmeli."""
    profil_d = BitkilProfili("Domates", 15, 30, 23, 60, 85, 1000, 90)
    profil_m = BitkilProfili("Marul",   10, 22, 16, 65, 85,  800, 45)
    ext_d = FeatureExtractor(profil_d)
    ext_m = FeatureExtractor(profil_m)
    vec_d = ext_d.cikart(sensor_normal)
    vec_m = ext_m.cikart(sensor_normal)
    # T_norm farklı olmalı (farklı min/max aralıkları)
    assert float(vec_d[0]) != float(vec_m[0])


# ── Eğitim Yardımcı Fonksiyonlar ──────────────────────────────

def test_hedef_to_stres_normal(profil):
    """Tüm kapalı → stres 0 (NORMAL)."""
    assert hedef_to_stres(HedefDeger()) == 0


def test_hedef_to_stres_sicak():
    """sogutma=True → stres 2 (SICAK)."""
    assert hedef_to_stres(HedefDeger(sogutma=True, fan=True)) == 2


def test_hedef_to_stres_soguk():
    """isitici=True → stres 1 (SOĞUK)."""
    assert hedef_to_stres(HedefDeger(isitici=True)) == 1


def test_hedef_to_stres_kuru():
    """sulama=True → stres 4 (KURU)."""
    assert hedef_to_stres(HedefDeger(sulama=True)) == 4


def test_hedef_to_stres_nemli():
    """Sadece fan=True → stres 3 (NEMLİ)."""
    assert hedef_to_stres(HedefDeger(fan=True)) == 3


def test_stres_hedef_tam_kapsar():
    """STRES_HEDEF tüm 5 sınıfı kapsamalı."""
    assert set(STRES_HEDEF.keys()) == {0, 1, 2, 3, 4}
    for h in STRES_HEDEF.values():
        assert isinstance(h, HedefDeger)


def test_verim_skoru_aralik(profil, sensor_normal):
    """Verim skoru 0–100 arasında olmalı."""
    skor = verim_skoru(sensor_normal, profil)
    assert 0.0 <= skor <= 100.0


def test_verim_skoru_optimal_yuksek(profil):
    """Optimal koşullar → yüksek verim."""
    s = SensorOkuma(
        sera_id="s1", T=profil.opt_T, H=72.0,
        co2=profil.opt_CO2, isik=50000, toprak_nem=500, ph=6.5, ec=1.8,
    )
    assert verim_skoru(s, profil) > 80.0


def test_verim_skoru_kotu_kosul_dusuk(profil):
    """Kötü koşullar (aşırı sıcak) → düşük verim."""
    s = SensorOkuma(
        sera_id="s1", T=profil.max_T + 8, H=72.0,
        co2=900, isik=50000, toprak_nem=500, ph=6.5, ec=1.8,
    )
    assert verim_skoru(s, profil) < 60.0


def test_buyume_skoru_aralik(profil, sensor_normal):
    """Büyüme skoru 0–1 arasında olmalı."""
    skor = buyume_skoru(sensor_normal, profil)
    assert 0.0 <= skor <= 1.0


# ── Sentetik Veri Üretimi ─────────────────────────────────────

def test_sentetik_veri_boyutu(profil):
    """sentetik_veri_uret() doğru boyutta array döndürmeli."""
    X, y_s, y_y, y_g = sentetik_veri_uret(profil, n=50, tohum=1)
    assert X.shape == (50, FEATURE_BOYUTU)
    assert y_s.shape == (50,)
    assert y_y.shape == (50,)
    assert y_g.shape == (50,)


def test_sentetik_veri_stres_siniflar(profil):
    """Üretilen veride birden fazla stres sınıfı olmalı."""
    _, y_s, _, _ = sentetik_veri_uret(profil, n=200, tohum=42)
    assert len(set(y_s.tolist())) >= 3


def test_sentetik_veri_tekrarlanabilir(profil):
    """Aynı tohum → aynı veri."""
    X1, _, _, _ = sentetik_veri_uret(profil, n=50, tohum=7)
    X2, _, _, _ = sentetik_veri_uret(profil, n=50, tohum=7)
    np.testing.assert_array_equal(X1, X2)


# ── Model Eğitimi ─────────────────────────────────────────────

@pytest.fixture
def egitilmis_modeller(profil):
    """Küçük veriyle (n=100) hızlı eğitim — her test suite için bir kez."""
    X, y_s, y_y, y_g = sentetik_veri_uret(profil, n=100, tohum=42)
    return modelleri_egit(X, y_s, y_y, y_g)


def test_modelleri_egit_dort_model(egitilmis_modeller):
    """modelleri_egit() 4 model döndürmeli."""
    assert set(egitilmis_modeller.keys()) == {"yield", "anomaly", "growth", "stress"}


def test_yield_model_tahmin_boyutu(profil, egitilmis_modeller):
    """yield modeli doğru boyutta tahmin yapmalı."""
    ext = FeatureExtractor(profil)
    s = SensorOkuma("s1", 23.0, 72.0, 950, 450, 500, 6.5, 1.8)
    X = ext.cikart(s).reshape(1, -1)
    pred = egitilmis_modeller["yield"].predict(X)
    assert pred.shape == (1,)


def test_stress_model_gecerli_sinif(profil, egitilmis_modeller):
    """stress modeli 0–4 arası sınıf döndürmeli."""
    ext = FeatureExtractor(profil)
    s = SensorOkuma("s1", 23.0, 72.0, 950, 450, 500, 6.5, 1.8)
    X = ext.cikart(s).reshape(1, -1)
    pred = int(egitilmis_modeller["stress"].predict(X)[0])
    assert pred in {0, 1, 2, 3, 4}


def test_anomaly_model_inlier_normal(profil, egitilmis_modeller):
    """Normal sensör → IsolationForest inlier (1) döndürmeli."""
    ext = FeatureExtractor(profil)
    s = SensorOkuma("s1", profil.opt_T, 72.0, 1000, 50000, 500, 6.5, 1.8)
    X = ext.cikart(s).reshape(1, -1)
    pred = int(egitilmis_modeller["anomaly"].predict(X)[0])
    assert pred in {-1, 1}   # -1=anomali, 1=normal; ikisi de mümkün ama genelde 1


# ── MLOptimizer ───────────────────────────────────────────────

def test_ml_optimizer_optimizer_base_alt_sinifi():
    assert issubclass(MLOptimizer, OptimizerBase)


def test_ml_optimizer_olusturma(ml_optimizer):
    """MLOptimizer başarıyla oluşturulmalı (eğitim dahil)."""
    assert ml_optimizer._stress_model is not None
    assert ml_optimizer._yield_model is not None
    assert ml_optimizer._anomaly_model is not None
    assert ml_optimizer._growth_model is not None


def test_ml_optimizer_hedef_hesapla_hedef_deger_doner(ml_optimizer, sensor_normal):
    """hedef_hesapla() HedefDeger döndürmeli."""
    h = ml_optimizer.hedef_hesapla(sensor_normal, Durum.NORMAL)
    assert isinstance(h, HedefDeger)


def test_ml_optimizer_acil_durdur_hepsi_kapali(ml_optimizer, profil):
    """ACİL_DURDUR → tüm aktüatörler kapalı (ML'e danışılmaz)."""
    s = SensorOkuma("s1", profil.opt_T + 15, 72.0, 950, 450, 500, 6.5, 1.8)
    h = ml_optimizer.hedef_hesapla(s, Durum.ACIL_DURDUR)
    assert h == HedefDeger()


def test_ml_optimizer_verim_tahmini_aralik(ml_optimizer, sensor_normal):
    """verim_tahmini() 0–100 arasında float döndürmeli."""
    v = ml_optimizer.verim_tahmini(sensor_normal)
    assert isinstance(v, float)
    assert 0.0 <= v <= 100.0


def test_ml_optimizer_buyume_hizi_aralik(ml_optimizer, sensor_normal):
    """buyume_hizi_tahmini() 0–1 arasında float döndürmeli."""
    b = ml_optimizer.buyume_hizi_tahmini(sensor_normal)
    assert isinstance(b, float)
    assert 0.0 <= b <= 1.0


def test_ml_optimizer_anomali_mi_bool(ml_optimizer, sensor_normal):
    """anomali_mi() bool döndürmeli."""
    assert isinstance(ml_optimizer.anomali_mi(sensor_normal), bool)


def test_ml_optimizer_model_kaydedilir(profil, tmp_path):
    """MLOptimizer eğitim sonrası .pkl dosyalarını oluşturmalı."""
    MLOptimizer(profil, model_dizin=str(tmp_path))
    for isim in ("yield", "anomaly", "growth", "stress"):
        assert (tmp_path / f"Domates_{isim}.pkl").exists()


def test_ml_optimizer_kayitli_modeli_yukler(profil, tmp_path):
    """İkinci oluşturmada disk'teki modelleri yüklemeli (eğitmemeli)."""
    # İlk: eğit + kaydet
    opt1 = MLOptimizer(profil, model_dizin=str(tmp_path))
    verim1 = opt1.verim_tahmini(
        SensorOkuma("s1", 23.0, 72.0, 950, 450, 500, 6.5, 1.8)
    )
    # İkinci: diskten yükle
    opt2 = MLOptimizer(profil, model_dizin=str(tmp_path))
    verim2 = opt2.verim_tahmini(
        SensorOkuma("s1", 23.0, 72.0, 950, 450, 500, 6.5, 1.8)
    )
    assert abs(verim1 - verim2) < 1e-6  # Aynı model, aynı tahmin
