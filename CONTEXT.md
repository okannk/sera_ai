# SERA AI — PROJE BAĞLAMI
# Claude Code'a verilecek başlangıç dosyası
# Versiyon: 1.0 | Tarih: 2025

---

## PROJENİN AMACI

Arduino Mega 2560 tabanlı sera otomasyon sistemi.
Tek serayla başlayıp çok seraya ölçeklenebilir,
endüstriyel güvenilirlikte, AI destekli kontrol sistemi.

Hedef: Hobi projesi değil, gerçek tarımsal üretimde
kullanılabilecek, arıza toleranslı, izlenebilir sistem.

---

## DONANIM (Mevcut ve Planlanan)

### Mevcut
- Arduino Mega 2560 (USB/Serial bağlantı)
- DHT22 — sıcaklık/nem sensörü
- MQ-135 — CO2 sensörü
- Toprak nem sensörü (analog)
- 4 kanallı röle modülü (sulama, ısıtıcı, fan, ışık)

### Kısa Vadeli Plan
- ESP32-S3 — her sera için ayrı kablosuz node
- Raspberry Pi 5 — merkez kontrol (Python AI buraya taşınır)
- RS-485 hattı — gürültülü ortam için kablolu iletişim

### Uzun Vadeli Plan
- PLC (Siemens LOGO veya Omron CP1E) — kritik aktüatörler
- UPS — güç kesintisi koruması
- LoRa — çok binalı kurulum için

---

## YAZILIM MİMARİSİ

### Temel Prensipler
1. Her katman bağımsız test edilebilir olmalı
2. Domain iş mantığı hiçbir framework'e bağımlı olmamalı
3. Transport değişince (Serial → MQTT → RS485) iş mantığı değişmemeli
4. Konfigürasyon kod içinde değil, config dosyasında
5. Her karar loglanmalı, izlenebilir olmalı

### Klasör Yapısı (Hedef)
```
sera_ai/
├── sera_ai/                  # Ana Python paketi
│   ├── __init__.py
│   ├── domain/               # İş mantığı — hiçbir şeye bağımlı değil
│   │   ├── models.py         # SensorOkuma, Komut, Durum dataclass'ları
│   │   ├── state_machine.py  # SeraStateMachine
│   │   ├── rules.py          # Karar kuralları (hangi sensörde ne yapılır)
│   │   └── profiles.py       # Bitki profilleri (Domates, Biber, Marul)
│   ├── infrastructure/       # Dış dünya bağlantıları
│   │   ├── transport/
│   │   │   ├── base.py       # Transport ABC
│   │   │   ├── serial_transport.py
│   │   │   ├── mqtt_transport.py
│   │   │   └── mock_transport.py
│   │   ├── repositories/
│   │   │   ├── base.py       # Repository ABC
│   │   │   ├── sqlite_repo.py
│   │   │   └── influxdb_repo.py
│   │   └── notifications/
│   │       ├── base.py
│   │       ├── telegram.py
│   │       ├── whatsapp.py
│   │       └── email_notif.py
│   ├── application/          # Use case'ler — domain + infra birleşir
│   │   ├── control_engine.py # KontrolMotoru
│   │   ├── alarm_service.py  # Alarm yönetimi
│   │   └── scheduler.py      # Zamanlanmış görevler
│   ├── api/                  # Flask REST API
│   │   ├── app.py
│   │   └── routes.py
│   └── config/
│       ├── settings.py       # Pydantic Settings
│       └── config.yaml       # Varsayılan değerler
├── tests/
│   ├── unit/
│   │   ├── test_state_machine.py
│   │   ├── test_rules.py
│   │   └── test_circuit_breaker.py
│   ├── integration/
│   │   ├── test_control_engine.py
│   │   └── test_api.py
│   └── conftest.py           # Pytest fixtures
├── scripts/
│   └── deploy/
│       └── sera_ai.service   # systemd unit dosyası
├── docs/
│   └── architecture.md       # Mimari kararlar ve gerekçeleri
├── .env.example              # Ortam değişkeni şablonu
├── config.yaml               # Kullanıcı konfigürasyonu
├── pyproject.toml            # Modern Python proje tanımı
└── README.md
```

---

## MİMARİ KARARLAR (Güncel — v0.2)

### 0. İKİ KATMANLI DONANIM MİMARİSİ (YENİ)

**Saha Katmanı** (`drivers/`) — Her sera için bağımsız node:
- `SahaNodeBase` ABC: `baglan()`, `sensor_oku()`, `komut_gonder()`, `kapat()`
- `ESP32S3Node`: WiFi/MQTT üzerinden haberleşme
- `MockSahaNode`: Test/demo, sıfır bağımlılık

