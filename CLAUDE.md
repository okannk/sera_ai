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
│
├── infrastructure/
│   ├── logging/         # JSONLLogger, LokiLogger, MockLogger, LogDispatcher
│   ├── mqtt/            # MQTTIstemciBase, Mock, ESP32Simulatoru, Paho
│   ├── notifications/   # BildirimKanalBase, Telegram, MockBildirim, Dispatcher
│   └── repositories/    # SensorRepository, KomutRepository, SQLite impl
│
├── grafana/             # Docker Compose + provisioning + 2 dashboard JSON
│   ├── docker-compose.yml
│   ├── promtail/config.yml
│   ├── provisioning/
│   └── dashboards/
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

**Versiyon:** 0.6.0 — `2026-03-10`

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
- [x] **`infrastructure/repositories/`** — `SensorRepository` + `KomutRepository` ABC, SQLite impl, WAL modu, idempotent yazma, zaman aralığı sorgu, temizleme
- [x] **`infrastructure/mqtt/`** — `MQTTIstemciBase` ABC, `MockMQTTBroker` (in-process, wildcard destekli), `MockMQTTIstemci`, `ESP32Simulatoru` (sensör yayını + komut ACK), `MQTTKomutKoprusu` (dış komut → callback), `PahoMQTTIstemci` (gerçek broker)
- [x] `config.yaml` `mqtt.aktif: false` alanı eklendi
- [x] **`infrastructure/notifications/`** — `BildirimKanalBase` ABC, `TelegramKanal` (httpx, lazy), `MockBildirimKanal`, `BildirimDispatcher` (EventBus abone, bastırma, kritik bypass)
- [x] **`drivers/esp32_s3.py`** — `SeraKonfig.sensorler` bazlı doğrulama: eksik alan → sentinel, fiziksel sınır dışı → sentinel, `gecerli_mi=False`; geriye dönük uyumlu (`sensorler=[]`)
- [x] `settings.py` `saha_node_olustur()` → `sensorler=` geçirildi
- [x] **Grafana/Loki entegrasyonu**
  - `infrastructure/logging/`: `LogYaziciBase` ABC, `JSONLLogger` (thread-safe, Promtail uyumlu), `LokiLogger` (HTTP push, batch, stream gruplama), `MockLogger`, `LogDispatcher` (EventBus abone, seviye eşleme)
  - `api/metrics.py`: `/metrics` Prometheus text format (stdlib, harici lib yok), auth muaf
  - `grafana/`: Docker Compose (Loki+Grafana+Promtail), provisioning, 2 dashboard JSON
- [x] **Uçtan uca entegrasyon testleri** — 3 senaryo, yeni production kodu yok
  - Senaryo 1: MockSahaNode → KontrolMotoru → SQLite + Bildirim + Log zinciri
  - Senaryo 2: ESP32Simulatoru → MockMQTTBroker → MQTTSahaNodeAdaptor → KontrolMotoru (MQTT round-trip)
  - Senaryo 3: 3 sera paralel, CB izolasyonu, çapraz kirlilik yok
