# ESP32-CAM Sera Kamera Nodu

## Donanım
- AI Thinker ESP32-CAM (OV2640, 4MB PSRAM)
- Güç: 5V/2A (USB veya harici)

## Flash Adımları

### 1. Arduino IDE Ayarları
- Board: **AI Thinker ESP32-CAM** (veya ESP32 Wrover Module)
- Upload Speed: 115200
- CPU Frequency: 240 MHz
- Flash Frequency: 80 MHz
- Flash Mode: QIO
- Partition Scheme: **Huge APP (3MB No OTA)**

### 2. WiFi Bilgilerini Gir
`sera_cam.ino` dosyasında değiştir:
```cpp
#define VARSAYILAN_WIFI_SSID   "WIFI_ADINIZI_YAZIN"
#define VARSAYILAN_WIFI_SIFRE  "WIFI_SIFRENIZI_YAZIN"
#define SERA_ID                "s1"   // hangi seraya ait
```

### 3. Flash (IO0 → GND bağla, sonra güç ver)
1. GPIO0 pinine GND bağla (flash modu)
2. Güç ver / USB tak
3. Arduino IDE → Upload
4. Flash bittikten sonra GPIO0'dan GND'yi çıkar
5. Cihazı yeniden başlat (Reset)

### 4. IP Adresini Öğren
Serial Monitor (115200 baud) açınca IP görünür:
```
[HAZIR] Raspberry Pi config.yaml'a ekle:
  url: http://192.168.1.201/capture
```

### 5. config.yaml'a Ekle
```yaml
goruntu:
  aktif: true
  kamera: esp32_cam
  seralar:
    - id: s1
      url: http://192.168.1.201/capture
      zaman_asimi_sn: 5
    - id: s2
      url: http://192.168.1.202/capture
      zaman_asimi_sn: 5
```

## Endpoint'ler
| URL | Açıklama |
|-----|----------|
| `GET /capture` | JPEG görüntü (Raspberry Pi tarafından çekiliyor) |
| `GET /status` | JSON sağlık bilgisi |
| `GET /` | Tarayıcıdan canlı önizleme |

## Test
```bash
# Görüntü al
curl http://192.168.1.201/capture -o test.jpg

# Durum
curl http://192.168.1.201/status
```
