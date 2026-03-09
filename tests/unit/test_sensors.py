"""
Unit Testler: Sensör Soyutlama Katmanı

sensors/base.py, sensors/mock.py, sensor_olustur() factory.
Gerçek donanım (I2C/UART) gerektirmeyen testler.
"""
import pytest

from sera_ai.sensors.base import SensorBase
from sera_ai.sensors.mock import MockSensor
from sera_ai.config.settings import sensor_olustur


# ── SensorBase Sözleşmesi ─────────────────────────────────────

def test_sensor_base_soyut():
    """SensorBase doğrudan örneklenemez."""
    with pytest.raises(TypeError):
        SensorBase()


def test_mock_sensor_sensor_base_alt_sinifi():
    assert issubclass(MockSensor, SensorBase)


# ── MockSensor ────────────────────────────────────────────────

def test_mock_sabit_deger_doner():
    s = MockSensor({"T": 23.0, "H": 70.0})
    assert s.oku() == {"T": 23.0, "H": 70.0}


def test_mock_olcum_alanlari():
    s = MockSensor({"T": 23.0, "H": 70.0})
    assert s.olcum_alanlari == frozenset({"T", "H"})


def test_mock_tek_alan():
    s = MockSensor({"co2": 950})
    assert s.olcum_alanlari == frozenset({"co2"})
    assert s.oku() == {"co2": 950}


def test_mock_cagri_sayaci():
    s = MockSensor({"T": 23.0})
    s.oku()
    s.oku()
    s.oku()
    assert s.cagri_sayisi == 3


def test_mock_hata_orani_sifir_hic_hata_vermez():
    s = MockSensor({"T": 23.0}, hata_orani=0.0, tohum=42)
    for _ in range(20):
        s.oku()   # Hiç IOError çıkmamalı
    assert s.hata_sayisi == 0


def test_mock_hata_orani_bir_hep_hata():
    s = MockSensor({"T": 23.0}, hata_orani=1.0)
    with pytest.raises(IOError):
        s.oku()


def test_mock_hata_sayaci_artar():
    s = MockSensor({"T": 23.0}, hata_orani=1.0)
    for _ in range(3):
        try:
            s.oku()
        except IOError:
            pass
    assert s.hata_sayisi == 3


def test_mock_sapma_std_deger_degistirir():
    s = MockSensor({"T": 23.0}, sapma_std=1.0, tohum=99)
    sonuclar = [s.oku()["T"] for _ in range(10)]
    # Gürültü ile hiçbir ikisi tam eşit olmamalı (istatistiksel)
    assert len(set(round(v, 6) for v in sonuclar)) > 1


def test_mock_deger_ayarla():
    s = MockSensor({"T": 20.0})
    s.deger_ayarla(T=35.0)
    assert s.oku()["T"] == 35.0


def test_mock_baglan_true_doner():
    s = MockSensor({"T": 23.0})
    assert s.baglan() is True


def test_mock_kapat_hata_vermez():
    s = MockSensor({"T": 23.0})
    s.kapat()   # Exception olmamalı


def test_mock_repr():
    s = MockSensor({"T": 23.0})
    r = repr(s)
    assert "MockSensor" in r


# ── Çok Alanlı MockSensor ─────────────────────────────────────

def test_mock_cok_alan_tam_doner():
    degerler = {"T": 23.0, "H": 72.0, "co2": 950, "isik": 500, "toprak_nem": 512}
    s = MockSensor(degerler)
    assert s.oku() == degerler


def test_mock_olcum_alanlari_tum_keyleri_kapsar():
    degerler = {"T": 23.0, "H": 72.0, "co2": 950}
    s = MockSensor(degerler)
    assert s.olcum_alanlari == frozenset({"T", "H", "co2"})


# ── sensor_olustur Factory ────────────────────────────────────

def test_factory_mock_tipi():
    s = sensor_olustur({"tip": "mock"})
    assert isinstance(s, MockSensor)


def test_factory_mock_varsayilan_degerler():
    s = sensor_olustur({"tip": "mock"})
    veri = s.oku()
    assert "T" in veri
    assert "H" in veri
    assert "co2" in veri


def test_factory_mock_ozel_degerler():
    s = sensor_olustur({"tip": "mock", "degerler": {"T": 30.0}})
    assert s.oku()["T"] == 30.0


def test_factory_varsayilan_mock():
    """tip belirtilmezse mock döner."""
    s = sensor_olustur({})
    assert isinstance(s, MockSensor)


def test_factory_bilinmeyen_tip_hata():
    with pytest.raises(ValueError, match="Bilinmeyen sensör tipi"):
        sensor_olustur({"tip": "yoktur_boyle_bir_sey"})


def test_factory_sht31_sinif_kontrol():
    """sht31 tipi SHT31Sensor döndürmeli (smbus2 olmasa da sınıf oluşturulabilir)."""
    from sera_ai.sensors.sht31 import SHT31Sensor
    s = sensor_olustur({"tip": "sht31", "adres": 0x44})
    assert isinstance(s, SHT31Sensor)


