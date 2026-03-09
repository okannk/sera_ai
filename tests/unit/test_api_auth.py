"""
Unit Testler: API Kimlik Doğrulama

İki katman test edilir:
  1. check_api_key() — Flask'tan bağımsız, saf mantık
  2. Flask test client — auth middleware entegrasyonu
"""
import pytest

from sera_ai.api.auth import check_api_key


# ── check_api_key() unit testleri (Flask gerektirmez) ─────────

def test_key_tanimli_degil_her_seye_izin_verir():
    """Sistem key'i tanımlı değilse (dev modu) her değere izin ver."""
    assert check_api_key("herhangi-bir-deger", beklenen_key="") is True
    assert check_api_key("",                   beklenen_key="") is True


def test_dogru_key_izin_verir():
    assert check_api_key("gizli-anahtar", beklenen_key="gizli-anahtar") is True


def test_yanlis_key_reddeder():
    assert check_api_key("yanlis",  beklenen_key="dogru-anahtar") is False


def test_bos_key_gonderilmis_reddeder():
    """Header hiç gönderilmemiş → boş string → reddet."""
    assert check_api_key("", beklened_key := "gizli") is False


def test_buyuk_kucuk_harf_duyarli():
    """'Gizli' != 'gizli' — key case-sensitive."""
    assert check_api_key("Gizli", beklenen_key="gizli") is False


# ── Flask test client testleri ────────────────────────────────

@pytest.fixture
def api_key_ile(request):
    """X-API-Key korumalı Flask test client'ı."""
    flask = pytest.importorskip("flask")
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="test-anahtar-123")
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def api_key_siz():
    """Key tanımlı olmayan Flask test client'ı (dev modu)."""
    pytest.importorskip("flask")
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="")
    app.config["TESTING"] = True
    return app.test_client()


def test_key_olmadan_401(api_key_ile):
    """Key zorunluyken header gönderilmezse 401."""
    r = api_key_ile.get("/api/seralar")
    assert r.status_code == 401


def test_yanlis_key_401(api_key_ile):
    """Yanlış key → 401."""
    r = api_key_ile.get("/api/seralar",
                        headers={"X-API-Key": "yanlis-anahtar"})
    assert r.status_code == 401


def test_dogru_key_200(api_key_ile):
    """Doğru key → 200."""
    r = api_key_ile.get("/api/seralar",
                        headers={"X-API-Key": "test-anahtar-123"})
    assert r.status_code == 200


def test_saglik_auth_gerektirmez(api_key_ile):
    """/api/sistem/saglik auth olmadan erişilebilir."""
    r = api_key_ile.get("/api/sistem/saglik")
    assert r.status_code in (200, 503)   # 503 alarm varsa, ikisi de OK


def test_key_siz_modda_auth_yok(api_key_siz):
    """Key tanımlı değilse tüm endpoint'ler açık (dev modu)."""
    r = api_key_siz.get("/api/seralar")
    assert r.status_code == 200


def test_401_yanit_formati(api_key_ile):
    """401 yanıtı standart JSON zarfında gelmeli."""
    import json
    r = api_key_ile.get("/api/seralar")
    veri = json.loads(r.data)
    assert veri["success"] is False
    assert veri["error"] is not None


def test_komut_endpoint_key_zorunlu(api_key_ile):
    """POST /api/seralar/<sid>/komut da auth gerektirir."""
    r = api_key_ile.post("/api/seralar/s1/komut",
                          json={"komut": "FAN_AC"})
    assert r.status_code == 401


def test_komut_dogru_key_ile_basarili(api_key_ile):
    """Doğru key + geçerli komut → 201."""
    r = api_key_ile.post(
        "/api/seralar/s1/komut",
        json={"komut": "FAN_AC"},
        headers={"X-API-Key": "test-anahtar-123"},
    )
    assert r.status_code == 201


def test_gecersiz_komut_400(api_key_ile):
    """Bilinmeyen komut → 400."""
    r = api_key_ile.post(
        "/api/seralar/s1/komut",
        json={"komut": "UCAK_KALDIR"},
        headers={"X-API-Key": "test-anahtar-123"},
    )
    assert r.status_code == 400


def test_bilinmeyen_sera_404(api_key_ile):
    """Olmayan sera → 404."""
    r = api_key_ile.get("/api/seralar/s999",
                        headers={"X-API-Key": "test-anahtar-123"})
    assert r.status_code == 404