**Merkez Katmanı** (`merkez/`) — Tüm sistemin beyni:
- `MerkezKontrolBase` ABC: node yönetimi + kontrol döngüsü
- `RaspberryPiMerkez`: Python thread döngüsü, şu an kullanılan
- `MockMerkez`: Entegrasyon testleri için
- **Gelecek**: `SiemensS71200Merkez` (Modbus TCP — `merkez/base.py`'de yorum olarak hazır)

**Kural**: Sistem geri kalanı (state machine, ML, API, bildirim) sadece
`SahaNodeBase` ve `MerkezKontrolBase` arayüzlerini görür.

**Donanım değiştirmek**: `config.yaml`'da iki satır:
```yaml
donanim:
  saha:   esp32_s3      # → ESP32S3Node devreye girer
  merkez: raspberry_pi  # → RaspberryPiMerkez devreye girer
```

---

## ŞU ANA KADAR ALINAN MİMARİ KARARLAR

### 1. State Machine
**Neden:** `if/else` yığını yerine, her sera açık bir durumda.
Durum geçişleri loglanır, nereden nereye nasıl geçildiği izlenebilir.

**Durumlar:**
- BASLATILAMADI → NORMAL → UYARI → ALARM → ACİL_DURDUR
- MANUEL_KONTROL (operatör devraldı)

**Geçiş kuralı:** Durum kötüleşince bildirim gönderilir,
iyileşince iyileşme bildirimi gönderilir.

### 2. Circuit Breaker
**Neden:** Arduino yanıt vermeyince sistem çökmemeli.
5 hata → CB açılır → 60 saniye bekle → yarı açık → test et → kapat.

**Üç durum:** KAPALI (normal) / YARI_ACIK (test ediyor) / ACIK (devre dışı)

**Kritik:** Her sera için ayrı CB. Sera C arızalanınca A ve B çalışmaya devam eder.

### 3. Event Bus (Yayın/Abone)
**Neden:** Modüller birbirini import etmemeli.
Kontrol motoru bildirim sisteminin varlığından haberdar olmamalı.
Durum değişikliği olayı yayınlar, bildirim sistemi dinler.

**Olaylar:** SENSOR_OKUMA, DURUM_DEGISTI, KOMUT_GONDERILDI,
CB_ACILDI, CB_KAPANDI, SISTEM_HATASI

### 4. Repository Pattern
**Neden:** Kontrol motoru verinin nerede saklandığını bilmemeli.
Bugün SQLite, yarın InfluxDB — iş mantığı değişmez.

**Kural:** Domain katmanı repository interface'ini kullanır,
hangi implementation olduğunu bilmez.

### 5. Idempotent Komutlar
**Neden:** Arduino'ya iki kez SULAMA_AC gönderilince sorun olmamalı.
Sistem son aktüatör durumunu önbellekte tutar,
değişiklik yoksa komut gönderilmez.

### 6. Structured Logging
**Neden:** `print()` yetmez. Her log kaydında:
- timestamp (ISO 8601)
- transaction ID (tx_id) — bir olayı baştan sona takip eder
- seviye (INFO/WARNING/ERROR/CRITICAL)
- bağlam (hangi sera, hangi sensör, hangi komut)

Format: JSONL (her satır geçerli JSON) → Grafana/ELK ile işlenebilir.

---

## KONFİGÜRASYON YÖNETİMİ

### Öncelik Sırası
1. Ortam değişkenleri (SERA_MQTT_HOST=...)
2. config.yaml
3. Varsayılan değerler (kod içinde)

### Kritik Ayarlar
```yaml
# config.yaml
sera:
  seralar:
    - id: s1
      isim: "Sera A"
      bitki: Domates
      alan_m2: 500
      serial_port: /dev/ttyUSB0

bitki_profilleri:
  Domates:
    opt_T: 23.0
    min_T: 18.0
    max_T: 28.0
    opt_H: 70.0
    opt_CO2: 1000

sistem:
  sensor_interval_sn: 2.5
  cb_hata_esigi: 5
  cb_recovery_sn: 60
  db_yolu: sera_data.db
  log_dosyasi: sera_system.jsonl

mqtt:
  host: localhost
  port: 1883
  aktif: false

api:
  aktif: true
  port: 5000

bildirim:
  telegram_token: ""
  telegram_chat_id: ""
  bastirma_dk: 10
  sabah_raporu_saat: "07:00"
```

---

## TEST STRATEJİSİ

### Unit Testler (infrastructure olmadan çalışır)
```python
# Örnek — bu seviyede testler olmalı
def test_state_machine_normal_to_alarm():
    sm = SeraStateMachine("s1", DOMATES_PROFIL)
    sensor = SensorOkuma(T=35.0, H=70, co2=900)  # maxT=28 üstünde
    yeni_durum = sm.guncelle(sensor)
    assert yeni_durum == Durum.ALARM

def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker("test_cb", hata_esigi=5, recovery_sn=60)
    for _ in range(5):
        cb.hata_kaydet("Arduino yanıt vermedi")
    assert cb.durum == CBDurum.ACIK

def test_idempotent_command_not_resent():
    motor = KontrolMotoru(transport=MockTransport())
    motor.komut_gonder(Komut.SULAMA_AC)
    motor.komut_gonder(Komut.SULAMA_AC)  # İkinci kez gönderilmemeli
    assert motor.transport.gonderilen_komut_sayisi == 1
```

### Integration Testler (mock transport ile)
- Kontrol motoru → sensör al → karar ver → komut gönder akışı
- API endpoint'leri → doğru HTTP kodu ve body döner mi
- Alarm sistemi → durum değişince bildirim kuyruğa girer mi

### Çalıştırma
```bash
pytest tests/ -v                    # Tümü
pytest tests/unit/ -v               # Sadece unit
pytest tests/ --cov=sera_ai         # Coverage raporu
```

---

## GÜVENLİK

### Minimum Gereksinimler
- REST API: X-API-Key header zorunlu
- MQTT: TLS + kullanıcı/şifre (internet'e açıksa)
- .env dosyası git'e commit edilmez (.gitignore'da)
- Şifreler ve token'lar kodda asla olmaz

### Network
- Sera cihazları (ESP32) ayrı VLAN'da
- Sadece MQTT broker'a konuşabilirler
- İnternet erişimleri yok

---

## DEPLOYMENT

### systemd (Raspberry Pi / Linux)
```ini
[Unit]
Description=Sera AI Kontrol Sistemi
After=network.target

[Service]
Type=simple
User=sera
WorkingDirectory=/opt/sera_ai
EnvironmentFile=/opt/sera_ai/.env
ExecStart=/opt/sera_ai/venv/bin/python -m sera_ai
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Komutlar
```bash
sudo systemctl enable sera_ai   # Açılışta başlat
sudo systemctl start sera_ai    # Başlat
sudo systemctl status sera_ai   # Durum
journalctl -u sera_ai -f        # Canlı log
```

---

## MEVCUT DOSYALAR (Bu Konuşmada Üretildi)

Bu dosyalar `/outputs/` klasöründe mevcut.
Claude Code'a taşınacak ve refactor edilecek:

| Dosya | İçerik | Durum |
|-------|--------|-------|
| sera_endustriyel.py | State machine, CB, Config, Logger, EventBus | Çalışıyor ama monolitik |
| modul1_veritabani.py | SQLite + InfluxDB repository | Çalışıyor |
| modul2_mqtt.py | MQTT bridge, ESP32 simülatörü | Çalışıyor |
| modul3_api.py | Flask REST API | Çalışıyor |
| modul4_bildirim.py | Telegram, WhatsApp, e-posta | Çalışıyor |
| sera_tam_sistem.py | Tüm modülleri birleştiren orkestratör | Çalışıyor |
| ml_motor.py | 4 ML modeli (verim, büyüme, anomali, stres) | Çalışıyor |
| otonom_ajan.py | Q-Learning RL ajanı | Çalışıyor |
| endustriyel_guvenilirlik.py | Blockchain audit, watchdog, yedeklilik | Çalışıyor |
| SeraAIFinal.jsx | React dashboard (7 sekme) | Çalışıyor |
| sera_sim_dashboard.jsx | Tam simülasyon arayüzü | Çalışıyor |

### Bilinen Sorunlar
- Enum kimlik çakışması (farklı modüllerden import) — workaround var ama kök çözüm gerekiyor
- Test yok
- Konfigürasyon hâlâ kod içinde (varsayilan() metodu)
- Tek Python process, deployment mekanizması yok
- API'de authentication yok

---

## CLAUDE CODE İÇİN İLK GÖREVLER

Öncelik sırasıyla:

1. **Proper paket yapısı**: Yukarıdaki klasör yapısına taşı
2. **Pydantic Settings**: config.yaml + env değişkenleri
3. **Unit testler**: State machine, CB, idempotent komutlar
4. **Enum düzeltmesi**: BildirimSeviye/Seviye çakışmasını kökten çöz
5. **API auth**: X-API-Key middleware
6. **systemd service dosyası**: Deployment hazır

---

## BAĞLAM NOTLARI

- Kullanıcı donanım geliştirici, Python öğreniyor
- Türkçe değişken isimleri tercih ediliyor (Türkçe proje)
- Açıklayıcı yorumlar önemli — "neden" yazılmalı, "ne" değil
- Demo mod her zaman çalışmalı (Arduino olmadan test)
- Hata mesajları Türkçe, log kayıtları İngilizce (standart)
