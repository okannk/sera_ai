# SERA AI — PROJE BAĞLAMI
# Versiyon: 2.0 | Tarih: 2026-03

---

## PROJENİN AMACI

ESP32-S3 + Raspberry Pi 5 tabanlı endüstriyel sera otomasyon sistemi.
Her sera için bağımsız ESP32-S3 sensör nodu, merkez kontrol Raspberry Pi 5'te çalışır.
Hobi projesi değil — gerçek tarımsal üretimde kullanılacak, arıza toleranslı, AI destekli sistem.

---

## DONANIM STACK (GERÇEK)

### Merkez
- **Raspberry Pi 5** — Python kontrol sistemi burda çalışır
  - MQTT broker (Mosquitto) host eder
  - Flask REST API
  - ML inference + state machine

### Saha (Her Sera İçin Ayrı)
- **ESP32-S3** — WiFi/MQTT saha nodu
  - I2C bus: SHT31 + BH1750
  - UART: MH-Z19C
  - ADC: Kapasitif toprak nem
  - Dijital çıkış → SSR röle (aktüatör kontrolü)

### Sensörler
| Sensör | Model | İletişim | Ölçüm |
|--------|-------|----------|-------|
| Sıcaklık / Nem | SHT31-D (Sensirion) | I2C 0x44 | T ±0.3°C, H ±2% RH |
| CO₂ | MH-Z19C (Winsen) | UART 9600 | 400–5000 ppm, ±(50+5%) |
| Işık | BH1750FVI (ROHM) | I2C 0x23 | 1–65535 lux |
| Toprak Nemi | Kapasitif (generik) | ADC (ADS1115 veya ESP32 ADC) | 0–1023 |

**Eski/Fallback (destekleniyor ama önerilmiyor):**
- DHT22 → SHT31 ile değiştirin (daha doğru, CRC korumalı, I2C)

### Aktüatörler
- **SSR (Solid State Röle)** — 4 kanal: sulama, ısıtıcı, soğutma/fan, aydınlatma
  - Mekanik röleye göre daha sessiz, uzun ömürlü, hızlı anahtarlama

### İletişim
- **MQTT** (ESP32 → RPi): `sera/{node_id}/sensor` yayın, `sera/{node_id}/komut` komut
- **I2C** (SHT31, BH1750): RPi/ESP32 dahili bus
- **UART** (MH-Z19C): `/dev/ttyS0` (RPi) veya ESP32 hardware UART

---

## YAZILIM MİMARİSİ

### Temel Prensipler
1. Her katman bağımsız test edilebilir
2. Domain iş mantığı hiçbir framework'e bağımlı değil (stdlib only)
3. Donanım değişince Python kodu değişmez — sadece `config.yaml`
4. **Sensör değiştirmek = `sensors/` altına yeni driver, başka hiçbir şey değişmez**
5. Her karar loglanır, izlenebilir (JSONL, tx_id ile)

### Klasör Yapısı (Güncel)
```
sera_ai/
├── domain/              # Saf iş mantığı — stdlib only, sıfır dış bağımlılık
│   ├── models.py        # SensorOkuma, Komut, SeraKonfig, SistemKonfig
│   ├── state_machine.py # 6 durum: BASLATILAMADI→NORMAL→UYARI→ALARM→ACİL_DURDUR
│   └── circuit_breaker.py
│
├── sensors/             # Sensör soyutlama — YENI SENSÖR = SADECE BURAYA
│   ├── base.py          # SensorBase ABC: oku() → dict
│   ├── sht31.py         # I2C, T+H (smbus2)
│   ├── dht22.py         # GPIO, T+H fallback (adafruit_dht)
│   ├── mh_z19c.py       # UART, CO₂ (pyserial)
│   ├── bh1750.py        # I2C, ışık (smbus2)
│   ├── kapasitif_nem.py # ADC, toprak nemi (ADS1115)
│   └── mock.py          # Test için sabit/gürültülü değer
│
├── drivers/             # Saha node soyutlaması (SahaNodeBase)
│   ├── base.py          # ABC: baglan/sensor_oku/komut_gonder/kapat
│   ├── esp32_s3.py      # MQTT client, thread-safe Queue
│   └── mock.py          # Gauss drift simülasyonu
│
├── merkez/              # Merkez donanım (MerkezKontrolBase)
│   ├── base.py          # ABC + Modbus TCP placeholder
│   ├── raspberry_pi.py  # Daemon thread, per-sera CB+SM+Motor
│   └── mock.py
│
├── application/         # Orkestrasyon
│   ├── control_engine.py  # KontrolMotoru (idempotent, optimizer DI)
│   └── event_bus.py
│
├── intelligence/        # Karar motoru (optimizer DI)
│   ├── base.py          # OptimizerBase + HedefDeger
│   ├── kural_motoru.py  # Deterministik if/else (varsayılan)
│   ├── ml_motor.py      # GradientBoosting + IsolationForest + RandomForest
│   ├── feature_extractor.py
│   ├── egitim.py        # CLI: python -m sera_ai.intelligence.egitim
│   └── mock.py
│
├── config/
│   └── settings.py      # factory: saha_node_olustur, sensor_olustur, optimizer_olustur
│
├── api/                 # Flask REST + X-API-Key auth
│   ├── app.py
│   └── auth.py
│
└── infrastructure/      # İskelet — repository, notifications
```

