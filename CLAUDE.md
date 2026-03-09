# CLAUDE.md — Sera AI Proje Rehberi

> **Kural:** Her `git commit` öncesinde bu dosyayı güncelle.
> Yeni dosyalar, tamamlanan görevler, değişen durum, yeni komutlar burada yansımalı.

---

## Proje Amacı

Endüstriyel sera otomasyonu: ESP32-S3 sensör nodları → MQTT → Raspberry Pi 5 merkez kontrol.
Sıcaklık, nem, CO₂, toprak nemi gibi parametreleri izler; ısıtıcı, sulama, soğutma, fan
aktüatörlerini otomatik kontrol eder. ML katmanı verim tahmini ve anomali tespiti yapar.

---

## Klasör Yapısı

```
sera_ai/
├── domain/              # Saf iş mantığı — sıfır dış bağımlılık (stdlib only)
│   ├── models.py        # SensorOkuma, Komut, SeraKonfig, SistemKonfig, BitkilProfili
│   ├── state_machine.py # SeraStateMachine: BASLATILAMADI→NORMAL→UYARI→ALARM→ACİL_DURDUR
│   └── circuit_breaker.py # CircuitBreaker: KAPALI/ACIK/YARI_ACIK, per-sera bağımsız
│
├── application/         # Orkestrasyon — domain'i birbirine bağlar
│   ├── control_engine.py  # KontrolMotoru: sensör→optimizer→komut (idempotent)
│   └── event_bus.py       # EventBus: pub/sub, OlayTur enum, hata izolasyonlu
│
├── intelligence/        # Karar motoru — optimizer DI ile değiştirilebilir
│   ├── base.py            # OptimizerBase ABC + HedefDeger dataclass
│   ├── kural_motoru.py    # KuralMotoru: deterministik if/else (varsayılan, sklearn gerekmez)
│   ├── mock.py            # MockOptimizer: test için sabit değer, çağrı sayacı
│   ├── feature_extractor.py # SensorOkuma → 9-dim float32 numpy vektör
│   ├── ml_motor.py        # MLOptimizer: GradientBoosting+IsolationForest+RandomForest×2
│   └── egitim.py          # Offline eğitim scripti + sentetik veri üretimi
│
├── drivers/             # Saha donanım soyutlaması (SahaNodeBase)
│   ├── base.py            # SahaNodeBase ABC: baglan/sensor_oku/komut_gonder/kapat
│   ├── esp32_s3.py        # ESP32S3Node: WiFi/MQTT, thread-safe Queue, paho-mqtt
│   └── mock.py            # MockSahaNode: Gauss drift fizik simülasyonu, test assertion
│
├── merkez/              # Merkez donanım soyutlaması (MerkezKontrolBase)
│   ├── base.py            # MerkezKontrolBase ABC + Modbus TCP placeholder (Siemens S7-1200)
│   ├── raspberry_pi.py    # RaspberryPiMerkez: daemon thread, per-sera CB+SM+Motor
│   └── mock.py            # MockMerkez: komut geçmişi kayıtlı, integration test için
│
├── config/
│   └── settings.py      # konfig_yukle(), saha_node_olustur(), merkez_olustur(),
│                        #   optimizer_olustur(), tam_sistem_kur()
│
├── api/                 # Flask REST API
│   ├── app.py           # api_uygulamasi_olustur(), SeraApiServisi, before_request auth
│   └── auth.py          # check_api_key(), MUAF_ENDPOINTLER
│
├── infrastructure/      # İskelet — henüz implementasyon yok
│   ├── repositories/    # SQLite → InfluxDB geçişi için Repository pattern
│   └── notifications/   # Telegram / WhatsApp / e-posta (config.yaml'dan aktif edilir)
│
└── __main__.py          # CLI: --demo, --adim, --config; Windows UTF-8 fix

config.yaml              # Tüm ayarlar burada (gizli değer yok — .env'den gelir)
pyproject.toml           # Bağımlılıklar + extras: hardware, api, ml, notifications, dev
tests/
├── conftest.py          # Paylaşılan fixture'lar
├── unit/                # test_state_machine, test_circuit_breaker, test_rules,
│   │                    #   test_api_auth, test_intelligence, test_ml_motor
└── integration/         # test_control_engine
```

---

