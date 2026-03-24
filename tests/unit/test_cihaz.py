"""
Cihaz Yönetimi Birim Testleri

Kapsam:
  - CihazKimlik.durum() — bağlantı durumu hesabı
  - CihazKimlik.to_dict() — serializasyon
  - SQLiteCihazRepository — CRUD işlemleri
  - MQTTBrokerAuth — kimlik doğrulama ve konu kontrolü
  - BaglantiYoneticisi — kalp atışı ve durum takibi
  - CihazProvisioning — cihaz oluşturma ve şifre sıfırlama
  - broker_auth yardımcı fonksiyonlar
"""
from __future__ import annotations

import hashlib
import secrets
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sera_ai.domain.models import CihazKimlik, CihazKayit


# ─────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────

def _cihaz(cihaz_id="SERA-IST01-001", sera_id="s1", dakika_once=0) -> CihazKimlik:
    return CihazKimlik(
        cihaz_id=cihaz_id,
        tesis_kodu="IST01",
        sera_id=sera_id,
        seri_no="A1B2C3D4E5F6",
        mac_adresi="A4:CF:12:78:5B:01",
        baglanti_tipi="WiFi",
        firmware_versiyon="1.0.0",
        son_gorulen=datetime.now() - timedelta(minutes=dakika_once),
        aktif=True,
    )


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(tmp_db):
    from sera_ai.infrastructure.repositories.cihaz_repository import SQLiteCihazRepository
    return SQLiteCihazRepository(tmp_db)


@pytest.fixture
def provisioning(repo):
    from sera_ai.infrastructure.provisioning.cihaz_provisioning import CihazProvisioning
    return CihazProvisioning(repo, mqtt_host="test.local", mqtt_port=1883)


# ─────────────────────────────────────────────────────────────
# CihazKimlik.durum()
# ─────────────────────────────────────────────────────────────

class TestCihazKimlikDurum:
    def test_cevrimici_son_10s(self):
        c = _cihaz()
        assert c.durum() == "CEVRIMICI"

    def test_gecikmeli_60s_once(self):
        c = CihazKimlik(
            cihaz_id="SERA-IST01-001", tesis_kodu="IST01", sera_id="s1",
            seri_no="X", mac_adresi="", baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0",
            son_gorulen=datetime.now() - timedelta(seconds=60),
            aktif=True,
        )
        assert c.durum() == "GECIKMELI"

    def test_kopuk_2dk_once(self):
        c = CihazKimlik(
            cihaz_id="SERA-IST01-001", tesis_kodu="IST01", sera_id="s1",
            seri_no="X", mac_adresi="", baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0",
            son_gorulen=datetime.now() - timedelta(minutes=2),
            aktif=True,
        )
        assert c.durum() == "KOPUK"

    def test_esik_29s_cevrimici(self):
        c = CihazKimlik(
            cihaz_id="X", tesis_kodu="T", sera_id="s1", seri_no="X",
            mac_adresi="", baglanti_tipi="WiFi", firmware_versiyon="1.0.0",
            son_gorulen=datetime.now() - timedelta(seconds=29), aktif=True,
        )
        assert c.durum() == "CEVRIMICI"

    def test_esik_30s_gecikmeli(self):
        c = CihazKimlik(
            cihaz_id="X", tesis_kodu="T", sera_id="s1", seri_no="X",
            mac_adresi="", baglanti_tipi="WiFi", firmware_versiyon="1.0.0",
            son_gorulen=datetime.now() - timedelta(seconds=31), aktif=True,
        )
        assert c.durum() == "GECIKMELI"


class TestCihazKimlikToDict:
    def test_to_dict_anahtarlar(self):
        c = _cihaz()
        d = c.to_dict()
        for k in ("cihaz_id", "tesis_kodu", "sera_id", "seri_no", "mac_adresi",
                  "baglanti_tipi", "firmware_versiyon", "son_gorulen", "aktif", "durum"):
            assert k in d

    def test_to_dict_durum_dahil(self):
        c = _cihaz()
        d = c.to_dict()
        assert d["durum"] == "CEVRIMICI"

    def test_to_dict_son_gorulen_string(self):
        c = _cihaz()
        d = c.to_dict()
        assert isinstance(d["son_gorulen"], str)
        # ISO-8601 formatında olmalı
        datetime.fromisoformat(d["son_gorulen"])


