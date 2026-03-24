"""
Konfigürasyon Yönetimi

Öncelik sırası:
  1. Ortam değişkenleri (SERA_MQTT_HOST=...)
  2. config.yaml
  3. Kod içi varsayılanlar (SistemKonfig.varsayilan())

Factory fonksiyonlar:
  saha_node_olustur() → config.yaml'daki saha_donanim'a göre node döner
  merkez_olustur()    → config.yaml'daki merkez_donanim'a göre merkez döner

Bu sayede sistem geri kalanı hangi sınıfın kullanıldığını bilmez.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..domain.models import (
    BildirimKonfig, BitkilProfili, SeraKonfig, SistemKonfig,
    VARSAYILAN_PROFILLER,
)


def konfig_yukle(yol: str = "config.yaml") -> SistemKonfig:
    """
    config.yaml → SistemKonfig.
    Dosya yoksa veya parse edilemezse güvenli varsayılanlar.
    """
    dosya = Path(yol)
    if not dosya.exists():
        print(f"[Konfig] {yol} bulunamadı → varsayılan kullanılıyor")
        return SistemKonfig.varsayilan()

    try:
        import yaml
    except ImportError:
        print("[Konfig] PyYAML yok → varsayılan (pip install pyyaml)")
        return SistemKonfig.varsayilan()

    with open(dosya, encoding="utf-8") as f:
        ham = yaml.safe_load(f) or {}

    # Ortam değişkenleri en yüksek öncelikte
    mqtt_host = os.getenv("SERA_MQTT_HOST", ham.get("mqtt", {}).get("host", "localhost"))
    mqtt_port = int(os.getenv("SERA_MQTT_PORT", ham.get("mqtt", {}).get("port", 1883)))

    # Bitki profilleri
    profiller = dict(VARSAYILAN_PROFILLER)
    for isim, p in ham.get("bitki_profilleri", {}).items():
        profiller[isim] = BitkilProfili(
            isim=isim,
            min_T=p.get("min_T", 15), max_T=p.get("max_T", 30),
            opt_T=p.get("opt_T", 22),
            min_H=p.get("min_H", 60), max_H=p.get("max_H", 85),
            opt_CO2=p.get("opt_CO2", 1000), hasat_gun=p.get("hasat_gun", 90),
            min_isik=p.get("min_isik", 200),
            opt_isik=p.get("opt_isik", 5000),
            max_isik=p.get("max_isik", 50000),
            min_pH=p.get("min_pH", 5.5),
            opt_pH=p.get("opt_pH", 6.2),
            max_pH=p.get("max_pH", 7.0),
            min_EC=p.get("min_EC", 0.8),
            opt_EC=p.get("opt_EC", 1.8),
            max_EC=p.get("max_EC", 3.5),
        )

    # Seralar
    seralar = []
    for s in ham.get("sera", {}).get("seralar", []):
        seralar.append(SeraKonfig(
            id=s["id"],
            isim=s.get("isim", s["id"]),
            alan_m2=s.get("alan_m2", 100),
            bitki=s.get("bitki", "Domates"),
            saha_donanim=s.get("saha_donanim",
                               ham.get("donanim", {}).get("saha", "mock")),
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            node_id=s.get("node_id", f"esp32_{s['id']}"),
            sensorler=s.get("sensorler", []),
        ))

    if not seralar:
        print("[Konfig] Sera listesi boş → varsayılan seralar kullanılıyor")
        return SistemKonfig.varsayilan()

    sistem_ham   = ham.get("sistem", {})
    donanim_ham  = ham.get("donanim", {})
    api_ham      = ham.get("api", {})
    bildirim_ham = ham.get("bildirim", {})

    bildirim = BildirimKonfig(
        bastirma_dk=bildirim_ham.get("bastirma_dk", 10),
        sabah_raporu=bildirim_ham.get("sabah_raporu", "07:00"),
        telegram_aktif=bildirim_ham.get("telegram_aktif", False),
        whatsapp_aktif=bildirim_ham.get("whatsapp_aktif", False),
        eposta_aktif=bildirim_ham.get("eposta_aktif", False),
        telegram_token_env=bildirim_ham.get("telegram_token_env", "TELEGRAM_TOKEN"),
        telegram_chat_id_env=bildirim_ham.get("telegram_chat_id_env", "TELEGRAM_CHAT_ID"),
    )

    return SistemKonfig(
        seralar=seralar,
        profiller=profiller,
        merkez_donanim=donanim_ham.get("merkez", "mock"),
        sensor_interval_sn=sistem_ham.get("sensor_interval_sn", 2.5),
        cb_hata_esigi=sistem_ham.get("cb_hata_esigi", 5),
        cb_recovery_sn=sistem_ham.get("cb_recovery_sn", 60),
        log_dosyasi=sistem_ham.get("log_dosyasi", "sera_system.jsonl"),
        db_yolu=sistem_ham.get("db_yolu", "sera_data.db"),
        api_port=api_ham.get("port", 5000),
        api_aktif=api_ham.get("aktif", True),
        api_key_env=api_ham.get("api_key_env", "SERA_API_KEY"),
        bildirim=bildirim,
        optimizer_tip=ham.get("intelligence", {}).get("optimizer", "kural_motoru"),
        model_dizin=ham.get("intelligence", {}).get("model_dizin", "models"),
        goruntu_konfig=ham.get("goruntu", {}),
    )


def saha_node_olustur(sera_konfig: SeraKonfig, sistem: SistemKonfig):
    """
    config.yaml'daki saha_donanim değerine göre doğru node'u oluştur.

    Dönen tip: SahaNodeBase (concrete sınıf değil)
    Çağıran bu fonksiyonu çağırır, hangisinin geldiğini sorgulamaz.
    """
    from ..drivers.base import SahaNodeBase

    tip = sera_konfig.saha_donanim.lower()

    if tip == "esp32_s3":
        from ..drivers.esp32_s3 import ESP32S3Node
        return ESP32S3Node(
            sera_id=sera_konfig.id,
            node_id=sera_konfig.node_id or f"esp32_{sera_konfig.id}",
            mqtt_host=sera_konfig.mqtt_host,
            mqtt_port=sera_konfig.mqtt_port,
            kullanici=os.getenv("MQTT_KULLANICI", ""),
            sifre=os.getenv("MQTT_SIFRE", ""),
            sensorler=sera_konfig.sensorler,
        )

    if tip == "mock":
        from ..drivers.mock import MockSahaNode
        profil = sistem.profil_al(sera_konfig.bitki)
        return MockSahaNode(
            sera_id=sera_konfig.id,
            profil=profil,
        )

    raise ValueError(
        f"Bilinmeyen saha donanımı: {tip!r}. "
        f"Geçerli seçenekler: esp32_s3, mock"
    )


def merkez_olustur(konfig: SistemKonfig):
    """
    config.yaml'daki merkez_donanim değerine göre merkez oluştur.

    Dönen tip: MerkezKontrolBase (concrete sınıf değil)
    """
    from ..application.event_bus import EventBus as EB

    tip = konfig.merkez_donanim.lower()
    bus = EB()

    if tip == "raspberry_pi":
        from ..merkez.raspberry_pi import RaspberryPiMerkez
        return RaspberryPiMerkez(konfig, olay_bus=bus)

    if tip == "mock":
        from ..merkez.mock import MockMerkez
        return MockMerkez()

    raise ValueError(
        f"Bilinmeyen merkez donanımı: {tip!r}. "
        f"Geçerli seçenekler: raspberry_pi, mock"
    )


def sensor_olustur(sensor_konfig: dict):
    """
    config.yaml sensör tanımından doğru sensör sürücüsünü oluştur.

    Dönen tip: SensorBase (concrete sınıf değil)
    Yeni sensör eklemek → sensors/ altına yeni dosya + buraya 3 satır.
    """
    tip = sensor_konfig.get("tip", "mock").lower()

    if tip == "sht31":
        from ..sensors.sht31 import SHT31Sensor
        return SHT31Sensor(
            adres=sensor_konfig.get("adres", 0x44),
            bus_no=sensor_konfig.get("bus_no", 1),
        )

    if tip == "dht22":
        from ..sensors.dht22 import DHT22Sensor
        return DHT22Sensor(pin=sensor_konfig.get("pin", 4))

    if tip == "mh_z19c":
        from ..sensors.mh_z19c import MHZ19CSensor
        return MHZ19CSensor(
            port=sensor_konfig.get("port", "/dev/ttyS0"),
            baud=sensor_konfig.get("baud", 9600),
        )

    if tip == "bh1750":
        from ..sensors.bh1750 import BH1750Sensor
        return BH1750Sensor(
            adres=sensor_konfig.get("adres", 0x23),
            bus_no=sensor_konfig.get("bus_no", 1),
        )

    if tip == "kapasitif_nem":
        from ..sensors.kapasitif_nem import KapasitifNemSensor
        return KapasitifNemSensor(
            kanal=sensor_konfig.get("kanal", 0),
            i2c_adres=sensor_konfig.get("i2c_adres", 0x48),
        )

    if tip == "mock":
        from ..sensors.mock import MockSensor
        return MockSensor(degerler=sensor_konfig.get("degerler", {
            "T": 23.0, "H": 72.0, "co2": 950,
            "isik": 500, "toprak_nem": 500,
        }))

    raise ValueError(
        f"Bilinmeyen sensör tipi: {tip!r}. "
        f"Geçerli: sht31, dht22, mh_z19c, bh1750, kapasitif_nem, mock"
    )


def optimizer_olustur(konfig: SistemKonfig, profil):
    """
    config.yaml'daki intelligence.optimizer değerine göre optimizer oluştur.

    Dönen tip: OptimizerBase (concrete sınıf değil)
    KontrolMotoru optimizer= parametresine doğrudan verilir.
    """
    tip = konfig.optimizer_tip.lower()

    if tip == "ml_motor":
        from ..intelligence.ml_motor import MLOptimizer
        return MLOptimizer(profil, model_dizin=konfig.model_dizin)

    if tip == "kural_motoru":
        from ..intelligence.kural_motoru import KuralMotoru
        return KuralMotoru(profil)

    if tip == "rl_ajan":
        from ..intelligence.rl_ajan import RLAjan
        return RLAjan(profil)

    raise ValueError(
        f"Bilinmeyen optimizer: {tip!r}. "
        f"Geçerli seçenekler: kural_motoru, ml_motor, rl_ajan"
    )


def kamera_olustur(kamera_konfig: dict):
    """
    config.yaml kamera tanımından doğru KameraBase implementasyonunu oluştur.

    Yeni kamera eklemek → goruntu/ altına yeni dosya + buraya 3 satır.
    """
    tip = kamera_konfig.get("tip", "mock").lower()

    if tip == "esp32_cam":
        from ..goruntu.esp32_kamera import ESP32Kamera
        return ESP32Kamera(
            url=kamera_konfig.get("url", "http://192.168.1.200/capture"),
            zaman_asimi_sn=kamera_konfig.get("zaman_asimi_sn", 5.0),
        )

    if tip == "mock":
        from ..goruntu.mock import MockKamera
        return MockKamera(
            hata_orani=kamera_konfig.get("hata_orani", 0.0),
        )

    raise ValueError(
        f"Bilinmeyen kamera tipi: {tip!r}. "
        f"Geçerli seçenekler: esp32_cam, mock"
    )


def tespit_olustur(goruntu_konfig: dict):
    """
    config.yaml görüntü tanımından doğru HastalikTespitBase implementasyonunu oluştur.
    """
    tip = goruntu_konfig.get("tespit", "mock").lower()

    if tip == "model":
        from ..goruntu.model import HastalikModeli
        return HastalikModeli(
            model_yolu=goruntu_konfig.get("model_yolu", "models/hastalik_tespiti.pkl")
        )

    if tip == "mock":
        from ..goruntu.mock import MockHastalıkTespit
        return MockHastalıkTespit()

    raise ValueError(
        f"Bilinmeyen tespit tipi: {tip!r}. "
        f"Geçerli seçenekler: model, mock"
    )


def goruntu_servisleri_olustur(konfig: SistemKonfig, olay_bus=None) -> dict:
    """
    config.yaml'daki goruntu.seralar listesine göre per-sera GorüntuServisi oluştur.

    Döner: {sera_id: GorüntuServisi}
    goruntu.aktif: false ise boş dict döner.
    """
    from ..goruntu.base import GorüntuServisi

    goruntu_konfig = getattr(konfig, "goruntu_konfig", {})
    if not goruntu_konfig.get("aktif", False):
        return {}

    genel_tespit_konfig = {
        "tespit":     goruntu_konfig.get("tespit", "mock"),
        "model_yolu": goruntu_konfig.get("model_yolu", "models/hastalik_tespiti.pkl"),
    }
    guven_esigi = goruntu_konfig.get("guven_esigi", 0.60)

    servisler = {}
    for sera_conf in goruntu_konfig.get("seralar", []):
        sera_id = sera_conf.get("id")
        if not sera_id:
            continue
        kamera = kamera_olustur({
            "tip": goruntu_konfig.get("kamera", "mock"),
            **sera_conf,
        })
        tespit = tespit_olustur(genel_tespit_konfig)
        servisler[sera_id] = GorüntuServisi(
            kamera=kamera,
            tespit=tespit,
            olay_bus=olay_bus,
            guven_esigi=guven_esigi,
        )

    return servisler


def tam_sistem_kur(konfig: SistemKonfig):
    """
    config.yaml'dan tam sistem oluştur.
    Her seraya uygun node ekle, merkezi döndür.

    Kullanım:
        konfig = konfig_yukle("config.yaml")
        merkez = tam_sistem_kur(konfig)
        merkez.baslat()
    """
    merkez = merkez_olustur(konfig)
    for sera in konfig.seralar:
        node = saha_node_olustur(sera, konfig)
        merkez.node_ekle(sera.id, node)
    return merkez
