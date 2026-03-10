"""
Unit Testler: API Kimlik Doğrulama

İki katman test edilir:
  1. check_api_key() — FastAPI'den bağımsız, saf mantık
  2. FastAPI TestClient — auth middleware entegrasyonu
"""
import pytest

from sera_ai.api.auth import check_api_key


# ── check_api_key() unit testleri (framework gerektirmez) ─────

def test_key_tanimli_degil_her_seye_izin_verir():
    """Sistem key'i tanımlı değilse (dev modu) her değere izin ver."""
    assert check_api_key("herhangi-bir-deger", beklenen_key="") is True
    assert check_api_key("",                   beklenen_key="") is True


def test_dogru_key_izin_verir():
    assert check_api_key("gizli-anahtar", beklenen_key="gizli-anahtar") is True


def test_yanlis_key_reddeder():
    assert check_api_key("yanlis", beklenen_key="dogru-anahtar") is False


def test_bos_key_gonderilmis_reddeder():
    """Header hiç gönderilmemiş → boş string → reddet."""
    assert check_api_key("", beklenen_key="gizli") is False


def test_buyuk_kucuk_harf_duyarli():
    """'Gizli' != 'gizli' — key case-sensitive."""
    assert check_api_key("Gizli", beklened_key := "gizli") is False


# ── FastAPI TestClient testleri ───────────────────────────────

@pytest.fixture
def api_key_ile():
    """X-API-Key korumalı FastAPI test client'ı."""
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="test-anahtar-123")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def api_key_siz():
    """Key tanımlı olmayan FastAPI test client'ı (dev modu)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="")
    return TestClient(app, raise_server_exceptions=False)


def test_key_olmadan_401(api_key_ile):
    """Key zorunluyken header gönderilmezse 401."""
    r = api_key_ile.get("/api/v1/seralar")
    assert r.status_code == 401


def test_yanlis_key_401(api_key_ile):
    """Yanlış key → 401."""
    r = api_key_ile.get("/api/v1/seralar", headers={"X-API-Key": "yanlis-anahtar"})
    assert r.status_code == 401


def test_dogru_key_200(api_key_ile):
    """Doğru key → 200."""
    r = api_key_ile.get("/api/v1/seralar", headers={"X-API-Key": "test-anahtar-123"})
    assert r.status_code == 200


def test_saglik_auth_gerektirmez(api_key_ile):
    """/api/v1/sistem/saglik auth olmadan erişilebilir."""
    r = api_key_ile.get("/api/v1/sistem/saglik")
    assert r.status_code in (200, 503)


def test_key_siz_modda_auth_yok(api_key_siz):
    """Key tanımlı değilse tüm endpoint'ler açık (dev modu)."""
    r = api_key_siz.get("/api/v1/seralar")
    assert r.status_code == 200


def test_401_yanit_formati(api_key_ile):
    """401 yanıtı {"success": false, "hata": ..., "kod": ...} formatında gelmeli."""
    r = api_key_ile.get("/api/v1/seralar")
    veri = r.json()
    assert veri["success"] is False
    assert "hata" in veri
    assert veri["kod"] == "YETKISIZ"


def test_komut_endpoint_key_zorunlu(api_key_ile):
    """POST /api/v1/seralar/{sid}/komut da auth gerektirir."""
    r = api_key_ile.post("/api/v1/seralar/s1/komut", json={"komut": "FAN_AC"})
    assert r.status_code == 401


def test_komut_dogru_key_ile_basarili(api_key_ile):
    """Doğru key + geçerli komut → 201."""
    r = api_key_ile.post(
        "/api/v1/seralar/s1/komut",
        json={"komut": "FAN_AC"},
        headers={"X-API-Key": "test-anahtar-123"},
    )
    assert r.status_code == 201


def test_gecersiz_komut_400(api_key_ile):
    """Bilinmeyen komut → 400."""
    r = api_key_ile.post(
        "/api/v1/seralar/s1/komut",
        json={"komut": "UCAK_KALDIR"},
        headers={"X-API-Key": "test-anahtar-123"},
    )
    assert r.status_code == 400


def test_bilinmeyen_sera_404(api_key_ile):
    """Olmayan sera → 404."""
    r = api_key_ile.get(
        "/api/v1/seralar/s999",
        headers={"X-API-Key": "test-anahtar-123"},
    )
    assert r.status_code == 404


# ── Input validation testleri (Pydantic / 422) ────────────────

def test_bos_komut_422(api_key_siz):
    """Boş komut string → 422 Unprocessable Entity."""
    r = api_key_siz.post("/api/v1/seralar/s1/komut", json={"komut": "   "})
    assert r.status_code == 422


def test_komut_alani_eksik_422(api_key_siz):
    """komut alanı hiç gönderilmemiş → 422."""
    r = api_key_siz.post("/api/v1/seralar/s1/komut", json={})
    assert r.status_code == 422


def test_422_yanit_formati(api_key_siz):
    """422 yanıtı {"success": false, "hata": ..., "kod": "GECERSIZ_ISTEK"} formatında."""
    r = api_key_siz.post("/api/v1/seralar/s1/komut", json={"komut": ""})
    veri = r.json()
    assert veri["success"] is False
    assert "hata" in veri
    assert veri["kod"] == "GECERSIZ_ISTEK"


# ── Docs endpoint testi ───────────────────────────────────────

def test_docs_endpoint_erislebilir(api_key_siz):
    """/docs endpoint'i auth olmadan erişilebilir."""
    r = api_key_siz.get("/docs")
    assert r.status_code == 200
