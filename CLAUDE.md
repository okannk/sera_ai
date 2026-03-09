# CLAUDE.md — Sera AI Proje Rehberi

> **Kural:** Her `git commit` öncesinde bu dosyayı güncelle.
> Yeni dosyalar, tamamlanan görevler, değişen durum, yeni komutlar burada yansımalı.

---

## Proje Amacı

ESP32-S3 + Raspberry Pi 5 tabanlı endüstriyel sera otomasyonu.
Her sera için bağımsız ESP32-S3 sensör nodu (SHT31/MH-Z19C/BH1750/kapasitif nem) → MQTT → RPi 5 merkez.
Sıcaklık, nem, CO₂, toprak nemi izlenir; SSR röle ile aktüatörler (sulama, ısıtıcı, soğutma, fan) kontrol edilir.

---

## Donanım Stack

| Katman | Donanım | İletişim |
|--------|---------|----------|
| Merkez | Raspberry Pi 5 | — (Python process) |
| Saha node | ESP32-S3 (her sera için ayrı) | WiFi / MQTT |
| Sıcaklık + Nem | SHT31-D (Sensirion) | I2C 0x44 |
| CO₂ | MH-Z19C (Winsen NDIR) | UART 9600 baud |
| Işık | BH1750FVI (ROHM) | I2C 0x23 |
| Toprak Nemi | Kapasitif + ADS1115 | I2C ADC |
| Aktüatörler | SSR röle (4 kanal) | GPIO (ESP32) |
| Eski/fallback | DHT22 | GPIO (önerilmiyor) |

**Gelecek (iskelet hazır):**
- Siemens S7-1200 → `merkez/base.py` Modbus TCP placeholder
- STM32 → `drivers/base.py` RS-485 notu

---

## Klasör Yapısı

```
sera_ai/
├── domain/              # Saf iş mantığı — stdlib only, sıfır dış bağımlılık
│   ├── models.py        # SensorOkuma, Komut, SeraKonfig, SistemKonfig, BitkilProfili
│   ├── state_machine.py # SeraStateMachine: 6 durum, on_gecis callback
│   └── circuit_breaker.py # Per-sera bağımsız CB
│
├── sensors/             # Sensör soyutlama — YENİ SENSÖR = SADECE BURAYA
│   ├── base.py          # SensorBase ABC: oku() → dict, olcum_alanlari
│   ├── sht31.py         # I2C, T+H, CRC-8 doğrulama (smbus2)
│   ├── dht22.py         # GPIO, T+H, eski donanım fallback (adafruit_dht)
│   ├── mh_z19c.py       # UART, CO₂, checksum (pyserial)
│   ├── bh1750.py        # I2C, lux (smbus2)
│   ├── kapasitif_nem.py # ADC/ADS1115, toprak nemi (adafruit-ads1x15)
│   └── mock.py          # Sabit değer + gürültü + hata oranı + çağrı sayacı
│
├── drivers/             # Saha node soyutlaması (SahaNodeBase)
│   ├── base.py          # ABC: baglan/sensor_oku/komut_gonder/kapat
│   ├── esp32_s3.py      # MQTT client, thread-safe Queue, ACK bekleme
│   └── mock.py          # Gauss drift fizik simülasyonu
│
├── merkez/              # Merkez donanım (MerkezKontrolBase)
│   ├── base.py          # ABC + Modbus TCP FC03/05/06/02 placeholder
│   ├── raspberry_pi.py  # Daemon thread, per-sera CB+SM+KontrolMotoru
│   └── mock.py          # Komut geçmişi kayıtlı, integration test
│
├── application/         # Orkestrasyon
│   ├── control_engine.py  # KontrolMotoru: sensör→optimizer→komut (idempotent)
│   └── event_bus.py       # Senkron pub/sub, OlayTur enum, hata izolasyonlu
│
├── intelligence/        # Karar motoru — optimizer DI ile değiştirilebilir
│   ├── base.py          # OptimizerBase ABC + HedefDeger dataclass
│   ├── kural_motoru.py  # Deterministik if/else (varsayılan, sklearn gerekmez)
│   ├── mock.py          # Sabit değer + çağrı sayacı
│   ├── feature_extractor.py # SensorOkuma → 9-dim float32, profil-normalize
│   ├── ml_motor.py      # GradientBoosting+IsolationForest+RandomForest×2
│   └── egitim.py        # Sentetik veri + CLI: python -m sera_ai.intelligence.egitim
│
├── config/
│   └── settings.py      # Factory: saha_node_olustur, sensor_olustur,
│                        #   merkez_olustur, optimizer_olustur, tam_sistem_kur
│
├── api/                 # Flask REST API
│   ├── app.py           # api_uygulamasi_olustur(), before_request X-API-Key
│   └── auth.py          # check_api_key(), MUAF_ENDPOINTLER
│
└── infrastructure/      # İskelet — henüz implement edilmedi
    ├── repositories/    # SQLite → InfluxDB geçişi için
    └── notifications/   # Telegram/WhatsApp/e-posta

config.yaml              # Tüm ayarlar (gizli değer yok — .env'den gelir)
pyproject.toml           # Extras: hardware, api, ml, notifications, dev
CONTEXT.md               # Donanım + mimari kararlar (tam bağlam)
```

---

## Katman Kuralları

### `domain/` — Değişmez Çekirdek
- Yalnızca stdlib: `dataclasses`, `enum`, `datetime`, `uuid`, `time`, `typing`
- Runtime `from ..application...` import yasağı (önceden temizlendi)
- `state_machine.py`: EventBus'a `on_gecis: Callable[[dict], None]` ile bağlanır