- [x] **374 test, 0 hata**
- [x] **`intelligence/rl_ajan.py`** — Tabular Q-Learning RL ajan
  - 30 durum (5×3×2: T_sapma × H_band × toprak_band), 16 eylem (2^4)
  - KuralMotoru warm-start: ilk adımdan güvenli, sıfırdan başlamaz
  - `odul_hesapla()` + `ogren()` online Bellman güncellemesi
  - `kaydet()`/`yukle()` pickle kalıcılığı
  - `epsilon`-greedy keşif (production'da 0.05, test'te 0.0)
  - ACİL_DURDUR → HedefDeger() (ML/RL'e danışılmaz)
  - numpy yoksa KuralMotoru fallback (sessiz degradasyon)
  - `config.yaml` `intelligence.optimizer: rl_ajan` ile aktif
  - 26 unit test, KontrolMotoru DI entegrasyon testi dahil
- [x] **RLAjan öğrenme döngüsü** — `KontrolMotoru` entegrasyonu
  - `OptimizerBase.geri_bildirim(onceki, sonraki)` → no-op varsayılan
  - `RLAjan.geri_bildirim()` → ödül hesapla + Bellman güncelle
  - `KontrolMotoru._onceki_sensor` state, her `adim_at()` sonunda güncellenir
  - Geçersiz sensör → zincir sıfırlanır (yanlış ödül hesabı engellenir)
  - 9 yeni test (35 toplam RL testi)

- [x] **Flask → FastAPI geçişi** (v1.0 API katmanı)
  - `/api/v1/` prefix, async endpoint'ler, `/docs` OpenAPI
  - slowapi rate limiting: 60 req/min per IP (`/sistem/saglik` muaf)
  - Pydantic input validation, 422 + açıklayıcı hata
  - Global exception handler, tutarlı hata formatı `{"success": false, "hata": ..., "kod": ...}`
  - Uvicorn ile çalışır
- [x] **API → gerçek sisteme bağlantısı** (`api/servis.py` — `MerkezApiServisi`)
  - `MerkezKontrolBase` + `SistemKonfig` → API duck-type arayüzüne adapte
  - `tum_seralar / sera_detay / son_sensor / komut_gonder / saglik / metrikler / aktif_alarmlar`
  - Komut string → Komut enum çevirisi, geçersiz komut/sera doğrulaması
  - `__main__.py` `--api` flag'i: kontrol döngüsüyle aynı süreçte Flask başlatır
  - `api_uygulamasi_olustur(servis=MerkezApiServisi(...))` ile inject edilir
  - Mock servis (`SeraApiServisi`) değişmedi — demo/geliştirme için hâlâ geçerli
  - 23 unit test + 4 Flask entegrasyon testi

- [x] **Altyapı boşlukları kapatıldı** (v0.5.0)
  - `RaspberryPiMerkez` artık SQLiteRepository + LogDispatcher + BildirimDispatcher kullanıyor
  - `_sera_adimi()` → sensör verisi doğrudan DB'ye yazılıyor
  - `KOMUT_GONDERILDI` event → `KomutRepository`'ye yazılıyor
  - `OptimizerBase.baslangic_yukle()` / `kapatma_kaydet()` — lifecycle API
  - `RLAjan` restart'ta Q-tablosunu yüklüyor, kapanırken kaydediyor
  - `odul_hesapla()` CO₂ bileşeni eklendi (aralık -4…0)
  - `JSONLLogger` log rotation: `max_mb=10`, `yedek_sayisi=3`
  - `__main__.py` `--api` → Waitress (yoksa Flask dev server + uyarı)
  - `pyproject.toml` `api` extras'a `waitress>=3.0` eklendi
  - `MockMerkez.tum_durum()` — `RaspberryPiMerkez` ile aynı format
  - API mock fallback uyarısı

- [x] **RLAjan tam sensör entegrasyonu** (v0.5.1)
  - `BitkilProfili` 9 yeni alan: `min_isik/opt_isik/max_isik`, `min_pH/opt_pH/max_pH`, `min_EC/opt_EC/max_EC` (varsayılan değerli, geriye dönük uyumlu)
  - `VARSAYILAN_PROFILLER` bitki-spesifik ışık/pH/EC değerleri (Domates/Biber/Marul)
  - `DURUM_SAYISI` 30 → **2430** (5×3×2×3×3×3×3 — 7 sensörün tamamı)
  - Durum indeksi: `t×486 + h×162 + toprak×81 + co2×27 + isik×9 + ph×3 + ec`
  - `odul_hesapla()` artık 7 bileşen: T, H, toprak, CO₂, ışık, pH, EC (aralık -7…0)
  - `config.yaml` bitki profillerine ışık/pH/EC alanları eklendi
  - `settings.py` `konfig_yukle()` yeni alanları okuyor
  - 38 test, 370 toplam, 0 hata

- [x] **Çoklu sera yönetimi** (v0.6.0) — Adım 1 tamamlandı
  - `RaspberryPiMerkez` zaten N-greenhouse: per-sera `_cb_ler`, `_sm_ler`, `_motorlar` dict'leri
  - `_kontrol_dongusu()` tüm seraları sıralı işler, per-sera CB izolasyonu
  - `demo_komplet.py` → `DemoBridgeMulti` (3 sera: s1 Domates, s2 Biber, s3 Marul)
    - 3× ESP32Simulatoru + 3× MQTTSahaNodeAdaptor (paylaşımlı broker)
    - 3× RLAjan Q(2430, 16) paralel öğrenme
    - CB izolasyonu kanıtlandı: s2 ALARM, s1/s3 NORMAL kalıyor
    - API tüm seraları tek endpointten sunuyor (`/api/seralar`)
    - 40 komut / 56 JSONL satır / 6 bildirim (10 adım, 3 sera)
  - Production yolu (`config.yaml` → `RaspberryPiMerkez`) zaten doğru, değişmedi
  - `tests/integration/test_uctan_uca.py` Senaryo 3: 3 sera paralel, CB izolasyonu testli
  - 370 test, 0 hata

### Devam Edenler / Sıradaki
- [x] **React dashboard** (canlı veri, alarm banner, grafik, komut paneli) — Adım 2
  - `dashboard/` — Vite + React + TypeScript + Tailwind v4 + Recharts
  - Her 2 saniyede otomatik güncelleme, karta tıkla → modal (grafik + komut)
  - `npm run dev` ile başlatılır (proxy: localhost:5000)
- [ ] Görüntü işleme (kamera hastalık tespiti) — Adım 3
- [ ] Sesli asistan (Türkçe) — Adım 4
- [ ] Siemens S7-1200 / Modbus TCP (donanım gelince)

---

## Dashboard Komutları

```bash
# Geliştirme: önce Flask'ı başlat, sonra React'ı
python -m sera_ai --demo          # terminal 1 — Flask :5000
cd dashboard && npm run dev        # terminal 2 — Vite :5173

# Production build
cd dashboard && npm run build
```

## Sık Kullanılan Komutlar

```bash
# Test çalıştır (tam suite)
~/.local/bin/uv run --with pytest --with flask --with flask-cors \
  --with scikit-learn --with numpy --with joblib \
  pytest tests/ -q

# Sadece sensör testleri
~/.local/bin/uv run --with pytest pytest tests/unit/test_sensors.py -v

# Çoklu sera demo (3 sera paralel)
~/.local/bin/uv run --with flask --with flask-cors \
  --with numpy --with joblib python demo_komplet.py

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