### Sensör Soyutlama — Değişmez Kural

```
sensors/
  SensorBase.oku() → dict   (her sensör kendi key'lerini döndürür)
  SahaNode bu dict'leri birleştirir → SensorOkuma

Yeni sensör eklemek:
  1. sensors/yeni_sensor.py  (SensorBase implement et)
  2. config/settings.py:sensor_olustur()  (3 satır if bloğu)
  3. config.yaml'da: - tip: yeni_sensor
  4. Başka HİÇBİR DOSYA değişmez.
```

### Donanım Değiştirme
```yaml
# config.yaml — tek satır değişikliği yeter
donanim:
  saha:   esp32_s3     # mock → esp32_s3
  merkez: raspberry_pi # mock → raspberry_pi

intelligence:
  optimizer: ml_motor  # kural_motoru → ml_motor

# Per-sera sensör listesi
sera:
  seralar:
    - id: s1
      sensorler:
        - tip: sht31
          adres: 0x44
        - tip: mh_z19c
          port: /dev/ttyS0
```

---

## MİMARİ KARARLAR

### 1. State Machine
6 durum: BASLATILAMADI → NORMAL → UYARI → ALARM → ACİL_DURDUR → MANUEL_KONTROL
Geçişler loglanır: "NORMAL → ALARM, sebep: T=34°C, tx=a3f2"

### 2. Circuit Breaker
3 durum: KAPALI / YARI_ACIK / ACIK
Per-sera bağımsız: Sera C arızalanınca A ve B çalışmaya devam eder.

### 3. Event Bus
Senkron pub/sub, hata izolasyonlu. Modüller birbirini import etmez.
Olaylar: SENSOR_OKUMA, DURUM_DEGISTI, KOMUT_GONDERILDI, CB_ACILDI, SISTEM_HATASI

### 4. Optimizer DI
```python
motor = KontrolMotoru(..., optimizer=None)           # KuralMotoru otomatik
motor = KontrolMotoru(..., optimizer=MLOptimizer(.)) # ML ile
```
ACİL_DURDUR → her zaman HedefDeger() (güvenlik kuralı, ML'e danışılmaz)
Anomali → KuralMotoru fallback

### 5. domain → application bağımlılığı yok
state_machine.py OlayTur'u import etmez.
Bağlantı `on_gecis: Callable[[dict], None]` callback ile kurulur.

### 6. Idempotent Komutlar
Son aktüatör durumu önbellekte. Değişiklik yoksa komut gönderilmez.

---

## GÜVENLİK
- REST API: X-API-Key header zorunlu (`/api/sistem/saglik` muaf)
- Gizli değerler .env'de: MQTT_KULLANICI, MQTT_SIFRE, SERA_API_KEY, TELEGRAM_TOKEN
- MQTT: TLS + kullanıcı/şifre (internet'e açıksa)
- ESP32 VLAN'da — sadece MQTT broker'a konuşur

---

## DEPLOYMENT (Raspberry Pi 5)

```bash
# Sistem servisi
sudo systemctl enable sera_ai
sudo systemctl start sera_ai
journalctl -u sera_ai -f

# ML model ön eğitimi (prod'da saha verisiyle)
python -m sera_ai.intelligence.egitim --hepsi --n 2000
```

```ini
# /etc/systemd/system/sera_ai.service
[Service]
User=sera
WorkingDirectory=/opt/sera_ai
EnvironmentFile=/opt/sera_ai/.env
ExecStart=/opt/sera_ai/venv/bin/python -m sera_ai
Restart=on-failure
RestartSec=10
```
