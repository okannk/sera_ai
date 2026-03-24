"""
Zero-Touch Provisioning Birim Testleri

Kapsam:
  - JWT yardımcı fonksiyonlar (üret / doğrula / süre kontrolü)
  - ProvisioningTalep (to_dict, sure_gecti_mi)
  - ZeroTouchProvisioning (yeni_kayit_bekle, onayla, reddet,
      token_dogrula, bekleyen_listele, durum_al)
  - MQTTBrokerAuth JWT token desteği (güncellenmiş)
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from sera_ai.infrastructure.provisioning.zero_touch import (
    ZeroTouchProvisioning,
    ProvisioningTalep,
    jwt_uret,
    jwt_dogrula,
    _OTUZ_YIL_SN,
)


_GIZLI = "test-gizli-123"


# ─────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def repo(tmp_path):
    from sera_ai.infrastructure.repositories.cihaz_repository import SQLiteCihazRepository
    return SQLiteCihazRepository(str(tmp_path / "test.db"))


@pytest.fixture
def prov(repo):
    return ZeroTouchProvisioning(repo, jwt_secret=_GIZLI, tesis_kodu="IST01")


# ─────────────────────────────────────────────────────────────
# JWT yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────

class TestJWT:
    def test_uret_ve_dogrula(self):
        payload = {"sub": "test", "data": 42}
        token = jwt_uret(payload, _GIZLI)
        sonuc = jwt_dogrula(token, _GIZLI)
        assert sonuc is not None
        assert sonuc["sub"] == "test"
        assert sonuc["data"] == 42

    def test_yanlis_secret(self):
        token = jwt_uret({"sub": "test"}, _GIZLI)
        assert jwt_dogrula(token, "yanlis-gizli") is None

    def test_bozulmus_token(self):
        token = jwt_uret({"sub": "test"}, _GIZLI)
        bozuk = token[:-3] + "XXX"
        assert jwt_dogrula(bozuk, _GIZLI) is None

    def test_suresi_dolmus(self):
        now = int(time.time())
        payload = {"sub": "test", "iat": now - 100, "exp": now - 1}
        token = jwt_uret(payload, _GIZLI)
        assert jwt_dogrula(token, _GIZLI) is None

    def test_30_yil_gecerli(self):
        now = int(time.time())
        payload = {"sub": "test", "exp": now + _OTUZ_YIL_SN}
        token = jwt_uret(payload, _GIZLI)
        sonuc = jwt_dogrula(token, _GIZLI)
        assert sonuc is not None

    def test_gecersiz_format(self):
        assert jwt_dogrula("bu.bir.token.degil.ama.uzun", _GIZLI) is None
        assert jwt_dogrula("", _GIZLI) is None
        assert jwt_dogrula("sadece", _GIZLI) is None

    def test_payload_tam_donuyor(self):
        payload = {"sub": "X", "cihaz_id": "SERA-IST01-001", "sera_id": "s1"}
        token = jwt_uret(payload, _GIZLI)
        sonuc = jwt_dogrula(token, _GIZLI)
        assert sonuc["cihaz_id"] == "SERA-IST01-001"
        assert sonuc["sera_id"] == "s1"


# ─────────────────────────────────────────────────────────────
# ProvisioningTalep
# ─────────────────────────────────────────────────────────────

class TestProvisioningTalep:
    def _talep(self, dakika_once=0) -> ProvisioningTalep:
        return ProvisioningTalep(
            talep_id="t-001",
            mac_adresi="A4:CF:12:78:5B:09",
            sera_id="s1",
            baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0",
            talep_zamani=datetime.now() - timedelta(minutes=dakika_once),
        )

    def test_to_dict_anahtarlar(self):
        t = self._talep()
        d = t.to_dict()
        for k in ("talep_id", "mac_adresi", "sera_id", "baglanti_tipi",
                  "firmware_versiyon", "talep_zamani", "durum", "cihaz_id"):
            assert k in d

    def test_varsayilan_durum_beklemede(self):
        t = self._talep()
        assert t.durum == "BEKLEMEDE"
        assert t.to_dict()["durum"] == "BEKLEMEDE"

    def test_sure_gecti_mi_false_yeni(self):
        t = self._talep(dakika_once=5)
        assert t.sure_gecti_mi(dakika=30) is False

    def test_sure_gecti_mi_true_eski(self):
        t = self._talep(dakika_once=60)
        assert t.sure_gecti_mi(dakika=30) is True


# ─────────────────────────────────────────────────────────────
# ZeroTouchProvisioning
# ─────────────────────────────────────────────────────────────

class TestZeroTouchProvisioning:
    def test_yeni_kayit_bekle(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1", "WiFi")
        assert t.durum == "BEKLEMEDE"
        assert t.mac_adresi == "AA:BB:CC:DD:EE:FF"
        assert t.sera_id == "s1"

    def test_talep_id_benzersiz(self, prov):
        t1 = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:01", "s1")
        t2 = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:02", "s1")
        assert t1.talep_id != t2.talep_id

    def test_bekleyen_listele(self, prov):
        prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:01", "s1")
        prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:02", "s2")
        assert len(prov.bekleyen_listele()) == 2

    def test_onayla_basarili(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1", "WiFi")
        sonuc = prov.onayla(t.talep_id)
        assert sonuc is not None
        cihaz, token = sonuc
        assert cihaz.sera_id == "s1"
        assert cihaz.tesis_kodu == "IST01"
        assert cihaz.cihaz_id == "SERA-IST01-001"
        assert len(token) > 20

    def test_onayla_durum_degisir(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.onayla(t.talep_id)
        assert t.durum == "ONAYLANDI"

    def test_onayla_bekleyen_listeden_cikar(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.onayla(t.talep_id)
        assert len(prov.bekleyen_listele()) == 0

    def test_onayla_cihaz_db_kaydedildi(self, prov, repo):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        cihaz, _ = prov.onayla(t.talep_id)
        assert repo.bul(cihaz.cihaz_id) is not None

    def test_onayla_tekrar_olmayan(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.onayla(t.talep_id)
        assert prov.onayla(t.talep_id) is None  # zaten işlendi

    def test_onayla_olmayan_talep(self, prov):
        assert prov.onayla("olmayan-talep-id") is None

    def test_reddet_basarili(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        assert prov.reddet(t.talep_id) is True
        assert t.durum == "REDDEDILDI"

    def test_reddet_bekleyen_listeden_cikar(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.reddet(t.talep_id)
        assert len(prov.bekleyen_listele()) == 0

    def test_reddet_olmayan(self, prov):
        assert prov.reddet("olmayan") is False

    def test_reddet_tekrar_olmayan(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.reddet(t.talep_id)
        assert prov.reddet(t.talep_id) is False

    def test_durum_al_beklemede(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        d = prov.durum_al(t.talep_id)
        assert d is not None
        assert d["durum"] == "BEKLEMEDE"
        assert "token" not in d

    def test_durum_al_onaylandi_token_var(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        prov.onayla(t.talep_id)
        d = prov.durum_al(t.talep_id)
        assert d["durum"] == "ONAYLANDI"
        assert "token" in d
        assert len(d["token"]) > 20
        assert "cihaz_id" in d

    def test_durum_al_olmayan(self, prov):
        assert prov.durum_al("olmayan") is None

    def test_token_dogrula_gecerli(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        cihaz, token = prov.onayla(t.talep_id)
        dogrulanmis = prov.token_dogrula(token)
        assert dogrulanmis is not None
        assert dogrulanmis.cihaz_id == cihaz.cihaz_id

    def test_token_dogrula_gecersiz(self, prov):
        assert prov.token_dogrula("gecersiz.token.burada") is None

    def test_token_dogrula_yanlis_secret(self, prov, repo):
        from sera_ai.infrastructure.provisioning.zero_touch import ZeroTouchProvisioning
        prov2 = ZeroTouchProvisioning(repo, jwt_secret="farkli-gizli", tesis_kodu="IST01")
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        _, token = prov.onayla(t.talep_id)
        # Farklı secret ile doğrulama başarısız olmalı
        assert prov2.token_dogrula(token) is None

    def test_token_yenile(self, prov):
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        cihaz, token1 = prov.onayla(t.talep_id)
        token2 = prov.token_yenile(cihaz.cihaz_id)
        assert token2 is not None
        # Her iki token da geçerli (aynı saniyede üretilirlerse değerleri aynı olabilir)
        assert prov.token_dogrula(token1) is not None
        assert prov.token_dogrula(token2) is not None
        # Her iki token da aynı cihaza ait
        c1 = prov.token_dogrula(token1)
        c2 = prov.token_dogrula(token2)
        assert c1.cihaz_id == c2.cihaz_id == cihaz.cihaz_id

    def test_token_yenile_olmayan_cihaz(self, prov):
        assert prov.token_yenile("OLMAYAN") is None

    def test_sira_no_sirayla_artar(self, prov):
        t1 = prov.yeni_kayit_bekle("MAC1", "s1")
        t2 = prov.yeni_kayit_bekle("MAC2", "s2")
        c1, _ = prov.onayla(t1.talep_id)
        c2, _ = prov.onayla(t2.talep_id)
        assert c1.cihaz_id == "SERA-IST01-001"
        assert c2.cihaz_id == "SERA-IST01-002"


# ─────────────────────────────────────────────────────────────
# MQTTBrokerAuth — JWT token desteği
# ─────────────────────────────────────────────────────────────

class TestMQTTBrokerAuthJWT:
    def test_jwt_ile_kimlik_dogrula(self, prov, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        cihaz, token = prov.onayla(t.talep_id)
        auth = MQTTBrokerAuth(repo, zero_touch=prov)
        assert auth.kimlik_dogrula(cihaz.cihaz_id, token) is True

    def test_yanlis_cihaz_id_ile_token(self, prov, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        t = prov.yeni_kayit_bekle("AA:BB:CC:DD:EE:FF", "s1")
        _, token = prov.onayla(t.talep_id)
        auth = MQTTBrokerAuth(repo, zero_touch=prov)
        assert auth.kimlik_dogrula("YANLIS-CIHAZ-ID", token) is False

    def test_gecersiz_token(self, prov, repo):
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        auth = MQTTBrokerAuth(repo, zero_touch=prov)
        assert auth.kimlik_dogrula("SERA-IST01-001", "gecersiz.jwt.token") is False

    def test_zero_touch_olmadan_sifre_hash_calisir(self, repo):
        """Geriye dönük uyumluluk: zero_touch=None → şifre hash yöntemi."""
        import hashlib, secrets
        from sera_ai.infrastructure.mqtt.broker_auth import MQTTBrokerAuth
        from sera_ai.domain.models import CihazKimlik, CihazKayit
        from datetime import datetime

        salt = secrets.token_hex(16)
        sifre = "test123"
        h = hashlib.sha256((salt + sifre).encode()).hexdigest()

        cihaz = CihazKimlik(
            cihaz_id="SERA-TST-001", tesis_kodu="TST", sera_id="s1",
            seri_no="X", mac_adresi="", baglanti_tipi="WiFi",
            firmware_versiyon="1.0.0", son_gorulen=datetime.now(), aktif=True,
        )
        kayit = CihazKayit(
            cihaz_id="SERA-TST-001",
            sifre_hash=f"{salt}:{h}",
            izin_verilen_konular=[],
        )
        repo.kayit_et(cihaz, kayit)
        auth = MQTTBrokerAuth(repo)  # zero_touch=None
        assert auth.kimlik_dogrula("SERA-TST-001", sifre) is True
        assert auth.kimlik_dogrula("SERA-TST-001", "yanlis") is False
