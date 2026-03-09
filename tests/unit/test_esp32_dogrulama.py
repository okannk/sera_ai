"""
ESP32S3Node Sensör Doğrulama Testleri

Kapsam:
  - Sensör konfigürasyonsuz (eski davranış) → doğrulama atlanır
  - Tam veri + konfigürasyon → gecerli_mi True
  - Eksik alan (konfigürasyona göre beklenen) → sentinel → gecerli_mi False
  - Fiziksel sınır dışı değer → sentinel → gecerli_mi False
  - Birden fazla sensör tipi birlikte
  - Konfigürasyon dışı sensör alanı eksikse → sessiz (sorun değil)
  - _dict_to_okuma varsayılan sentinel değerleri
  - settings.py factory sensorler parametresini geçirir
"""
from __future__ import annotations

import pytest

from sera_ai.drivers.esp32_s3 import ESP32S3Node, _SENTINEL
from sera_ai.domain.models import SeraKonfig, SistemKonfig, BitkilProfili


# ── Yardımcı ─────────────────────────────────────────────────────

def node_olustur(sensorler: list) -> ESP32S3Node:
    """Bağlantı gerektirmeyen, sadece doğrulama test edilebilir node."""
    return ESP32S3Node(
        sera_id="s1",
        node_id="esp32_test",
        sensorler=sensorler,
    )


TAM_VERI = {
    "T": 23.5, "H": 70.0, "co2": 950,
    "isik": 500, "toprak": 512, "ph": 6.5, "ec": 1.8,
}

SENSORLER_HEPSI = [
    {"tip": "sht31"},
    {"tip": "mh_z19c"},
    {"tip": "bh1750"},
    {"tip": "kapasitif_nem"},
]


# ── Doğrulama Kapalı (sensorler=[]) ──────────────────────────────

class TestDogrulamaKapali:

    def test_bos_sensorler_dogrulama_yok(self):
        node = node_olustur([])
        # Eksik alanlar bile olsa sentinel konmaz
        eksik_veri = {"T": 23.0}
        sonuc = node._dogrula_ve_doldur(eksik_veri)
        assert sonuc == eksik_veri  # Değişmeden döner

    def test_beklenen_alanlar_bos(self):
        node = node_olustur([])
        assert node._beklenen_alanlar == set()

    def test_dict_to_okuma_varsayilan_sentinel(self):
        """Doğrulama kapalı, alan yok → sentinel → gecerli_mi False."""
        node = node_olustur([])
        okuma = node._dict_to_okuma("s1", {})
        assert not okuma.gecerli_mi


# ── Beklenen Alanlar Hesaplama ────────────────────────────────────

class TestBeklenenAlanlar:

    def test_sht31_T_H_bekler(self):
        node = node_olustur([{"tip": "sht31"}])
        assert {"T", "H"} <= node._beklenen_alanlar

    def test_mh_z19c_co2_bekler(self):
        node = node_olustur([{"tip": "mh_z19c"}])
        assert "co2" in node._beklenen_alanlar

    def test_bh1750_isik_bekler(self):
        node = node_olustur([{"tip": "bh1750"}])
        assert "isik" in node._beklenen_alanlar

    def test_kapasitif_nem_toprak_bekler(self):
        node = node_olustur([{"tip": "kapasitif_nem"}])
        assert "toprak" in node._beklenen_alanlar

    def test_dht22_T_H_bekler(self):
        node = node_olustur([{"tip": "dht22"}])
        assert {"T", "H"} <= node._beklenen_alanlar

    def test_tum_sensorler_tum_alanlar(self):
        node = node_olustur(SENSORLER_HEPSI)
        assert {"T", "H", "co2", "isik", "toprak"} <= node._beklenen_alanlar

    def test_ph_ec_her_zaman_beklenir(self):
        node = node_olustur([{"tip": "sht31"}])
        assert "ph" in node._beklenen_alanlar
        assert "ec" in node._beklenen_alanlar

    def test_bilinmeyen_tip_alan_eklemez(self):
        node = node_olustur([{"tip": "bilinmeyen_sensor"}])
        # Sadece ph, ec (her zaman)
        assert node._beklenen_alanlar == {"ph", "ec"}


# ── Doğrulama Mantığı ────────────────────────────────────────────

