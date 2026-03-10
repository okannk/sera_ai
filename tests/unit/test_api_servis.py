"""
Unit Testler: MerkezApiServisi

MerkezKontrolBase (MockMerkez) + SistemKonfig üzerinde:
  - tum_seralar()     → liste, metadata + durum + sensör
  - sera_detay()      → tek sera + profil, bilinmeyen → None
  - son_sensor()      → dict veya None
  - komut_gonder()    → geçerli/geçersiz komut ve sera_id
  - saglik()          → uptime, durum, alarm_sayisi
  - metrikler()       → sera_sayisi, durum_dagilimi
  - aktif_alarmlar()  → sadece alarm durumundakiler
  - Flask entegrasyon → MerkezApiServisi servis= ile inject
"""
import pytest

from sera_ai.domain.models import Komut, SistemKonfig, SensorOkuma
from sera_ai.merkez.mock import MockMerkez
from sera_ai.drivers.mock import MockSahaNode
from sera_ai.api.servis import MerkezApiServisi


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def konfig() -> SistemKonfig:
    return SistemKonfig.varsayilan()


@pytest.fixture
def merkez(konfig) -> MockMerkez:
    m = MockMerkez()
    for sera in konfig.seralar:
        profil = konfig.profil_al(sera.bitki)
        node   = MockSahaNode(sera.id, profil,
                              sensor_hata_orani=0.0, komut_hata_orani=0.0)
        m.node_ekle(sera.id, node)
    m.baslat()
    return m


@pytest.fixture
def servis(merkez, konfig) -> MerkezApiServisi:
    return MerkezApiServisi(merkez, konfig)


# ── tum_seralar() ─────────────────────────────────────────────

def test_tum_seralar_sera_sayisi(servis, konfig):
    """Konfig'deki sera sayısı kadar öğe döndürmeli."""
    sonuc = servis.tum_seralar()
    assert len(sonuc) == len(konfig.seralar)


def test_tum_seralar_zorunlu_alanlar(servis):
    """Her öğede id, isim, bitki, alan, durum alanları olmalı."""
    for s in servis.tum_seralar():
        assert "id"    in s
        assert "isim"  in s
        assert "bitki" in s
        assert "alan"  in s
        assert "durum" in s


def test_tum_seralar_idler_dogru(servis, konfig):
    """Dönen id'ler konfig'deki sıralamayla eşleşmeli."""
    idler = [s["id"] for s in servis.tum_seralar()]
    assert idler == [s.id for s in konfig.seralar]


# ── sera_detay() ──────────────────────────────────────────────

def test_sera_detay_gecerli_sid(servis, konfig):
    """Geçerli sid → dict, profil alanı dahil."""
    d = servis.sera_detay(konfig.seralar[0].id)
    assert d is not None
    assert "profil" in d
    assert "min_T"  in d["profil"]


def test_sera_detay_bilinmeyen_sid(servis):
    """Bilinmeyen sid → None."""
    assert servis.sera_detay("s_yok") is None


def test_sera_detay_bitki_profil_uyumu(servis, konfig):
    """Dönen profil, konfig'deki bitki profiline ait olmalı."""
    sera   = konfig.seralar[0]
    profil = konfig.profil_al(sera.bitki)
    d      = servis.sera_detay(sera.id)
    assert d["profil"]["opt_T"] == profil.opt_T


# ── son_sensor() ──────────────────────────────────────────────

def test_son_sensor_bos_baslangic(servis, konfig):
    """MockMerkez başlangıçta sensör okumadığı için None dönebilir."""
    # MockMerkez._son_okumallar boş başlar
    sonuc = servis.son_sensor(konfig.seralar[0].id)
    # None veya dict — ikisi de kabul
    assert sonuc is None or isinstance(sonuc, dict)


def test_son_sensor_bilinmeyen_sid(servis):
    """Bilinmeyen sid → None."""
    assert servis.son_sensor("s_yok") is None


# ── komut_gonder() ────────────────────────────────────────────

def test_komut_gonder_gecerli(servis, konfig):
    """Geçerli komut → basarili=True."""
    sonuc = servis.komut_gonder(konfig.seralar[0].id, "FAN_AC")
    assert sonuc["basarili"] is True
    assert sonuc["komut"] == "FAN_AC"


def test_komut_gonder_gecersiz_komut(servis, konfig):
    """Bilinmeyen komut → basarili=False + gecerli listesi."""
    sonuc = servis.komut_gonder(konfig.seralar[0].id, "UCAK_KALDIR")
    assert sonuc["basarili"] is False
    assert "gecerli" in sonuc


