# ESP32-S3 Sensör Node Firmware (MicroPython)

## Dosyalar
| Dosya | Görev |
|-------|-------|
| `boot.py` | İlk çalışan dosya — panik kurtarma, güvenli mod |
| `main.py` | Ana döngü — WiFi, MQTT, sensör, watchdog |
| `sensors.py` | SHT31 / MH-Z19C / BH1750 / kapasitif nem |
| `actuators.py` | SSR röle kontrolü (sulama, ısıtıcı, soğutma, fan, ışık) |
| `mqtt_client.py` | MQTT istemcisi — JWT token ile broker auth |
| `provisioning.py` | Zero-touch provisioning — AP modu + web form |
| `config.py` | `/config.json` tabanlı kalıcı depolama |
| `watchdog.py` | Donanım WDT + yazılım watchdog |

## MicroPython Flash Adımları

### 1. MicroPython İndir
ESP32-S3 için: https://micropython.org/download/ESP32_GENERIC_S3/

### 2. Flash (esptool ile)
```bash
pip install esptool

# Flash belleği temizle
esptool.py --chip esp32s3 --port COM3 erase_flash

# MicroPython yükle
esptool.py --chip esp32s3 --port COM3 --baud 460800 \
  write_flash -z 0 ESP32_GENERIC_S3-vX.Y.Z.bin
```

### 3. Dosyaları Yükle (mpremote veya Thonny)
```bash
pip install mpremote

# Tüm dosyaları kopyala
mpremote connect COM3 cp boot.py :boot.py
mpremote connect COM3 cp main.py :main.py
mpremote connect COM3 cp sensors.py :sensors.py
mpremote connect COM3 cp actuators.py :actuators.py
mpremote connect COM3 cp mqtt_client.py :mqtt_client.py
mpremote connect COM3 cp provisioning.py :provisioning.py
mpremote connect COM3 cp config.py :config.py
mpremote connect COM3 cp watchdog.py :watchdog.py

# Yeniden başlat
mpremote connect COM3 reset
```

### 4. İlk Açılış — Provisioning
1. Cihaz `SERA-SETUP-XXXX` WiFi ağı açar
2. Bu ağa bağlan
3. Tarayıcıda `http://192.168.4.1` aç
4. WiFi bilgilerini ve Raspberry Pi IP'sini gir
5. **Sera seç** (Raspberry Pi API'sinden otomatik çekilir)
6. Cihaz yeniden başlar → Raspberry Pi'dan token alır → normal moda girer

### 5. Güvenli Mod (Sorun Çıkarsa)
BOOT butonunu **3 saniye basılı tut** → `/config.json` silinir → provisioning moduna girer.

## Pin Haritası

### Sensörler
| Sensör | Bağlantı | Pin |
|--------|----------|-----|
| SHT31 (T+H) | I2C SDA | GPIO8 |
| SHT31 (T+H) | I2C SCL | GPIO9 |
| MH-Z19C (CO₂) | UART TX | GPIO17 |
| MH-Z19C (CO₂) | UART RX | GPIO16 |
| BH1750 (Işık) | I2C SDA | GPIO8 (paylaşımlı) |
| BH1750 (Işık) | I2C SCL | GPIO9 (paylaşımlı) |
| Kapasitif Nem | ADC | GPIO34 |

### Aktüatörler (SSR Röle)
| Aktüatör | GPIO |
|----------|------|
| SULAMA | 25 |
| ISITICI | 26 |
| SOGUTMA | 27 |
| FAN | 14 |
| ISIK | 12 |
