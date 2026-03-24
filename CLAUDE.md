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
| Kamera | ESP32-CAM | WiFi / HTTP |
| Eski/fallback | DHT22 | GPIO (önerilmiyor) |

**Gelecek (iskelet hazır):**
- Siemens S7-1200 → `merkez/base.py` Modbus TCP placeholder
- STM32 → `drivers/base.py` RS-485 notu

**PCB Tasarımları** (`pcb/`):
- `sensor_node/` — SHT31 + MH-Z19C + BH1750 + kapasitif nem
- `climate_node/` — iklim kontrol kartı
- `irrigation_node/` — sulama kontrol kartı

---

## Klasör Yapısı

```
sera_ai/
├── domain/              # Saf iş mantığı — stdlib only, sıfır dış bağımlılık
│   ├── models.py        # SensorOkuma, Komut, SeraKonfig, SistemKonfig, BitkilProfili
│   ├── state_machine.py # SeraStateMachine: 6 durum, on_gecis callback
│   └── circuit_breaker.py # Per-sera bağımsız CB
│
├── infrastructure/
│   ├── analytics/
│   │   └── sensor_saglik.py  # Anomali, spike, donmuş değer tespiti
│   ├── logging/         # JSONLLogger, LokiLogger, MockLogger, LogDispatcher
│   ├── mqtt/
│   │   ├── base.py, mock.py, broker.py, topics.py
│   │   ├── baglanti_yoneticisi.py  # Bağlantı yöneticisi
│   │   └── broker_auth.py          # MQTT broker kimlik doğrulama
│   ├── notifications/   # BildirimKanalBase, Telegram, MockBildirim, Dispatcher
│   ├── provisioning/
│   │   ├── cihaz_provisioning.py   # Cihaz kayıt ve kimlik yönetimi
│   │   └── zero_touch.py           # Zero-touch provisioning
│   └── repositories/
│       ├── base.py, sqlite_repository.py
│       └── cihaz_repository.py     # Cihaz kayıtları SQLite
│
├── goruntu/             # Görüntü işleme — kamera hastalık tespiti
│   ├── base.py          # AnalizciBase ABC
│   ├── analizci.py      # Ana analizci
│   ├── model.py         # CNN model tanımı
│   ├── egitim.py        # Model eğitimi CLI
│   ├── esp32_kamera.py  # ESP32-CAM entegrasyonu
│   └── mock.py          # Test mock'u
│
├── grafana/             # Docker Compose + provisioning + 2 dashboard JSON
│
├── sensors/             # Sensör soyutlama — YENİ SENSÖR = SADECE BURAYA
│   ├── base.py          # SensorBase ABC: oku() → dict, olcum_alanlari
│   ├── sht31.py, dht22.py, mh_z19c.py, bh1750.py, kapasitif_nem.py
│   └── mock.py
│
├── drivers/             # Saha node soyutlaması (SahaNodeBase)
│   ├── base.py, esp32_s3.py, mock.py
│
├── merkez/              # Merkez donanım (MerkezKontrolBase)
│   ├── base.py, raspberry_pi.py, mock.py
│
├── application/         # Orkestrasyon
│   ├── control_engine.py  # KontrolMotoru: sensör→optimizer→komut (idempotent)
│   └── event_bus.py       # Senkron pub/sub, OlayTur enum, hata izolasyonlu
│
├── intelligence/        # Karar motoru — optimizer DI ile değiştirilebilir
│   ├── base.py, kural_motoru.py, mock.py
│   ├── feature_extractor.py  # SensorOkuma → 9-dim float32, profil-normalize
│   ├── ml_motor.py           # GradientBoosting+IsolationForest+RandomForest×2
│   ├── rl_ajan.py            # Tabular Q-Learning, 2430 durum, 16 eylem
│   └── egitim.py
│
├── api/                 # FastAPI REST API
│   ├── app.py           # api_uygulamasi_olustur(), Uvicorn ile çalışır
│   ├── jwt_auth.py      # JWT token, bcrypt, kullanıcı DB (SQLite)
│   ├── auth_router.py   # /auth/* endpoint'leri
│   ├── seralar_router.py # /seralar/* — DB destekli sera CRUD
│   ├── sulama_router.py # /sulama/* — sulama grubu yönetimi
│   ├── servis.py        # MerkezApiServisi — gerçek sisteme adaptör
│   ├── metrics.py       # /metrics Prometheus (stdlib, harici lib yok)
│   ├── models.py        # Pydantic request/response modelleri
│   └── auth.py          # Eski X-API-Key (geriye dönük uyum)
│
└── config/
    └── settings.py      # Factory: hepsini çözer

esp32/                   # ESP32-S3 firmware (C/Arduino)
pcb/                     # KiCad şematik ve PCB tasarımları
dashboard/               # React frontend (ayrı bölüm)
config.yaml              # Tüm ayarlar (gizli değer yok — .env'den gelir)
pyproject.toml           # Extras: hardware, api, ml, notifications, dev
CONTEXT.md               # Donanım + mimari kararlar (tam bağlam)
data/seralar.db          # Sera ve bitki profili veritabanı (SQLite)
```