## Katman Kuralları

### `domain/` — Değişmez Çekirdek
- **Bağımlılık yasağı:** Hiçbir driver, framework, ML kütüphanesi import edilemez.
- Sadece stdlib: `dataclasses`, `enum`, `datetime`, `uuid`, `time`, `typing`.
- `state_machine.py`: EventBus'a `on_gecis: Callable[[dict], None]` callback ile bağlanır.
  Runtime `from ..application...` import'u **yasaktır** — daha önce temizlendi.

### `application/` — Orkestrasyon
- Domain + intelligence katmanlarını birbirine bağlar.
- `KontrolMotoru`: `optimizer=None` ise `KuralMotoru` otomatik kullanılır.
- `EventBus`: senkron, hata izolasyonlu (bir subscriber crash'i diğerini etkilemez).

### `intelligence/` — Optimizer DI
- `OptimizerBase.hedef_hesapla(sensor, durum) → HedefDeger` tek sözleşme.
- `KuralMotoru`: varsayılan, sklearn gerektirmez.
- `MLOptimizer`: ilk çalıştırmada otomatik eğitim; `models/` klasörüne `.pkl` yazar.
  Anomali → `KuralMotoru` fallback. `ACİL_DURDUR` → her zaman `HedefDeger()` (güvenlik).
- Yeni optimizer eklemek = yeni dosya + `config.yaml`'da `optimizer: yeni_tip`.

### `drivers/` — Saha Donanım
- `SahaNodeBase` ABC'den türer, 4 metot implement edilir.
- İş mantığı (eşik, karar, log) **yasak** — sadece "donanımla konuş".
- Yeni donanım eklemek = yeni dosya + `settings.py:saha_node_olustur()`'e 3 satır.

### `merkez/` — Merkez Donanım
- `MerkezKontrolBase` ABC'den türer.
- `raspberry_pi.py`: per-sera bağımsız CB + SM + KontrolMotoru; daemon thread döngüsü.
- Modbus TCP / Siemens S7-1200: `merkez/base.py`'de yorum olarak yer tutucu.

### `config/settings.py` — Factory
- `konfig_yukle()`: YAML → `SistemKonfig` (ortam değişkeni > YAML > kod varsayılanı).
- `saha_node_olustur()`, `merkez_olustur()`, `optimizer_olustur()`: tip → concrete sınıf.
- Yeni donanım/optimizer tipi → **sadece bu fonksiyon** güncellenir.

### `api/` — REST Katmanı
- `X-API-Key` middleware (`before_request`), `/api/sistem/saglik` muaf.
- API key değeri değil, env var adı config'de: `api_key_env: SERA_API_KEY`.

---

## Mevcut Durum

**Versiyon:** 0.2.0 — `2026-03-10`

### Tamamlananlar
- [x] İki katmanlı donanım soyutlaması: `SahaNodeBase` + `MerkezKontrolBase`
- [x] `config.yaml` driven hardware switching (`mock` / `esp32_s3` / `raspberry_pi`)
- [x] State machine (6 durum), Circuit breaker (per-sera bağımsız)
- [x] Event bus (pub/sub, hata izolasyonlu)
- [x] `KontrolMotoru` — idempotent komut mantığı
- [x] `intelligence/` katmanı — `OptimizerBase` + `KuralMotoru` + `MockOptimizer`
- [x] `MLOptimizer` — GradientBoosting, IsolationForest, RandomForest×2; otomatik eğitim
- [x] `FeatureExtractor` — 9-dim profil-bağımlı normalizasyon
- [x] `egitim.py` — CLI eğitim scripti, sentetik veri, tüm bitki profilleri
- [x] `optimizer_olustur()` factory — `config.yaml`'dan `kural_motoru` | `ml_motor`
- [x] Flask REST API + X-API-Key auth middleware
- [x] `--demo` CLI modu (mock sensör, terminal çıktısı)
- [x] domain → application bağımlılığı temizlendi (`on_gecis` callback pattern)
- [x] **112 test, 0 hata**

### Devam Edenler / Sıradaki
- [ ] `infrastructure/repositories/` — SQLite implementasyonu (Repository pattern iskelet hazır)
- [ ] `infrastructure/notifications/` — Telegram/WhatsApp/e-posta (config.yaml flag'leri hazır)
- [ ] `intelligence/` — RL ajanı iskelet (`RLAjan(OptimizerBase)`)
- [ ] Siemens S7-1200 / Modbus TCP — `merkez/siemens_s7.py` (placeholder `base.py`'de)
- [ ] STM32 / RS-485 — `drivers/stm32.py` (placeholder `drivers/base.py`'de)
- [ ] Arduino Mega — `drivers/arduino.py`
- [ ] Grafana/Loki — JSONL log formatı hazır (`sera_system.jsonl`)
- [ ] InfluxDB — Repository pattern geçişi

---

## Sık Kullanılan Komutlar

```bash
# Test çalıştır (tam suite)
~/.local/bin/uv run --with pytest --with flask --with flask-cors \
  --with scikit-learn --with numpy --with joblib \
  pytest tests/ -q

# Demo modu (mock donanım, terminal çıktısı)
~/.local/bin/uv run --with flask --with flask-cors \
  python -m sera_ai --demo --adim 20

# ML model eğitimi (tek bitki)
~/.local/bin/uv run --with scikit-learn --with numpy --with joblib \
  python -m sera_ai.intelligence.egitim --bitki Domates

# ML model eğitimi (tüm bitkiler)
~/.local/bin/uv run --with scikit-learn --with numpy --with joblib \
  python -m sera_ai.intelligence.egitim --hepsi --n 1000

# API sunucusu başlat (config.yaml'daki port: 5000)
~/.local/bin/uv run --with flask --with flask-cors python -m sera_ai

# Belirli test dosyası
~/.local/bin/uv run --with pytest ... pytest tests/unit/test_ml_motor.py -v

# Git log (son 5)
git log --oneline -5
```

---

## Donanım Kararları

| Katman | Şu an | İleride |
|--------|--------|---------|
| Saha node | `mock` (simülasyon) | `esp32_s3` (WiFi/MQTT) |
| Merkez | `mock` | `raspberry_pi` (RPi 5, daemon thread) |
| Saha iletişim | MQTT (paho-mqtt) | RS-485 (STM32), USB Serial (Arduino Mega) |
| Merkez iletişim | — | Modbus TCP (Siemens S7-1200, python-snap7/pymodbus) |

**Geçiş:** `config.yaml`'da tek satır değişikliği yeter — fabrika fonksiyonlar gerisini halleder.

```yaml
donanim:
  saha:   esp32_s3     # mock → esp32_s3
  merkez: raspberry_pi # mock → raspberry_pi
```

**Yeni donanım eklemek:**
1. `drivers/yeni_donanim.py` — `SahaNodeBase` implement et
2. `config/settings.py:saha_node_olustur()` — `if tip == "yeni_donanim":` ekle
3. `config.yaml`'da `saha: yeni_donanim` yaz
4. Başka hiçbir dosyaya dokunma.

---

## Bağımlılık Haritası (import yönü)

```
domain ←── application ←── intelligence
  ↑              ↑               ↑
drivers        merkez          config/settings (factory)
                 ↑
               api/
```

- `domain` hiçbir şeyi import etmez (stdlib hariç)
- `application` sadece `domain` + `intelligence` import eder
- `merkez` hepsini görür (koordinatör)
- `config/settings` factory: tipleri çözer, concrete sınıfları oluşturur

---

## Önemli Tasarım Kararları

| Karar | Neden |
|-------|-------|
| `on_gecis` callback (state_machine) | domain → application runtime import yasağı |
| `optimizer=None` → `KuralMotoru` | sklearn olmadan da çalışır; ML isteğe bağlı |
| `MLOptimizer` otomatik eğitim | İlk çalıştırmada sıfır kurulum; prod'da önceden eğit |
| `IsolationForest` anomali fallback | Bozuk sensör → güvenli KuralMotoru, sistem durmuyor |
| `ACİL_DURDUR` → `HedefDeger()` | ML'e danışılmaz; güvenlik kuralı her zaman önce gelir |
| Idempotent komutlar | Son aktüatör önbellekte; değişiklik yoksa komut gönderilmez |
| Per-sera CircuitBreaker | Sera C arızası Sera A/B'yi durdurmaz |
| JSONL structured log | Grafana/Loki uyumlu; ileride sorgulanabilir |
