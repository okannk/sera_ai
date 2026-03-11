"""
Domain Modelleri — Sistemin ortak dili.

Neden burada?
  Bu dosya hiçbir framework'e, donanıma, veritabanına bağlı değil.
  drivers/ da import eder, merkez/ da, api/ da — hepsi bu modelleri konuşur.
  Donanım değişse, transport değişse — bu dosya değişmez.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


# ──────────────────────────────────────────────────────────────
# BİTKİ PROFİLİ
# Sıcaklık/nem eşikleri koda değil, profile bağlı.
# Yeni bitki eklemek → koda dokunmadan config.yaml değişikliği.
# ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BitkilProfili:
    isim:      str
    min_T:     float   # Minimum güvenli sıcaklık (°C)
    max_T:     float   # Maksimum güvenli sıcaklık
    opt_T:     float   # Optimal sıcaklık
    min_H:     float   # Minimum nem (%)
    max_H:     float   # Maksimum nem
    opt_CO2:   int     # Optimal CO₂ (ppm)
    hasat_gun: int     # Ortalama hasat süresi
    # Işık (lux) — varsayılan: genel sera değerleri
    min_isik:  int     = 200
    opt_isik:  int     = 5000
    max_isik:  int     = 50000
    # pH — varsayılan: geniş kabul aralığı
    min_pH:    float   = 5.5
    opt_pH:    float   = 6.2
    max_pH:    float   = 7.0
    # EC — elektriksel iletkenlik (mS/cm)
    min_EC:    float   = 0.8
    opt_EC:    float   = 1.8
    max_EC:    float   = 3.5


VARSAYILAN_PROFILLER: dict[str, BitkilProfili] = {
    "Domates": BitkilProfili(
        "Domates", 15, 30, 23, 60, 85, 1000, 90,
        min_isik=2000, opt_isik=20000, max_isik=50000,
        min_pH=5.8, opt_pH=6.3, max_pH=6.8,
        min_EC=2.0,  opt_EC=3.0,  max_EC=4.0,
    ),
    "Biber": BitkilProfili(
        "Biber",   18, 32, 25, 55, 80,  900, 85,
        min_isik=1500, opt_isik=15000, max_isik=40000,
        min_pH=5.8, opt_pH=6.3, max_pH=6.8,
        min_EC=1.8,  opt_EC=2.5,  max_EC=3.5,
    ),
    "Marul": BitkilProfili(
        "Marul",   10, 22, 16, 65, 85,  800, 45,
        min_isik=500,  opt_isik=8000,  max_isik=20000,
        min_pH=5.5, opt_pH=6.0, max_pH=6.5,
        min_EC=0.8,  opt_EC=1.2,  max_EC=2.0,
    ),
}


# ──────────────────────────────────────────────────────────────
# SENSÖR OKUMA
# Fiziksel alanda ölçülen veri noktası.
# gecerli_mi → sensör arızası vs. gerçek aşırı değer ayrımı.
# ──────────────────────────────────────────────────────────────

@dataclass
class SensorOkuma:
    sera_id:     str
    T:           float   # Hava sıcaklığı °C
    H:           float   # Bağıl nem %
    co2:         int     # CO₂ ppm
    isik:        int     # Aydınlık (lux)
    toprak_nem:  int     # ADC değeri 0-1023
    ph:          float   # Çözelti pH
    ec:          float   # Elektriksel iletkenlik mS/cm
    zaman:       datetime = field(default_factory=datetime.now)
    tx_id:       str     = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict:
        d = asdict(self)
        d["zaman"] = self.zaman.isoformat()
        return d

    @property
    def gecerli_mi(self) -> bool:
        """
        Fiziksel olarak mümkün aralıkta mı?
        Neden önemli: Sensör arızası (örn. DHT22 bağlantısı koptu) →
        saçma değerler üretir. Bu check olmadan kontrol motoru
        25°C olan bir serayı -999°C'miş gibi ısıtmaya çalışır.
        """
        return (
            -10  <= self.T          <= 60    and
            0    <= self.H          <= 100   and
            300  <= self.co2        <= 5000  and
            0    <= self.isik       <= 100000 and
            0    <= self.toprak_nem <= 1023  and
            3.0  <= self.ph         <= 9.0   and
            0.0  <= self.ec         <= 10.0
        )


# ──────────────────────────────────────────────────────────────
# KOMUTLAR
# Idempotent semantik: "sulama AÇIK durumda ol"
# İki kez gönderilse bile röleyi bozmaz.
# ──────────────────────────────────────────────────────────────

class Komut(Enum):
    SULAMA_BASLAT  = "SULAMA_AC"
    SULAMA_DURDUR  = "SULAMA_KAPAT"
    ISITICI_BASLAT = "ISITICI_AC"
    ISITICI_DURDUR = "ISITICI_KAPAT"
    SOGUTMA_BASLAT = "SOGUTMA_AC"
    SOGUTMA_DURDUR = "SOGUTMA_KAPAT"
    FAN_BASLAT     = "FAN_AC"
    FAN_DURDUR     = "FAN_KAPAT"
    ISIK_BASLAT    = "ISIK_AC"
    ISIK_DURDUR    = "ISIK_KAPAT"
    ACIL_DURDUR    = "ACIL_DURDUR"


@dataclass
class KomutSonucu:
    komut:        Komut
    basarili:     bool
    mesaj:        str
    zaman:        datetime = field(default_factory=datetime.now)
    kaynak:       str = "sistem"   # "sistem" | "kullanici" | "alarm" | "zamanlayici"
    kullanici_id: str = ""         # kim gönderdi (API key, kullanıcı adı vb.)


# ──────────────────────────────────────────────────────────────
# SENSÖR SAĞLIK
# ──────────────────────────────────────────────────────────────

class SensorSaglik(Enum):
    NORMAL          = "normal"
    UYARI           = "uyari"           # eşik dışı ama makul
    ARIZALI         = "arizali"         # okuma yok / timeout
    PIK             = "pik"             # anlık anormal sıçrama
    DONMUS          = "donmus"          # uzun süre aynı değer
    KALIBRE_HATASI  = "kalibre_hatasi"  # fiziksel sınır dışı


@dataclass
class SensorDurum:
    sensor_tipi:          str
    son_deger:            float
    saglik:               SensorSaglik
    aciklama:             str
    son_gecerli_okuma:    datetime
    ardisik_hata_sayisi:  int
    pik_sayisi_son_1saat: int

    def to_dict(self) -> dict:
        return {
            "sensor_tipi":           self.sensor_tipi,
            "son_deger":             self.son_deger,
            "saglik":                self.saglik.value,
            "aciklama":              self.aciklama,
            "son_gecerli_okuma":     self.son_gecerli_okuma.isoformat(),
            "ardisik_hata_sayisi":   self.ardisik_hata_sayisi,
            "pik_sayisi_son_1saat":  self.pik_sayisi_son_1saat,
        }


# ──────────────────────────────────────────────────────────────
# CİHAZ YÖNETİMİ
# ESP32-S3 saha node'larının kimlik ve kayıt bilgileri.
# Provisioning → kayıt → bağlantı takibi akışı bu modeller üzerinden.
# ──────────────────────────────────────────────────────────────

@dataclass
class CihazKimlik:
    """
    Bir ESP32-S3 (veya benzeri) saha node'unun kimlik kartı.

    cihaz_id formatı: SERA-{tesis_kodu}-{sira_no:03d}
    Örnek: SERA-IST01-001
    """
    cihaz_id:          str       # SERA-IST01-001
    tesis_kodu:        str       # IST01
    sera_id:           str       # s1
    seri_no:           str       # uuid4().hex[:12]
    mac_adresi:        str       # 00:1A:2B:3C:4D:5E
    baglanti_tipi:     str       # WiFi | Ethernet | RS485
    firmware_versiyon: str       # 1.0.0
    son_gorulen:       datetime
    aktif:             bool = True

    def durum(self) -> str:
        """Son kalp atışına göre anlık bağlantı durumu."""
        delta = (datetime.now() - self.son_gorulen).total_seconds()
        if delta < 30:
            return "CEVRIMICI"
        if delta < 90:
            return "GECIKMELI"
        return "KOPUK"

    def to_dict(self) -> dict:
        return {
            "cihaz_id":          self.cihaz_id,
            "tesis_kodu":        self.tesis_kodu,
            "sera_id":           self.sera_id,
            "seri_no":           self.seri_no,
            "mac_adresi":        self.mac_adresi,
            "baglanti_tipi":     self.baglanti_tipi,
            "firmware_versiyon": self.firmware_versiyon,
            "son_gorulen":       self.son_gorulen.isoformat(),
            "aktif":             self.aktif,
            "durum":             self.durum(),
        }


@dataclass
class CihazKayit:
    """
    Cihazın kimlik doğrulama kaydı — MQTT broker auth için.

    sifre_hash formatı: "{salt}:{sha256(salt+sifre)}"
    """
    cihaz_id:             str
    sifre_hash:           str         # salt:sha256(salt+sifre)
    izin_verilen_konular: list        # MQTT topic whitelist (yazma için)
    kayit_tarihi:         datetime = field(default_factory=datetime.now)


# ──────────────────────────────────────────────────────────────
# KONFIG — Domain'e ait olanlar (bağımlılık yok)
# ──────────────────────────────────────────────────────────────

@dataclass
class BildirimKonfig:
    """
    Bildirim sistemi ayarları.
    Token ve şifreler burada saklanmaz — env var adları saklanır.
    Gerçek değerler çalışma anında os.getenv() ile okunur.
    """
    bastirma_dk:          int = 10       # Aynı alarmı tekrar göndermeden önce bekle
    sabah_raporu:         str = "07:00"  # Günlük rapor saati (HH:MM)
    telegram_aktif:       bool = False
    whatsapp_aktif:       bool = False
    eposta_aktif:         bool = False
    # Env var adları (değerlerin kendisi değil)
    telegram_token_env:   str = "TELEGRAM_TOKEN"
    telegram_chat_id_env: str = "TELEGRAM_CHAT_ID"

@dataclass
class SeraKonfig:
    id:           str
    isim:         str
    alan_m2:      float
    bitki:        str
    # Donanım tipi config.yaml'dan gelir, burada saklanır
    saha_donanim: str = "mock"          # esp32_s3 | mock
    # ESP32-S3 bağlantı detayları (donanım seçilince doldurulur)
    mqtt_host:    str = "localhost"
    mqtt_port:    int = 1883
    node_id:      str = ""              # ESP32 node kimliği
    # Sensör listesi — config.yaml'dan: [{tip: sht31, adres: 0x44}, ...]
    sensorler:    list = field(default_factory=list)


@dataclass
class SistemKonfig:
    seralar:              list[SeraKonfig]
    profiller:            dict[str, BitkilProfili]
    merkez_donanim:       str              = "mock"        # raspberry_pi | mock
    sensor_interval_sn:   float            = 2.5
    cb_hata_esigi:        int              = 5
    cb_recovery_sn:       int              = 60
    log_dosyasi:          str              = "sera_system.jsonl"
    db_yolu:              str              = "sera_data.db"
    api_port:             int              = 5000
    api_aktif:            bool             = True
    # API key: değer değil, env var adı saklanır
    api_key_env:          str              = "SERA_API_KEY"
    bildirim:             BildirimKonfig   = field(default_factory=BildirimKonfig)
    # Intelligence katmanı
    optimizer_tip:        str              = "kural_motoru"  # kural_motoru | ml_motor
    model_dizin:          str              = "models"
    # Görüntü işleme — ham konfig dict (settings.py parse eder)
    goruntu_konfig:       dict             = field(default_factory=dict)

    def profil_al(self, bitki: str) -> BitkilProfili:
        if bitki not in self.profiller:
            raise ValueError(
                f"Bilinmeyen bitki profili: {bitki!r}. "
                f"Mevcut: {list(self.profiller.keys())}"
            )
        return self.profiller[bitki]

    @classmethod
    def varsayilan(cls) -> "SistemKonfig":
        """config.yaml yoksa güvenli başlangıç değerleri."""
        return cls(
            seralar=[
                SeraKonfig("s1", "Sera A", 500, "Domates"),
                SeraKonfig("s2", "Sera B", 300, "Biber"),
                SeraKonfig("s3", "Sera C", 200, "Marul"),
            ],
            profiller=dict(VARSAYILAN_PROFILLER),
        )