# ─────────────────────────────────────────────────────────────
# SQLiteCihazRepository
# ─────────────────────────────────────────────────────────────

class TestSQLiteCihazRepository:
    def _kayit(self, cihaz_id="SERA-IST01-001", konular=None):
        return CihazKayit(
            cihaz_id=cihaz_id,
            sifre_hash="tuz:hash",
            izin_verilen_konular=konular or ["sera/IST01/s1/sensor"],
        )

    def test_kayit_et_ve_bul(self, repo):
        c = _cihaz()
        k = self._kayit()
        repo.kayit_et(c, k)
        bulunan = repo.bul("SERA-IST01-001")
        assert bulunan is not None
        assert bulunan.cihaz_id == "SERA-IST01-001"
        assert bulunan.sera_id  == "s1"

    def test_bul_yoksa_none(self, repo):
        assert repo.bul("OLMAYAN") is None

    def test_listele_bos(self, repo):
        assert repo.listele() == []

    def test_listele_dolu(self, repo):
        for i in range(3):
            c = _cihaz(cihaz_id=f"SERA-IST01-{i:03d}", sera_id=f"s{i+1}")
            k = self._kayit(cihaz_id=f"SERA-IST01-{i:03d}")
            repo.kayit_et(c, k)
        assert len(repo.listele()) == 3

    def test_tesis_cihaz_sayisi(self, repo):
        assert repo.tesis_cihaz_sayisi("IST01") == 0
        c = _cihaz(); k = self._kayit()
        repo.kayit_et(c, k)
        assert repo.tesis_cihaz_sayisi("IST01") == 1

    def test_son_gorulen_guncelle(self, repo):
        c = _cihaz(); k = self._kayit()
        repo.kayit_et(c, k)
        yeni_zaman = datetime.now() - timedelta(seconds=5)
        repo.son_gorulen_guncelle("SERA-IST01-001", yeni_zaman)
        guncel = repo.bul("SERA-IST01-001")
        assert abs((guncel.son_gorulen - yeni_zaman).total_seconds()) < 1.0

    def test_sil_mevcut(self, repo):
        c = _cihaz(); k = self._kayit()
        repo.kayit_et(c, k)
        assert repo.sil("SERA-IST01-001") is True
        assert repo.bul("SERA-IST01-001") is None

    def test_sil_olmayan(self, repo):
        assert repo.sil("YOK") is False

    def test_sifre_guncelle(self, repo):
        c = _cihaz(); k = self._kayit()
        repo.kayit_et(c, k)
        repo.sifre_guncelle("SERA-IST01-001", "yeni_tuz:yeni_hash")
        kayit = repo.kayit_bul("SERA-IST01-001")
        assert kayit.sifre_hash == "yeni_tuz:yeni_hash"

    def test_kayit_bul_yoksa_none(self, repo):
        assert repo.kayit_bul("YOK") is None

    def test_kayit_bul_konular(self, repo):
        konular = ["sera/IST01/s1/sensor", "cihaz/X/kalp_atisi"]
        c = _cihaz(); k = self._kayit(konular=konular)
        repo.kayit_et(c, k)
        kayit = repo.kayit_bul("SERA-IST01-001")
        assert kayit.izin_verilen_konular == konular

    def test_idempotent_kayit_et(self, repo):
        c = _cihaz(); k = self._kayit()
        repo.kayit_et(c, k)
        repo.kayit_et(c, k)  # tekrar → hata vermemeli
        assert len(repo.listele()) == 1

    def test_listele_tesis_filtresi(self, repo):
        c1 = _cihaz("SERA-IST01-001"); k1 = self._kayit("SERA-IST01-001")
        c2 = _cihaz("SERA-AKD01-001"); k2 = self._kayit("SERA-AKD01-001")
        c2 = CihazKimlik(
            cihaz_id="SERA-AKD01-001", tesis_kodu="AKD01", sera_id="s1",
            seri_no="X", mac_adresi="", baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0", son_gorulen=datetime.now(), aktif=True,
        )
        repo.kayit_et(c1, k1)
        repo.kayit_et(c2, k2)
        assert len(repo.listele(tesis_kodu="IST01")) == 1
        assert len(repo.listele(tesis_kodu="AKD01")) == 1
        assert len(repo.listele()) == 2