class TestDogrulama:

    def test_tam_veri_degismez(self):
        node = node_olustur(SENSORLER_HEPSI)
        sonuc = node._dogrula_ve_doldur(TAM_VERI)
        assert sonuc["T"]      == TAM_VERI["T"]
        assert sonuc["co2"]    == TAM_VERI["co2"]
        assert sonuc["toprak"] == TAM_VERI["toprak"]

    def test_eksik_T_sentinel_olur(self):
        node = node_olustur([{"tip": "sht31"}])
        veri = {**TAM_VERI}
        del veri["T"]
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["T"] == _SENTINEL["T"]

    def test_eksik_co2_sentinel_olur(self):
        node = node_olustur([{"tip": "mh_z19c"}])
        veri = {**TAM_VERI}
        del veri["co2"]
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["co2"] == _SENTINEL["co2"]

    def test_eksik_isik_sentinel_olur(self):
        node = node_olustur([{"tip": "bh1750"}])
        veri = {**TAM_VERI}
        del veri["isik"]
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["isik"] == _SENTINEL["isik"]

    def test_eksik_toprak_sentinel_olur(self):
        node = node_olustur([{"tip": "kapasitif_nem"}])
        veri = {**TAM_VERI}
        del veri["toprak"]
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["toprak"] == _SENTINEL["toprak"]

    def test_aralik_disi_T_sentinel_olur(self):
        """T=70 → maksimum 60°C dışında → sentinel."""
        node = node_olustur([{"tip": "sht31"}])
        veri = {**TAM_VERI, "T": 70.0}
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["T"] == _SENTINEL["T"]

    def test_aralik_disi_co2_sentinel_olur(self):
        """co2=100 → minimum 300 altında → sentinel."""
        node = node_olustur([{"tip": "mh_z19c"}])
        veri = {**TAM_VERI, "co2": 100}
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["co2"] == _SENTINEL["co2"]

    def test_aralik_disi_H_sentinel_olur(self):
        """H=110 → maksimum 100 üstünde → sentinel."""
        node = node_olustur([{"tip": "sht31"}])
        veri = {**TAM_VERI, "H": 110.0}
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["H"] == _SENTINEL["H"]

    def test_konfigurasyonda_olmayan_alan_eksikse_sorun_yok(self):
        """Sadece sht31 konfigüre, co2 JSON'da yok → sentinel yok (beklenmiyordu)."""
        node = node_olustur([{"tip": "sht31"}])
        veri = {"T": 23.0, "H": 70.0, "ph": 6.5, "ec": 1.8}
        sonuc = node._dogrula_ve_doldur(veri)
        # co2 alanı dokunulmaz (konfigürasyon dışı)
        assert "co2" not in sonuc or sonuc.get("co2") == veri.get("co2")

    def test_birden_fazla_gecersiz_alan(self):
        node = node_olustur(SENSORLER_HEPSI)
        veri = {**TAM_VERI, "T": 999.0, "co2": -1}
        sonuc = node._dogrula_ve_doldur(veri)
        assert sonuc["T"]   == _SENTINEL["T"]
        assert sonuc["co2"] == _SENTINEL["co2"]
        # Geçerli alanlar dokunulmaz
        assert sonuc["H"] == TAM_VERI["H"]


# ── SensorOkuma.gecerli_mi Entegrasyonu ──────────────────────────

class TestGecerliMiEntegrasyon:

    def test_tam_veri_gecerli(self):
        node = node_olustur(SENSORLER_HEPSI)
        sonuc = node._dogrula_ve_doldur(TAM_VERI)
        okuma = node._dict_to_okuma("s1", sonuc)
        assert okuma.gecerli_mi

    def test_eksik_alan_gecersiz(self):
        node = node_olustur([{"tip": "sht31"}, {"tip": "mh_z19c"}])
        veri = {**TAM_VERI}
        del veri["T"]
        sonuc = node._dogrula_ve_doldur(veri)
        okuma = node._dict_to_okuma("s1", sonuc)
        assert not okuma.gecerli_mi

    def test_aralik_disi_gecersiz(self):
        node = node_olustur([{"tip": "mh_z19c"}])
        veri = {**TAM_VERI, "co2": 0}  # 0 < 300 → sentinel → gecerli_mi False
        sonuc = node._dogrula_ve_doldur(veri)
        okuma = node._dict_to_okuma("s1", sonuc)
        assert not okuma.gecerli_mi

    def test_dogrulama_kapali_tam_veri_gecerli(self):
        node = node_olustur([])
        okuma = node._dict_to_okuma("s1", TAM_VERI)
        assert okuma.gecerli_mi


# ── Factory Entegrasyonu ──────────────────────────────────────────

class TestFactoryEntegrasyon:

    def test_saha_node_olustur_sensorleri_gecer(self):
        """settings.saha_node_olustur() sensorler= parametresini geçirmeli."""
        from sera_ai.config.settings import saha_node_olustur

        profil = BitkilProfili(
            isim="Domates", min_T=15, max_T=30, opt_T=23,
            min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
        )
        sistem = SistemKonfig(
            seralar=[], profiller={"Domates": profil}
        )
        sera = SeraKonfig(
            id="s1", isim="Sera A", alan_m2=500, bitki="Domates",
            saha_donanim="esp32_s3",
            sensorler=[{"tip": "sht31"}, {"tip": "mh_z19c"}],
        )
        node = saha_node_olustur(sera, sistem)

        assert isinstance(node, ESP32S3Node)
        assert len(node._sensorler) == 2
        assert {"T", "H", "co2"} <= node._beklenen_alanlar