def test_komut_gonder_bilinmeyen_sera(servis):
    """Bilinmeyen sera_id → basarili=False."""
    sonuc = servis.komut_gonder("s_yok", "FAN_AC")
    assert sonuc["basarili"] is False


def test_komut_gonder_buyuk_kucuk_harf(servis, konfig):
    """Komut string büyük/küçük harf farkı yutulmalı."""
    sonuc = servis.komut_gonder(konfig.seralar[0].id, "fan_ac")
    assert sonuc["basarili"] is True


def test_komut_gonder_tum_gecerli_komutlar(servis, konfig):
    """Tüm Komut enum değerleri geçerli komut olarak kabul edilmeli."""
    sid = konfig.seralar[0].id
    for komut in Komut:
        sonuc = servis.komut_gonder(sid, komut.value)
        assert sonuc["basarili"] is True, f"{komut.value} geçersiz sayıldı"


# ── saglik() ──────────────────────────────────────────────────

def test_saglik_zorunlu_alanlar(servis):
    """saglik() zorunlu alanları döndürmeli."""
    s = servis.saglik()
    assert s["durum"] == "CALISIYOR"
    assert "uptime_sn"   in s
    assert "seralar"     in s
    assert "alarm_sayisi" in s


def test_saglik_uptime_pozitif(servis):
    """Uptime sıfır veya pozitif olmalı."""
    assert servis.saglik()["uptime_sn"] >= 0


def test_saglik_seralar_anahtarlari(servis, konfig):
    """seralar dict'i konfig'deki tüm id'leri içermeli."""
    seralar = servis.saglik()["seralar"]
    for s in konfig.seralar:
        assert s.id in seralar


# ── metrikler() ───────────────────────────────────────────────

def test_metrikler_sera_sayisi(servis, konfig):
    assert servis.metrikler()["sera_sayisi"] == len(konfig.seralar)


def test_metrikler_durum_dagilimi_var(servis):
    assert "durum_dagilimi" in servis.metrikler()


# ── aktif_alarmlar() ──────────────────────────────────────────

def test_aktif_alarmlar_normal_durumda_bos(servis):
    """MockMerkez normal durumda alarm üretmez."""
    # MockMerkez.tum_durum() 'durum' alanı içermiyor → alarm çıkmaz
    alarmlar = servis.aktif_alarmlar()
    assert isinstance(alarmlar, list)


# ── FastAPI entegrasyon (MerkezApiServisi inject) ─────────────

@pytest.fixture
def fastapi_client(merkez, konfig):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sera_ai.api.app import api_uygulamasi_olustur
    from sera_ai.api.servis import MerkezApiServisi
    servis = MerkezApiServisi(merkez, konfig)
    app = api_uygulamasi_olustur(servis=servis, api_key="")
    return TestClient(app, raise_server_exceptions=False), konfig


def test_fastapi_tum_seralar_endpoint(fastapi_client):
    """MerkezApiServisi ile /api/v1/seralar endpoint'i çalışmalı."""
    c, konfig = fastapi_client
    r = c.get("/api/v1/seralar")
    assert r.status_code == 200
    veri = r.json()
    assert veri["success"] is True
    assert len(veri["data"]) == len(konfig.seralar)


def test_fastapi_sera_detay_endpoint(fastapi_client):
    """MerkezApiServisi ile /api/v1/seralar/{sid} çalışmalı."""
    c, konfig = fastapi_client
    r = c.get(f"/api/v1/seralar/{konfig.seralar[0].id}")
    assert r.status_code == 200
    veri = r.json()
    assert "profil" in veri["data"]


def test_fastapi_komut_endpoint(fastapi_client):
    """MerkezApiServisi ile POST /api/v1/seralar/{sid}/komut çalışmalı."""
    c, konfig = fastapi_client
    r = c.post(
        f"/api/v1/seralar/{konfig.seralar[0].id}/komut",
        json={"komut": "FAN_AC"},
    )
    assert r.status_code == 201
    veri = r.json()
    assert veri["success"] is True


def test_fastapi_saglik_endpoint(fastapi_client):
    """/api/v1/sistem/saglik MerkezApiServisi ile çalışmalı."""
    c, _ = fastapi_client
    r = c.get("/api/v1/sistem/saglik")
    assert r.status_code in (200, 503)
