"""
SensorSaglikAnalizi unit testleri.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from sera_ai.domain.models import SensorSaglik, SensorDurum
from sera_ai.infrastructure.analytics.sensor_saglik import SensorSaglikAnalizi


@pytest.fixture
def analiz():
    return SensorSaglikAnalizi()


# ── pik_tespiti ────────────────────────────────────────────────

class TestPikTespiti:
    def test_yetersiz_olcum_pik_degil(self, analiz):
        assert analiz.pik_tespiti([23.0, 23.1], 50.0) is False

    def test_normal_deger_pik_degil(self, analiz):
        assert analiz.pik_tespiti([23.0] * 10, 23.1) is False

    def test_z_score_buyuk_pik(self, analiz):
        olcumler = [23.0, 23.1, 23.0, 23.1, 23.0, 23.1, 23.0, 23.1, 23.0, 23.1]
        assert analiz.pik_tespiti(olcumler, 28.0) is True

    def test_yuzde_30_sapma_pik(self, analiz):
        assert analiz.pik_tespiti([100.0] * 10, 140.0) is True

    def test_yuzde_10_sapma_pik_degil(self, analiz):
        assert analiz.pik_tespiti([100.0] * 10, 110.0) is False

    def test_sifir_ortalama_pik_atlama(self, analiz):
        # std=0, z-score hesaplanamaz → False
        assert analiz.pik_tespiti([0.0] * 10, 1.0) is False

    def test_genis_dagilim_hassasiyeti(self, analiz):
        olcumler = [10.0, 20.0, 15.0, 25.0, 12.0, 22.0, 18.0, 14.0, 16.0, 19.0]
        # ort~17, std~4.5 → 27 ≈ z=2.2 → pik değil ama %30+ sapma kontrolü devreye girebilir
        # 27 - 17 = 10, 10/17 ≈ 0.59 → %30 sapma → pik
        assert analiz.pik_tespiti(olcumler, 27.0) is True

    def test_tek_olcum_hafif_sapma(self, analiz):
        olcumler = [50.0] * 10
        assert analiz.pik_tespiti(olcumler, 52.0) is False


# ── donmus_deger_tespiti ───────────────────────────────────────

class TestDonmusDeger:
    def test_yetersiz_olcum_donmus_degil(self, analiz):
        assert analiz.donmus_deger_tespiti([23.0] * 4) is False

    def test_ayni_deger_donmus(self, analiz):
        assert analiz.donmus_deger_tespiti([23.0] * 20) is True

    def test_tolerans_icinde_donmus(self, analiz):
        olcumler = [23.0, 23.05, 23.1, 23.0, 23.05] + [23.0] * 15
        assert analiz.donmus_deger_tespiti(olcumler) is True

    def test_degisen_deger_donmus_degil(self, analiz):
        # Son 5 elemanın da farklı olması gerekiyor (test son 5'e bakıyor)
        olcumler = [23.0, 23.5, 24.0, 23.8, 23.2,
                    23.4, 23.6, 23.1, 23.7, 23.3,
                    23.5, 23.2, 23.8, 23.1, 23.9,
                    23.5, 23.0, 23.7, 23.4, 23.6]
        assert analiz.donmus_deger_tespiti(olcumler) is False

    def test_bos_liste_donmus_degil(self, analiz):
        assert analiz.donmus_deger_tespiti([]) is False

    def test_tolerans_icinde_net(self, analiz):
        # 0.05 aralık → açıkça ≤ 0.1 → donmuş
        olcumler = [23.0, 23.05, 23.02, 23.08, 23.03]
        assert analiz.donmus_deger_tespiti(olcumler) is True

    def test_tolerans_ustunde_donmus_degil(self, analiz):
        # 23.0 ve 23.2 → aralik=0.2 > 0.1 → donmuş değil
        olcumler = [23.0, 23.2, 23.0, 23.2, 23.0]
        assert analiz.donmus_deger_tespiti(olcumler) is False


# ── fiziksel_sinir_kontrolu ────────────────────────────────────

class TestFizikselSinir:
    def test_sicaklik_normal(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("sicaklik", 23.0) is True

    def test_sicaklik_asiri_yuksek(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("sicaklik", 100.0) is False

    def test_sicaklik_asiri_dusuk(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("sicaklik", -50.0) is False

    def test_sicaklik_sinir_degerleri(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("sicaklik", -40.0) is True
        assert analiz.fiziksel_sinir_kontrolu("sicaklik", 85.0) is True

    def test_nem_normal(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("nem", 68.0) is True

    def test_nem_sinir_ustunde(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("nem", 101.0) is False

    def test_co2_normal(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("co2", 800.0) is True

    def test_co2_cok_dusuk(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("co2", 200.0) is False

    def test_co2_cok_yuksek(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("co2", 6000.0) is False

    def test_isik_normal(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("isik", 4500.0) is True

    def test_toprak_sinirda(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("toprak", 0.0) is True
        assert analiz.fiziksel_sinir_kontrolu("toprak", 100.0) is True

    def test_toprak_sinir_disi(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("toprak", -1.0) is False
        assert analiz.fiziksel_sinir_kontrolu("toprak", 101.0) is False

    def test_bilinmeyen_tip_gecerli(self, analiz):
        assert analiz.fiziksel_sinir_kontrolu("bilinmeyen", 9999.0) is True


# ── ardisik_hata_kontrolu ──────────────────────────────────────

class TestArdisikHata:
    def test_0_hata_normal(self, analiz):
        assert analiz.ardisik_hata_kontrolu(0) == SensorSaglik.NORMAL

    def test_2_hata_normal(self, analiz):
        assert analiz.ardisik_hata_kontrolu(2) == SensorSaglik.NORMAL

    def test_3_hata_uyari(self, analiz):
        assert analiz.ardisik_hata_kontrolu(3) == SensorSaglik.UYARI

    def test_9_hata_uyari(self, analiz):
        assert analiz.ardisik_hata_kontrolu(9) == SensorSaglik.UYARI

    def test_10_hata_arizali(self, analiz):
        assert analiz.ardisik_hata_kontrolu(10) == SensorSaglik.ARIZALI

    def test_50_hata_arizali(self, analiz):
        assert analiz.ardisik_hata_kontrolu(50) == SensorSaglik.ARIZALI


# ── saglik_skoru ───────────────────────────────────────────────

class TestSaglikSkoru:
    def _durum(self, saglik, pik=0, hata=0):
        return SensorDurum(
            sensor_tipi="SHT31", son_deger=23.0,
            saglik=saglik, aciklama="test",
            son_gecerli_okuma=datetime.now(),
            ardisik_hata_sayisi=hata,
            pik_sayisi_son_1saat=pik,
        )

    def test_normal_tam_skor(self, analiz):
        assert analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL)) == 1.0

    def test_arizali_sifir_skor(self, analiz):
        assert analiz.saglik_skoru(self._durum(SensorSaglik.ARIZALI)) == 0.0

    def test_uyari_skor_araliginda(self, analiz):
        s = analiz.saglik_skoru(self._durum(SensorSaglik.UYARI))
        assert 0.0 < s <= 0.70

    def test_donmus_skor_araliginda(self, analiz):
        s = analiz.saglik_skoru(self._durum(SensorSaglik.DONMUS))
        assert 0.0 < s <= 0.40

    def test_pik_ceza(self, analiz):
        s1 = analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL, pik=0))
        s2 = analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL, pik=5))
        assert s2 < s1

    def test_hata_ceza(self, analiz):
        s1 = analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL, hata=0))
        s2 = analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL, hata=5))
        assert s2 < s1

    def test_skor_0_1_araliginda_her_durum(self, analiz):
        for saglik in SensorSaglik:
            s = analiz.saglik_skoru(self._durum(saglik, pik=20, hata=20))
            assert 0.0 <= s <= 1.0, f"{saglik}: {s}"

    def test_max_ceza_sifir_alti_olmaz(self, analiz):
        s = analiz.saglik_skoru(self._durum(SensorSaglik.NORMAL, pik=100, hata=100))
        assert s >= 0.0


# ── analiz_et ─────────────────────────────────────────────────

class TestAnalizEt:
    def test_arizali_cok_hata(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [], ardisik_hata=10)
        assert durum.saglik == SensorSaglik.ARIZALI
        assert durum.sensor_tipi == "SHT31"

    def test_kalibre_hatasi(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [200.0] * 5)
        assert durum.saglik == SensorSaglik.KALIBRE_HATASI

    def test_donmus_deger(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [23.0] * 20)
        assert durum.saglik == SensorSaglik.DONMUS

    def test_pik_tespiti(self, analiz):
        # 9 normal + 1 büyük sıçrama → son değer pik
        olcumler = [23.0] * 9 + [50.0]
        durum = analiz.analiz_et("SHT31", "sicaklik", olcumler)
        assert durum.saglik == SensorSaglik.PIK

    def test_uyari_hata(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [23.0, 23.1, 23.2],
                                  ardisik_hata=5)
        assert durum.saglik == SensorSaglik.UYARI

    def test_uyari_cok_pik(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [23.0, 23.1, 23.2],
                                  pik_sayisi_1sa=6)
        assert durum.saglik == SensorSaglik.UYARI

    def test_normal_saglam_olcum(self, analiz):
        olcumler = [23.0 + i * 0.1 for i in range(10)]
        durum = analiz.analiz_et("SHT31", "sicaklik", olcumler)
        assert durum.saglik == SensorSaglik.NORMAL

    def test_sensor_tipi_dogru(self, analiz):
        durum = analiz.analiz_et("MH-Z19C", "co2", [900.0] * 5)
        assert durum.sensor_tipi == "MH-Z19C"

    def test_bos_olcum_listesi_normal(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [])
        assert durum.saglik == SensorSaglik.NORMAL

    def test_to_dict_yapisi(self, analiz):
        durum = analiz.analiz_et("SHT31", "sicaklik", [23.0, 23.1, 23.2])
        d = durum.to_dict()
        assert "sensor_tipi" in d
        assert "saglik" in d
        assert "aciklama" in d
        assert "son_gecerli_okuma" in d
        assert isinstance(d["saglik"], str)

    def test_once_arizali_sonra_kalibre_kalibre_olmaz(self, analiz):
        # 10+ hata → ARIZALI önce gelir (200°C dahi olsa)
        durum = analiz.analiz_et("SHT31", "sicaklik", [200.0], ardisik_hata=10)
        assert durum.saglik == SensorSaglik.ARIZALI

    def test_co2_fiziksel_sinir(self, analiz):
        durum = analiz.analiz_et("MH-Z19C", "co2", [200.0])
        assert durum.saglik == SensorSaglik.KALIBRE_HATASI

    def test_bilinmeyen_sensor_tipi(self, analiz):
        durum = analiz.analiz_et("OzelSensor", "bilinmeyen", [9999.0, 10000.0, 9998.0])
        assert durum.saglik == SensorSaglik.NORMAL  # Bilinmeyen → fiziksel sınır yok


# ── alarm_kontrol ─────────────────────────────────────────────

class TestAlarmKontrol:
    def _durum(self, saglik, pik=0, hata=0, son_gecerli=None):
        return SensorDurum(
            sensor_tipi="SHT31", son_deger=23.0,
            saglik=saglik, aciklama="test",
            son_gecerli_okuma=son_gecerli or datetime.now(),
            ardisik_hata_sayisi=hata,
            pik_sayisi_son_1saat=pik,
        )

    def test_normal_alarm_yok(self, analiz):
        assert analiz.alarm_kontrol(self._durum(SensorSaglik.NORMAL)) == []

    def test_arizali_kritik_alarm(self, analiz):
        alarmlar = analiz.alarm_kontrol(self._durum(SensorSaglik.ARIZALI, hata=10))
        assert any(a["tur"] == "SENSOR_ARIZASI" for a in alarmlar)
        assert any(a["seviye"] == "KRITIK" for a in alarmlar)

    def test_cok_pik_guvenilmez_alarm(self, analiz):
        alarmlar = analiz.alarm_kontrol(self._durum(SensorSaglik.NORMAL, pik=6))
        assert any(a["tur"] == "SENSOR_GUVENILMEZ" for a in alarmlar)

    def test_5_pik_alarm_yok(self, analiz):
        alarmlar = analiz.alarm_kontrol(self._durum(SensorSaglik.NORMAL, pik=5))
        assert not any(a["tur"] == "SENSOR_GUVENILMEZ" for a in alarmlar)

    def test_donmus_10dk_alarm(self, analiz):
        eski_zaman = datetime.now() - timedelta(minutes=15)
        alarmlar = analiz.alarm_kontrol(
            self._durum(SensorSaglik.DONMUS, son_gecerli=eski_zaman)
        )
        assert any(a["tur"] == "SENSOR_DONMUS" for a in alarmlar)

    def test_donmus_2dk_alarm_yok(self, analiz):
        yakin_zaman = datetime.now() - timedelta(minutes=2)
        alarmlar = analiz.alarm_kontrol(
            self._durum(SensorSaglik.DONMUS, son_gecerli=yakin_zaman)
        )
        assert not any(a["tur"] == "SENSOR_DONMUS" for a in alarmlar)

    def test_alarm_mesaj_sensor_tipi_icerir(self, analiz):
        alarmlar = analiz.alarm_kontrol(self._durum(SensorSaglik.ARIZALI, hata=12))
        assert any("SHT31" in a["mesaj"] for a in alarmlar)


# ── rapor_uret ────────────────────────────────────────────────

class TestRaporUret:
    def test_bos_girdi(self, analiz):
        assert analiz.rapor_uret({}) == []

    def test_tek_sensor(self, analiz):
        sonuclar = analiz.rapor_uret({
            "SHT31": {"tip": "sicaklik", "olcumler": [23.0] * 5}
        })
        assert len(sonuclar) == 1
        assert sonuclar[0].sensor_tipi == "SHT31"

    def test_coklu_sensor(self, analiz):
        sonuclar = analiz.rapor_uret({
            "SHT31":   {"tip": "sicaklik", "olcumler": [23.0] * 5},
            "MH-Z19C": {"tip": "co2",     "olcumler": [900.0] * 5},
            "BH1750":  {"tip": "isik",    "olcumler": [4500.0] * 5},
        })
        assert len(sonuclar) == 3

    def test_arizali_sensor_raporlanir(self, analiz):
        sonuclar = analiz.rapor_uret({
            "MH-Z19C": {"tip": "co2", "olcumler": [], "ardisik_hata": 10}
        })
        assert sonuclar[0].saglik == SensorSaglik.ARIZALI

    def test_donmus_sensor_raporlanir(self, analiz):
        sonuclar = analiz.rapor_uret({
            "Kapasitif": {"tip": "toprak", "olcumler": [45.2] * 20}
        })
        assert sonuclar[0].saglik == SensorSaglik.DONMUS