def test_factory_mhz19c_sinif_kontrol():
    from sera_ai.sensors.mh_z19c import MHZ19CSensor
    s = sensor_olustur({"tip": "mh_z19c", "port": "/dev/ttyS0"})
    assert isinstance(s, MHZ19CSensor)


def test_factory_bh1750_sinif_kontrol():
    from sera_ai.sensors.bh1750 import BH1750Sensor
    s = sensor_olustur({"tip": "bh1750", "adres": 0x23})
    assert isinstance(s, BH1750Sensor)


def test_factory_dht22_sinif_kontrol():
    from sera_ai.sensors.dht22 import DHT22Sensor
    s = sensor_olustur({"tip": "dht22", "pin": 4})
    assert isinstance(s, DHT22Sensor)


def test_factory_kapasitif_nem_sinif_kontrol():
    from sera_ai.sensors.kapasitif_nem import KapasitifNemSensor
    s = sensor_olustur({"tip": "kapasitif_nem", "kanal": 0})
    assert isinstance(s, KapasitifNemSensor)


# ── Donanım Sınıfları — Yapısal Testler ──────────────────────
# Gerçek I2C/UART yok — sadece sınıf yapısı ve olcum_alanlari test edilir

def test_sht31_olcum_alanlari():
    from sera_ai.sensors.sht31 import SHT31Sensor
    s = SHT31Sensor()
    assert s.olcum_alanlari == frozenset({"T", "H"})


def test_dht22_olcum_alanlari():
    from sera_ai.sensors.dht22 import DHT22Sensor
    s = DHT22Sensor()
    assert s.olcum_alanlari == frozenset({"T", "H"})


def test_mhz19c_olcum_alanlari():
    from sera_ai.sensors.mh_z19c import MHZ19CSensor
    s = MHZ19CSensor()
    assert s.olcum_alanlari == frozenset({"co2"})


def test_bh1750_olcum_alanlari():
    from sera_ai.sensors.bh1750 import BH1750Sensor
    s = BH1750Sensor()
    assert s.olcum_alanlari == frozenset({"isik"})


def test_kapasitif_nem_olcum_alanlari():
    from sera_ai.sensors.kapasitif_nem import KapasitifNemSensor
    s = KapasitifNemSensor()
    assert s.olcum_alanlari == frozenset({"toprak_nem"})


def test_donanim_siniflari_sensor_base_alt_sinifi():
    from sera_ai.sensors.sht31 import SHT31Sensor
    from sera_ai.sensors.dht22 import DHT22Sensor
    from sera_ai.sensors.mh_z19c import MHZ19CSensor
    from sera_ai.sensors.bh1750 import BH1750Sensor
    from sera_ai.sensors.kapasitif_nem import KapasitifNemSensor

    for sinif in (SHT31Sensor, DHT22Sensor, MHZ19CSensor, BH1750Sensor, KapasitifNemSensor):
        assert issubclass(sinif, SensorBase), f"{sinif.__name__} SensorBase'den türemeli"


# ── SeraKonfig Sensör Listesi ─────────────────────────────────

def test_sera_konfig_sensorler_alanı():
    """SeraKonfig.sensorler alanı mevcut olmalı."""
    from sera_ai.domain.models import SeraKonfig
    k = SeraKonfig("s1", "Sera A", 500, "Domates")
    assert hasattr(k, "sensorler")
    assert k.sensorler == []


def test_sera_konfig_sensorler_liste_kabul():
    from sera_ai.domain.models import SeraKonfig
    k = SeraKonfig(
        "s1", "Sera A", 500, "Domates",
        sensorler=[{"tip": "sht31", "adres": 0x44}],
    )
    assert len(k.sensorler) == 1
    assert k.sensorler[0]["tip"] == "sht31"


# ── konfig_yukle Sensör Entegrasyonu ─────────────────────────

def test_konfig_yukle_sensorler_parse(tmp_path):
    """config.yaml sensör listesi SeraKonfig.sensorler'e aktarılmalı."""
    yaml_icerik = """
donanim:
  saha: mock
  merkez: mock
sera:
  seralar:
    - id: s1
      isim: "Test Serası"
      bitki: Domates
      alan_m2: 100
      sensorler:
        - tip: sht31
          adres: 0x44
        - tip: mh_z19c
          port: /dev/ttyS0
mqtt:
  host: localhost
  port: 1883
"""
    konfig_dosya = tmp_path / "test_config.yaml"
    konfig_dosya.write_text(yaml_icerik, encoding="utf-8")

    from sera_ai.config.settings import konfig_yukle
    konfig = konfig_yukle(str(konfig_dosya))

    assert len(konfig.seralar[0].sensorler) == 2
    assert konfig.seralar[0].sensorler[0]["tip"] == "sht31"
    assert konfig.seralar[0].sensorler[1]["tip"] == "mh_z19c"