# ─────────────────────────────────────────────────────────────
# MQTTBrokerAuth
# ─────────────────────────────────────────────────────────────

class TestMQTTBrokerAuth:
    def _hash_sifre(self, sifre: str) -> str:
        salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + sifre).encode()).hexdigest()
        return f"{salt}:{h}"

    def _ekle(self, repo, cihaz_id="SERA-IST01-001", sifre="gizli123", sera_id="s1"):
        from sera_ai.infrastructure.mqtt.broker_auth import yazma_konulari_olustur
        c = _cihaz(cihaz_id=cihaz_id, sera_id=sera_id)
        k = CihazKayit(
            cihaz_id=cihaz_id,
            sifre_hash=self._hash_sifre(sifre),
            izin_verilen_konular=yazma_konulari_olustur("IST01", sera_id, cihaz_id),
        )
        repo.kayit_et(c, k)
        return c

    def test_dogru_sifre(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        self._ekle(repo, sifre="sifre123")
        auth = MQTTBrokerAuth(repo)
        assert auth.kimlik_dogrula("SERA-IST01-001", "sifre123") is True

    def test_yanlis_sifre(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        self._ekle(repo, sifre="sifre123")
        auth = MQTTBrokerAuth(repo)
        assert auth.kimlik_dogrula("SERA-IST01-001", "yanlis") is False

    def test_olmayan_cihaz(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        auth = MQTTBrokerAuth(repo)
        assert auth.kimlik_dogrula("OLMAYAN", "x") is False

    def test_yazma_izni_sensor_konusu(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        self._ekle(repo)
        auth = MQTTBrokerAuth(repo)
        assert auth.konu_kontrolu("SERA-IST01-001", "sera/IST01/s1/sensor", yazma=True) is True

    def test_yazma_izni_yok_komut(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        self._ekle(repo)
        auth = MQTTBrokerAuth(repo)
        # Komut konusuna yazma yasak (merkez yazar)
        assert auth.konu_kontrolu("SERA-IST01-001", "sera/IST01/s1/komut", yazma=True) is False

    def test_okuma_izni_komut_konusu(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        self._ekle(repo)
        auth = MQTTBrokerAuth(repo)
        assert auth.konu_kontrolu("SERA-IST01-001", "sera/IST01/s1/komut", yazma=False) is True

    def test_pasif_cihaz_izin_yok(self, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth, yazma_konulari_olustur
        c = CihazKimlik(
            cihaz_id="SERA-IST01-002", tesis_kodu="IST01", sera_id="s2",
            seri_no="X", mac_adresi="", baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0", son_gorulen=datetime.now(), aktif=False,
        )
        k = CihazKayit(
            cihaz_id="SERA-IST01-002",
            sifre_hash=self._hash_sifre("x"),
            izin_verilen_konular=yazma_konulari_olustur("IST01", "s2", "SERA-IST01-002"),
        )
        repo.kayit_et(c, k)
        auth = MQTTBrokerAuth(repo)
        assert auth.konu_kontrolu("SERA-IST01-002", "sera/IST01/s2/sensor", yazma=True) is False


# ─────────────────────────────────────────────────────────────
# BaglantiYoneticisi
# ─────────────────────────────────────────────────────────────

class TestBaglantiYoneticisi:
    def test_bilinmiyor_ilk_durumda(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        assert ym.durum("SERA-IST01-001") == "BILINMIYOR"

    def test_cevrimici_kalp_atisi_sonrasi(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("SERA-IST01-001")
        assert ym.durum("SERA-IST01-001") == "CEVRIMICI"

    def test_gecikmeli_60s_once(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("SERA-IST01-001", zaman=datetime.now() - timedelta(seconds=60))
        assert ym.durum("SERA-IST01-001") == "GECIKMELI"

    def test_kopuk_120s_once(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("SERA-IST01-001", zaman=datetime.now() - timedelta(seconds=120))
        assert ym.durum("SERA-IST01-001") == "KOPUK"

    def test_tum_durumlar(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("A")
        ym.kalp_atisi_al("B", zaman=datetime.now() - timedelta(seconds=120))
        d = ym.tum_durumlar()
        assert d["A"] == "CEVRIMICI"
        assert d["B"] == "KOPUK"

    def test_backoff_ilk_deneme(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        assert ym.sonraki_deneme_sn("SERA-IST01-001") == 5

    def test_backoff_artar(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("X")
        ym.kopuk_isle("X")
        assert ym.sonraki_deneme_sn("X") == 15
        ym.kopuk_isle("X")
        assert ym.sonraki_deneme_sn("X") == 30

    def test_backoff_sifirlanir_kalp_atisiyla(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.kalp_atisi_al("X")
        ym.kopuk_isle("X")
        ym.kopuk_isle("X")
        ym.kalp_atisi_al("X")  # sıfırla
        assert ym.sonraki_deneme_sn("X") == 5

    def test_baslat_durdur(self):
        from sera_ai.infrastructure.mqtt.baglanti_yoneticisi import BaglantiYoneticisi
        ym = BaglantiYoneticisi()
        ym.baslat()
        assert ym._calisiyor is True
        ym.durdur()
        assert ym._calisiyor is False


# ─────────────────────────────────────────────────────────────
# CihazProvisioning
# ─────────────────────────────────────────────────────────────

class TestCihazProvisioning:
    def test_yeni_cihaz_olustur_cihaz_id(self, provisioning, repo):
        cihaz, sifre, konfig = provisioning.yeni_cihaz_olustur("IST01", "s1")
        assert cihaz.cihaz_id == "SERA-IST01-001"
        assert cihaz.tesis_kodu == "IST01"
        assert cihaz.sera_id == "s1"

    def test_yeni_cihaz_sira_no_artar(self, provisioning, repo):
        c1, _, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        c2, _, _ = provisioning.yeni_cihaz_olustur("IST01", "s2")
        assert c1.cihaz_id == "SERA-IST01-001"
        assert c2.cihaz_id == "SERA-IST01-002"

    def test_sifre_guclu(self, provisioning):
        _, sifre, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        assert len(sifre) >= 16

    def test_sifre_hash_kaydedildi(self, provisioning, repo):
        cihaz, sifre, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        kayit = repo.kayit_bul(cihaz.cihaz_id)
        assert kayit is not None
        assert ":" in kayit.sifre_hash  # salt:hash formatı

    def test_sifre_dogrulanabilir(self, provisioning, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth, _dogrula_sifre
        cihaz, sifre, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        kayit = repo.kayit_bul(cihaz.cihaz_id)
        assert _dogrula_sifre(sifre, kayit.sifre_hash) is True

    def test_firmware_konfig_anahtarlar(self, provisioning):
        _, _, konfig = provisioning.yeni_cihaz_olustur("IST01", "s1")
        for k in ("cihaz_id", "mqtt_host", "mqtt_port", "mqtt_kullanici",
                  "mqtt_sifre", "sensor_topic", "komut_topic", "kalp_atisi_topic"):
            assert k in konfig

    def test_firmware_konfig_sensor_topic(self, provisioning):
        _, _, konfig = provisioning.yeni_cihaz_olustur("IST01", "s1")
        assert konfig["sensor_topic"] == "sera/IST01/s1/sensor"

    def test_sifre_sifirla(self, provisioning, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import _dogrula_sifre
        cihaz, eski_sifre, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        sonuc = provisioning.sifre_sifirla(cihaz.cihaz_id)
        assert sonuc is not None
        yeni_hash, yeni_sifre = sonuc
        assert yeni_sifre != eski_sifre
        assert _dogrula_sifre(yeni_sifre, yeni_hash) is True

    def test_sifre_sifirla_olmayan(self, provisioning):
        assert provisioning.sifre_sifirla("OLMAYAN") is None

    def test_cihaz_db_kaydedildi(self, provisioning, repo):
        cihaz, _, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        assert repo.bul(cihaz.cihaz_id) is not None

    def test_yazma_konulari_dogrulandi(self, provisioning, repo):
        cihaz, _, _ = provisioning.yeni_cihaz_olustur("IST01", "s1")
        kayit = repo.kayit_bul(cihaz.cihaz_id)
        assert "sera/IST01/s1/sensor" in kayit.izin_verilen_konular
        assert f"cihaz/{cihaz.cihaz_id}/kalp_atisi" in kayit.izin_verilen_konular