---

## Katman Kuralları

### `domain/` — Değişmez Çekirdek
- Yalnızca stdlib: `dataclasses`, `enum`, `datetime`, `uuid`, `time`, `typing`
- Runtime `from ..application...` import yasağı
- `state_machine.py`: EventBus'a `on_gecis: Callable[[dict], None]` ile bağlanır

### `sensors/` — Sensör Soyutlama ← YENİ SENSÖR BURAYA
- `SensorBase.oku() → dict` tek sözleşme
- Donanım kütüphaneleri lazy import — yoksa IOError döner
- **Yeni sensör:** `sensors/yeni.py` → `config/settings.py:sensor_olustur()` → `config.yaml`

### `intelligence/` — Optimizer DI
- `ACİL_DURDUR` → her zaman `HedefDeger()` (güvenlik kuralı, ML/RL'e danışılmaz)
- Anomali → `KuralMotoru` fallback
- `sklearn` yoksa sessiz degradasyon

### `api/` — FastAPI
- Uvicorn ile çalışır (`--api` flag)
- JWT auth: `jwt_auth.py` — admin varsayılan şifre `ADMIN_SIFRE` env, yoksa `sera2024!`
- Sera CRUD: `seralar_router.py` — `data/seralar.db` SQLite, seed: s1/s2/s3
- Rate limit: 60 req/min per IP (`/sistem/saglik` muaf)

---

## Mevcut Durum

**Versiyon:** 0.7.0 — `2026-03-24`

### Tamamlananlar (önceki)
- [x] İki katmanlı donanım soyutlaması, state machine, circuit breaker, event bus
- [x] `intelligence/` — KuralMotoru + MLOptimizer + RLAjan (2430 durum, 16 eylem)
- [x] `sensors/` soyutlama katmanı — SHT31, MH-Z19C, BH1750, kapasitif nem, DHT22, mock
- [x] `infrastructure/` — MQTT, SQLite repositories, Grafana/Loki, Telegram bildirimleri
- [x] Flask → **FastAPI** geçişi — `/api/v1/`, async, Pydantic, slowapi rate limit
- [x] **PCB tasarımları** — 3 node KiCad şematik + layout (sensor, climate, irrigation)

### Tamamlananlar (v0.7.0 — bu oturum)
- [x] **JWT kimlik doğrulama** (`api/jwt_auth.py` + `api/auth_router.py`)
  - bcrypt şifre hash, JWT access/refresh token
  - `/auth/login`, `/auth/sifre-dogrula`, `/auth/sifre-degistir`
  - Admin otomatik oluşturma, kullanıcı yönetimi endpoint'leri
- [x] **DB destekli sera yönetimi** (`api/seralar_router.py`)
  - `data/seralar.db` SQLite — seralar + bitki_profilleri tabloları
  - Sera CRUD, bitki profilleri, `_sync_servis()` ile in-memory senkron
  - Seed: s1 Domates, s2 Biber, s3 Marul + 5 bitki profili
- [x] **Sulama router** (`api/sulama_router.py`) — sulama grubu yönetimi
- [x] **Cihaz provisioning** (`infrastructure/provisioning/`)
  - `cihaz_provisioning.py` — cihaz kayıt, kimlik, MQTT şifre üretimi
  - `zero_touch.py` — zero-touch eşleştirme akışı
  - `infrastructure/repositories/cihaz_repository.py`
  - `infrastructure/mqtt/baglanti_yoneticisi.py`, `broker_auth.py`
- [x] **Görüntü işleme iskeleti** (`sera_ai/goruntu/`)
  - CNN tabanlı hastalık/zararlı tespiti, ESP32-CAM entegrasyonu
  - `AnalizciBase` ABC, mock analizci, eğitim CLI
- [x] **Sensör sağlık izleme** (`infrastructure/analytics/sensor_saglik.py`)
  - Anomali tespiti, spike dedektörü, donmuş değer tespiti
- [x] **React dashboard** — tam özellikli
  - Sayfalar: GenelBakis, Grafikler, AlarmMerkezi, Sulama, SulamaGrup, Ekonomi, LogKomutlar, Ayarlar, CihazDetay
  - Komut kaynağı takibi (sistem/manuel/alarm) — `KaynakBadge`
  - `GoruntuAnaliz` bileşeni (kamera analiz UI)
- [x] **KomutGuvenlik sistemi** — localStorage persist, timeout YOK
  - Şifre doğrulama → kilit açılır, sayfa yenilemede durum korunur
  - Sadece "Kilitle" butonuyla manuel kilitlenir
  - Kilitli sayfalara erişimde otomatik şifre modal
- [x] **Navbar sulama dropdown** — "💧 Sulama Sistemi" / "📋 Sulama Grupları"
- [x] **Login sayfası kaldırıldı** — direkt dashboard, kilit sistemi yeterli
- [x] **Ayarlar sayfası**
  - Sensör tipleri: mock / mqtt / rs485 (esp32_s3 kaldırıldı)
  - MQTT Topic alanı sadece mqtt seçilince görünür
  - Cihaz formu: Cihaz ID + Sera select (DB'den) + Bağlantı Tipi + MAC + Firmware
  - Sera listesinde sıcaklık/nem gösterimi kaldırıldı
- [x] **526 test, 0 hata**

### Sıradaki — Öncelik Sırası

#### Acil (bugün — gerçek donanım için şart)
- [ ] **ESP32 firmware** (`esp32/`) — sensör okuma + MQTT yayını + komut ACK
  - SHT31, MH-Z19C, BH1750, kapasitif nem → `sera/{id}/sensor` topic
  - Backend + provisioning hazır, firmware tek eksik

#### Kısa vade (en güçlü AI özelliği)
- [ ] **Görüntü işleme model eğitimi** (`sera_ai/goruntu/egitim.py`)
  - Transfer learning: MobileNetV3 + 200+ hastalıklı yaprak fotoğrafı
  - Hedef: "erken evre külleme/mildiyö tespiti" kameradan
  - ESP32-CAM entegrasyonu (`goruntu/esp32_kamera.py` iskelet hazır)

#### Kısa vade (yatırımcı/çiftçi ikna aracı)
- [ ] **Ekonomi sayfası** (şu an kilitli/boş)
  - Su tüketimi × tarife, enerji × elektrik fiyatı
  - Beklenen verim × piyasa fiyatı → ROI hesabı
  - Sezon bazlı maliyet/gelir grafiği

#### Orta vade (saha kullanımı)
- [ ] **PWA / mobil uyumluluk** — çiftçi telefona bakıyor, desktop yetmez
  - `manifest.json` + service worker + responsive breakpoint'ler
- [ ] **Tahminsel alarm** — reaktif değil proaktif
  - Trend analizi: "90 dakika içinde kritik eşik aşılacak"
  - Şu an: "sıcaklık şu an yüksek" → Hedef: "şimdi müdahale et"

#### Uzun vade (ölçek)
- [ ] **Federe öğrenme** — N çiftlikte paylaşımlı RL
  - Her sera kendi Q-tablosunu eğitir, merkezi sunucuda birleştirilir
  - Tek çiftçinin yıllarda öğreneceğini sistem haftada öğrenir
- [ ] **Dijital ikiz** — "biber yerine domates ekleseydin %23 daha kârlıydı"
- [ ] **Karbon/su verimliliği metrikleri** → AB tarım teşvik/hibe uyumluluğu
- [ ] Sesli asistan (Türkçe) — Adım 4
- [ ] Siemens S7-1200 / Modbus TCP (donanım gelince)

---

## Komutlar

```bash
# Geliştirme
~/.local/bin/uv run --extra api python -m sera_ai --demo --api   # terminal 1 — Uvicorn :5000
cd dashboard && npm run dev                                        # terminal 2 — Vite :5173

# Production build
cd dashboard && npm run build

# Test (tam suite)
~/.local/bin/uv run --with pytest --with flask --with flask-cors \
  --with scikit-learn --with numpy --with joblib \
  pytest tests/ -q

# Çoklu sera demo
~/.local/bin/uv run --with numpy --with joblib python demo_komplet.py

# ML model eğitimi
~/.local/bin/uv run --with scikit-learn --with numpy --with joblib \
  python -m sera_ai.intelligence.egitim --hepsi --n 1000

# Görüntü modeli eğitimi
~/.local/bin/uv run python -m sera_ai.goruntu.egitim

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
  │     api/ ←── jwt_auth / seralar_router / sulama_router
  └────────────────────────────────────────────────────────

goruntu/  ←── bağımsız modül, api/ üzerinden servis edilir
```

---

## Önemli Tasarım Kararları

| Karar | Neden |
|-------|-------|
| `on_gecis` callback | domain → application runtime import yasağı |
| `SensorBase.oku() → dict` | Sensör değiştirmek = sadece sensors/ dosyası |
| `ACİL_DURDUR` → `HedefDeger()` | Güvenlik kuralı, ML/RL'e danışılmaz |
| Per-sera CircuitBreaker | Sera C arızası A/B'yi etkilemez |
| Lazy hardware imports | smbus2/serial olmadan import hatası vermez |
| JSONL structured log | Grafana/Loki uyumlu |
| JWT + KomutGuvenlik iki katman | JWT = sistem erişimi, KomutGuvenlik = komut onayı |
| Login sayfası yok | KomutGuvenlik kilidi yeterli — dashboard her zaman açık |
| KomutGuvenlik localStorage | Sayfa yenilemede kilit durumu korunur, timeout yok |
| `seralar_router` DB önce | FastAPI route sırası: DB router, sonra v1 router |
