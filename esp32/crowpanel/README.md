# CrowPanel 7.0 — Sera HMI Paneli

> **TEST AMAÇLI** — Bu firmware sadece CrowPanel 7'yi sera sensör terminali olarak
> denemek içindir. Üretim sisteminde bu yaklaşım kullanılmayacak.

## Donanım

- **Elecrow CrowPanel 7.0** (ESP32-S3, 7" IPS 800×480, GT911 kapasitif dokunmatik)
- Güç: USB-C 5V/2A

## Ne Yapar?

```
MQTT Broker (RPi) ──── sera/{id}/sensor ───→ CrowPanel (ekranda göster)
CrowPanel ──────────── sera/{id}/komut  ───→ MQTT Broker → ESP32 Sensör Node
```

- Canlı sensör verisini 7" ekranda gösterir (T, H, CO₂, Işık)
- Eşik aşılınca alarm banner kırmızı yanar
- 5 dokunmatik buton: SULAMA, ISITICI, SOGUTMA, FAN, ISIK
- Aktüatöre dokunmak → MQTT komut gönderir → ESP32 node aktüatörü açar/kapar

## Ekran Düzeni (800×480)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SERA HMI — Domates Serası (s1)                      WiFi OK  MQTT OK       │ ← Başlık
├───────────┬───────────┬───────────┬───────────┬──────────────────────────── │
│ Sıcaklık  │    Nem    │    CO2    │   Işık    │                              │
│  24.5 °C  │  68.0 %   │  850 ppm  │ 3200 lux  │ ← 4 sensör kartı          │
│  ███████░ │  ██████░░ │  ████░░░░ │  ██████░░ │                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✓ Tüm değerler normal sınırlarda                           12s önce        │ ← Alarm bar
├─────────────────────────────────────────────────────────────────────────────┤
│  AKTÜATÖRLER                                                                │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│ │ SULAMA  │ │ ISITICI │ │ SOGUTMA │ │   FAN   │ │  ISIK   │               │ ← Butonlar
│ │ KAPALI  │ │ KAPALI  │ │ KAPALI  │ │  AÇIK   │ │ KAPALI  │               │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Kurulum

### 1. Gerekli Kütüphaneler (Arduino IDE → Library Manager)

| Kütüphane | Versiyon |
|-----------|---------|
| LovyanGFX | v1.1.x |
| PubSubClient | v2.8+ |
| ArduinoJson | v7.x |

### 2. Arduino IDE Ayarları

| Ayar | Değer |
|------|-------|
| Board | ESP32S3 Dev Module |
| PSRAM | OPI PSRAM |
| Flash Size | 16MB (128Mb) |
| CPU Frequency | 240 MHz |
| Partition Scheme | Huge APP (3MB No OTA) |
| Upload Speed | 921600 |

### 3. `sera_panel.ino` İçinde Değiştir

```cpp
#define WIFI_SSID       "WIFI_ADINIZI_YAZIN"
#define WIFI_SIFRE      "WIFI_SIFRENIZI_YAZIN"

#define MQTT_SUNUCU     "192.168.1.100"   // Raspberry Pi IP
#define MQTT_KULLANICI  ""                // MQTT auth varsa
#define MQTT_SIFRE_STR  ""

#define SERA_ID         "s1"              // İzlenecek sera
#define SERA_ISIM       "Domates Serası"  // Ekranda gösterilecek
```

### 4. Flash

1. CrowPanel 7'yi USB-C ile bilgisayara bağla
2. Arduino IDE → Tools → Port → COM? seç
3. Upload düğmesine bas
4. Serial Monitor (115200 baud) ile durumu takip et

## MQTT Topic Formatı

### Sensör Verisi (broker → CrowPanel)

```
Topic: sera/s1/sensor
Payload: {
  "T": 24.5,
  "H": 68.0,
  "co2": 850.0,
  "isik": 3200.0,
  "toprak": 45.0
}
```

### Komut (CrowPanel → broker)

```
Topic: sera/s1/komut
Payload: {
  "komut": "SULAMA_AC",
  "kaynak": "hmi_panel"
}
```

### Aktüatör Durum (broker → CrowPanel)

```
Topic: sera/s1/durum
Payload: {
  "sulama": false,
  "isitici": false,
  "sogutma": false,
  "fan": true,
  "isik": false
}
```

## Test Komutu (Broker'dan Sahte Veri Gönder)

```bash
# Sensör verisi gönder
mosquitto_pub -h 192.168.1.100 -t "sera/s1/sensor" \
  -m '{"T":24.5,"H":68.0,"co2":850,"isik":3200,"toprak":45}'

# Alarm testi (sıcaklık çok yüksek)
mosquitto_pub -h 192.168.1.100 -t "sera/s1/sensor" \
  -m '{"T":38.0,"H":30.0,"co2":2500,"isik":100,"toprak":20}'

# Aktüatör durumu güncelle
mosquitto_pub -h 192.168.1.100 -t "sera/s1/durum" \
  -m '{"sulama":false,"isitici":false,"sogutma":false,"fan":true,"isik":false}'

# Panelin gönderdiği komutları dinle
mosquitto_sub -h 192.168.1.100 -t "sera/s1/komut"
```

## Pin Haritası (CrowPanel 7.0)

Firmware'deki pin konfigürasyonu Elecrow resmi örneklerinden alınmıştır.
Kendi kartınızda pin numaraları farklıysa `LGFX` sınıfını güncelle.

| Sinyal | GPIO |
|--------|------|
| Backlight | 2 |
| VSYNC | 41 |
| HSYNC | 39 |
| PCLK | 42 |
| DE | 40 |
| Touch SDA | 19 |
| Touch SCL | 20 |
| Touch INT | 18 |
| Touch RST | 38 |

## Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| Ekran açılmıyor | `PSRAM: OPI PSRAM` seçili olduğundan emin ol |
| Dokunmatik çalışmıyor | Touch pin RST/INT değerlerini Elecrow dokümanı ile karşılaştır |
| MQTT bağlanmıyor | Broker IP'sini ve port'u Serial Monitor'dan kontrol et |
| Veri gelmiyor | `mosquitto_pub` ile test mesajı gönder |
| Ekran titriyor | `cfg.freq_write` değerini 12000000'e düşür |