### `sensors/` — Sensör Soyutlama ← YENİ SENSÖR BURAYA
- `SensorBase.oku() → dict` tek sözleşme
- Donanım kütüphaneleri (smbus2, serial) lazy import — yoksa IOError döner
- **Yeni sensör eklemek:**
  1. `sensors/yeni.py` — `SensorBase` implement et
  2. `config/settings.py:sensor_olustur()` — 3 satır `if tip == "yeni":` bloğu
  3. `config.yaml`'da `- tip: yeni` yaz
  4. **Başka hiçbir dosya değişmez**

### `drivers/` — Saha Donanım
- `SahaNodeBase` ABC'den türer, 4 metot implement edilir
- İş mantığı (eşik, karar) yasak — sadece "donanımla konuş"
- Sensör listesi `SeraKonfig.sensorler`'dan okunur

### `merkez/` — Merkez Donanım
- `MerkezKontrolBase` ABC'den türer
- Per-sera bağımsız CB + SM + KontrolMotoru

### `intelligence/` — Optimizer DI
- `OptimizerBase.hedef_hesapla(sensor, durum) → HedefDeger`
- `ACİL_DURDUR` → her zaman `HedefDeger()` (güvenlik kuralı, ML'e danışılmaz)
- Anomali → `KuralMotoru` fallback
- `sklearn` yoksa sessiz degradasyon (KuralMotoru devreye girer)

### `config/settings.py` — Factory Merkezi
- Tüm "tip → concrete sınıf" çözümlemesi burada
- Yeni donanım/sensör/optimizer → sadece bu fonksiyonlar güncellenir

---

## Mevcut Durum

**Versiyon:** 0.2.0 — `2026-03-10`

### Tamamlananlar
- [x] İki katmanlı donanım soyutlaması: `SahaNodeBase` + `MerkezKontrolBase`
- [x] `config.yaml` driven hardware switching
- [x] State machine (6 durum), Circuit breaker (per-sera bağımsız)
- [x] Event bus (pub/sub, hata izolasyonlu)
- [x] `KontrolMotoru` — idempotent komut, optimizer DI
- [x] `intelligence/` katmanı — `KuralMotoru` + `MLOptimizer` (4 model)
- [x] `FeatureExtractor` — 9-dim profil-normalize
- [x] `egitim.py` — CLI, sentetik veri, tüm profiller
- [x] Flask REST API + X-API-Key auth
- [x] `--demo` CLI modu
- [x] domain → application bağımlılığı temizlendi
- [x] **`sensors/` soyutlama katmanı** — SHT31, MH-Z19C, BH1750, kapasitif nem, DHT22, mock
- [x] `sensor_olustur()` factory
- [x] `SeraKonfig.sensorler` + config.yaml sensör listesi
- [x] CONTEXT.md gerçek donanım stack ile güncellendi
- [x] **147 test, 0 hata**

### Devam Edenler / Sıradaki
- [ ] `infrastructure/repositories/` — SQLite implementasyonu
- [ ] `infrastructure/notifications/` — Telegram/WhatsApp
- [ ] `intelligence/` — RL ajanı iskeleti
- [ ] `drivers/esp32_s3.py` — sensör config ile veri doğrulama
- [ ] Siemens S7-1200 / Modbus TCP
- [ ] Grafana/Loki entegrasyonu

---

## Sık Kullanılan Komutlar

```bash
# Test çalıştır (tam suite)
~/.local/bin/uv run --with pytest --with flask --with flask-cors \
  --with scikit-learn --with numpy --with joblib \
  pytest tests/ -q

# Sadece sensör testleri
~/.local/bin/uv run --with pytest pytest tests/unit/test_sensors.py -v

# Demo modu
~/.local/bin/uv run --with flask --with flask-cors \
  python -m sera_ai --demo --adim 20

# ML model eğitimi
~/.local/bin/uv run --with scikit-learn --with numpy --with joblib \
  python -m sera_ai.intelligence.egitim --hepsi --n 1000

# Git log
git log --oneline -5
```

---

## Bağımlılık Haritası (import yönü)

```
domain ←── sensors
  ↑
  ├── application ←── intelligence
  │       ↑
  │    drivers
  │       ↑
  │    merkez ←── config/settings (factory: hepsini çözer)
  │       ↑
  │     api/
  └────────────────────────────────────────────────────────
```

- `domain` hiçbir şeyi import etmez (stdlib hariç)
- `sensors` sadece `domain.models`'a bağımlı
- `config/settings` factory: tipleri çözer, concrete sınıfları oluşturur

---

## Önemli Tasarım Kararları

| Karar | Neden |
|-------|-------|
| `on_gecis` callback | domain → application runtime import yasağı |
| `SensorBase.oku() → dict` | Sensör değiştirmek = sadece sensors/ dosyası |
| `optimizer=None` → `KuralMotoru` | sklearn olmadan da çalışır |
| `ACİL_DURDUR` → `HedefDeger()` | Güvenlik kuralı, ML'e danışılmaz |
| `IsolationForest` anomali fallback | Bozuk sensör → sistem durmuyor |
| Per-sera CircuitBreaker | Sera C arızası A/B'yi etkilemez |
| Lazy hardware imports | smbus2/serial olmadan import hatası vermez |
| JSONL structured log | Grafana/Loki uyumlu |
