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


VARSAYILAN_PROFILLER: dict[str, BitkilProfili] = {
    "Domates": BitkilProfili("Domates", 15, 30, 23, 60, 85, 1000, 90),
    "Biber":   BitkilProfili("Biber",   18, 32, 25, 55, 80,  900, 85),
    "Marul":   BitkilProfili("Marul",   10, 22, 16, 65, 85,  800, 45),
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
    komut:    Komut
    basarili: bool
    mesaj:    str
    zaman:    datetime = field(default_factory=datetime.now)


# ──────────────────────────────────────────────────────────────
# KONFIG — Domain'e ait olanlar (bağımlılık yok)
# ──────────────────────────────────────────────────────────────

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


@dataclass
class SistemKonfig:
    seralar:              list[SeraKonfig]
    profiller:            dict[str, BitkilProfili]
    merkez_donanim:       str   = "mock"        # raspberry_pi | mock
    sensor_interval_sn:   float = 2.5
    cb_hata_esigi:        int   = 5
    cb_recovery_sn:       int   = 60
    log_dosyasi:          str   = "sera_system.jsonl"
    db_yolu:              str   = "sera_data.db"
    api_port:             int   = 5000
    api_aktif:            bool  = True

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
