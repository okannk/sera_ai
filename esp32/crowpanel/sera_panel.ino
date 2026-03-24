/**
 * sera_panel.ino — Elecrow CrowPanel 7.0 Sera HMI
 *
 * TEST AMAÇLI — Production sistemde bu yaklaşım kullanılmayacak.
 *
 * Görev:
 *   WiFi → MQTT broker bağlan
 *   sera/{id}/sensor topicini dinle → anlık sensör verisi göster
 *   Dokunmatik butonlarla aktüatör komutları gönder (sera/{id}/komut)
 *
 * Donanım:
 *   Elecrow CrowPanel 7.0 (ESP32-S3, 7" IPS 800×480, GT911 kapasitif dokunmatik)
 *
 * Gerekli kütüphaneler (Arduino IDE → Library Manager):
 *   - LovyanGFX  (mevlut_gfx tarafından, v1.1.x)
 *   - PubSubClient (Nick O'Leary, v2.8)
 *   - ArduinoJson (Benoit Blanchon, v7.x)
 *
 * Arduino IDE Ayarları:
 *   Board     : ESP32S3 Dev Module
 *   PSRAM     : OPI PSRAM (veya Disabled)
 *   Flash     : 16MB (128Mb)
 *   CPU Freq  : 240 MHz
 *   Partition : Huge APP (3MB No OTA)
 *
 * KURULUM:
 *   1. Aşağıdaki #define'ları kendi ortamınıza göre düzenleyin
 *   2. Arduino IDE → Upload
 *   3. Serial Monitor (115200 baud) ile bağlantı durumunu takip edin
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <LovyanGFX.hpp>

// ─────────────────────────────────────────────────────────────────────────────
// YAPILANDIRMA — Burası değiştirilmeli
// ─────────────────────────────────────────────────────────────────────────────

#define WIFI_SSID       "WIFI_ADINIZI_YAZIN"
#define WIFI_SIFRE      "WIFI_SIFRENIZI_YAZIN"

#define MQTT_SUNUCU     "192.168.1.100"   // Raspberry Pi IP
#define MQTT_PORT       1883
#define MQTT_KULLANICI  ""                // Boş bırakırsanız auth yok
#define MQTT_SIFRE_STR  ""

#define SERA_ID         "s1"              // Hangi serayı izleyecek
#define SERA_ISIM       "Domates Serası"  // Ekranda gösterilecek isim

// Eşik değerleri — aşılınca alarm banner kırmızı yanar
#define ALARM_SICAKLIK_MAX  35.0f
#define ALARM_SICAKLIK_MIN  10.0f
#define ALARM_NEM_MIN       40.0f
#define ALARM_CO2_MAX       2000.0f
#define ALARM_ISIK_MIN      200.0f

// ─────────────────────────────────────────────────────────────────────────────
// CrowPanel 7.0 — LovyanGFX Konfigürasyonu
// Elecrow resmi örneklerinden alınan pin haritası:
//   https://github.com/Elecrow-RD/CrowPanel-ESP32-Display
// ─────────────────────────────────────────────────────────────────────────────

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_RGB         _panel_instance;
  lgfx::Bus_RGB           _bus_instance;
  lgfx::Light_PWM         _light_instance;
  lgfx::Touch_GT911       _touch_instance;

public:
  LGFX() {
    // ── Ekran Otobüs Ayarı (RGB paralel) ──────────────────────────────────
    {
      auto cfg = _bus_instance.config();
      cfg.panel = &_panel_instance;

      cfg.pin_d0  = GPIO_NUM_8;   // B0
      cfg.pin_d1  = GPIO_NUM_3;   // B1
      cfg.pin_d2  = GPIO_NUM_46;  // B2
      cfg.pin_d3  = GPIO_NUM_9;   // B3
      cfg.pin_d4  = GPIO_NUM_1;   // B4
      cfg.pin_d5  = GPIO_NUM_5;   // G0
      cfg.pin_d6  = GPIO_NUM_6;   // G1
      cfg.pin_d7  = GPIO_NUM_7;   // G2
      cfg.pin_d8  = GPIO_NUM_15;  // G3
      cfg.pin_d9  = GPIO_NUM_16;  // G4
      cfg.pin_d10 = GPIO_NUM_4;   // G5
      cfg.pin_d11 = GPIO_NUM_45;  // R0
      cfg.pin_d12 = GPIO_NUM_48;  // R1
      cfg.pin_d13 = GPIO_NUM_47;  // R2
      cfg.pin_d14 = GPIO_NUM_21;  // R3
      cfg.pin_d15 = GPIO_NUM_14;  // R4

      cfg.pin_henable = GPIO_NUM_40;  // DE
      cfg.pin_vsync   = GPIO_NUM_41;  // VSYNC
      cfg.pin_hsync   = GPIO_NUM_39;  // HSYNC
      cfg.pin_pclk    = GPIO_NUM_42;  // PCLK (pixel clock)

      cfg.freq_write  = 14000000;     // 14 MHz — kararlı için düşük tut
      cfg.hsync_polarity    = 0;
      cfg.hsync_front_porch = 8;
      cfg.hsync_pulse_width = 4;
      cfg.hsync_back_porch  = 43;
      cfg.vsync_polarity    = 0;
      cfg.vsync_front_porch = 8;
      cfg.vsync_pulse_width = 4;
      cfg.vsync_back_porch  = 12;
      cfg.pclk_active_neg   = 1;

      _bus_instance.config(cfg);
      _panel_instance.setBus(&_bus_instance);
    }

    // ── Panel Ayarı ───────────────────────────────────────────────────────
    {
      auto cfg = _panel_instance.config();
      cfg.memory_width  = 800;
      cfg.memory_height = 480;
      cfg.panel_width   = 800;
      cfg.panel_height  = 480;
      cfg.offset_rotation = 0;
      _panel_instance.config(cfg);
    }

    // ── Arka Işık (PWM) ───────────────────────────────────────────────────
    {
      auto cfg = _light_instance.config();
      cfg.pin_bl = GPIO_NUM_2;
      cfg.invert = false;
      cfg.freq   = 44100;
      cfg.pwm_channel = 7;
      _light_instance.config(cfg);
      _panel_instance.setLight(&_light_instance);
    }

    // ── GT911 Kapasitif Dokunmatik ────────────────────────────────────────
    {
      auto cfg = _touch_instance.config();
      cfg.x_min      = 0;
      cfg.x_max      = 799;
      cfg.y_min      = 0;
      cfg.y_max      = 479;
      cfg.pin_int    = GPIO_NUM_18;
      cfg.pin_rst    = GPIO_NUM_38;
      cfg.bus_shared = false;
      cfg.offset_rotation = 0;
      cfg.i2c_port   = 0;
      cfg.i2c_addr   = 0x5D;
      cfg.pin_sda    = GPIO_NUM_19;
      cfg.pin_scl    = GPIO_NUM_20;
      cfg.freq       = 400000;
      _touch_instance.config(cfg);
      _panel_instance.setTouch(&_touch_instance);
    }

    setPanel(&_panel_instance);
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// Renkler (RGB565)
// ─────────────────────────────────────────────────────────────────────────────

static const uint32_t COL_BG      = 0x0D1117;  // Koyu arka plan
static const uint32_t COL_CARD    = 0x161B22;  // Kart arka planı
static const uint32_t COL_BORDER  = 0x30363D;  // Kart kenarı
static const uint32_t COL_ACCENT  = 0x58A6FF;  // Mavi vurgu
static const uint32_t COL_GREEN   = 0x3FB950;  // Normal / OK
static const uint32_t COL_YELLOW  = 0xD29922;  // Uyarı
static const uint32_t COL_RED     = 0xF85149;  // Alarm / Hata
static const uint32_t COL_WHITE   = 0xE6EDF3;  // Metin
static const uint32_t COL_GRAY    = 0x8B949E;  // İkincil metin
static const uint32_t COL_BTN_OFF = 0x21262D;  // Buton kapalı
static const uint32_t COL_BTN_ON  = 0x1F6FEB;  // Buton açık

// ─────────────────────────────────────────────────────────────────────────────
// Veri Yapıları
// ─────────────────────────────────────────────────────────────────────────────

struct SensorVeri {
  float    T      = NAN;  // Sıcaklık °C
  float    H      = NAN;  // Nem %
  float    co2    = NAN;  // CO₂ ppm
  float    isik   = NAN;  // Işık lux
  float    toprak = NAN;  // Toprak nemi %
  uint32_t zaman  = 0;    // millis() — son güncelleme
};

struct Aktuator {
  const char* isim;
  const char* komut_ac;
  const char* komut_kapat;
  bool        durum;      // true = açık
  uint32_t    renk_ac;
};

// Aktüatörler
Aktuator aktuatorler[] = {
  { "SULAMA",  "SULAMA_AC",  "SULAMA_KAPAT",  false, 0x1F6FEB },
  { "ISITICI", "ISITICI_AC", "ISITICI_KAPAT", false, 0xE85537 },
  { "SOGUTMA", "SOGUTMA_AC", "SOGUTMA_KAPAT", false, 0x1F6FEB },
  { "FAN",     "FAN_AC",     "FAN_KAPAT",     false, 0x3FB950 },
  { "ISIK",    "ISIK_AC",    "ISIK_KAPAT",    false, 0xD29922 },
};
static const int AKTUATOR_SAYISI = 5;

// ─────────────────────────────────────────────────────────────────────────────
// Layout Sabitleri (800×480)
// ─────────────────────────────────────────────────────────────────────────────

static const int HEADER_H    = 48;   // Üst başlık çubuğu
static const int ALARM_H     = 32;   // Alarm banner yüksekliği
static const int SENSOR_Y    = HEADER_H;
static const int SENSOR_H    = 220;
static const int BTN_Y       = SENSOR_Y + SENSOR_H + ALARM_H + 4;
static const int BTN_H       = 480 - BTN_Y - 4;
static const int KART_W      = 190;  // Sensör kartı genişliği
static const int KART_BOSLUK = 10;   // Kartlar arası boşluk

// Buton pozisyonları (5 buton yatay)
static const int BTN_W    = 148;
static const int BTN_PH   = 60;
static const int BTN_BOSLUK = 10;
// Toplam: 5*148 + 4*10 = 780 → merkez: (800-780)/2 = 10 margin

// ─────────────────────────────────────────────────────────────────────────────
// Global Nesneler
// ─────────────────────────────────────────────────────────────────────────────

static LGFX         ekran;
static LGFX_Sprite  sprite(&ekran);   // Tam ekran sprite (flicker yok)

static WiFiClient   wifiIstemci;
static PubSubClient mqttIstemci(wifiIstemci);

static SensorVeri   sensor;
static bool         mqttBagli     = false;
static bool         wifiBagli     = false;
static uint32_t     sonYenilenme  = 0;   // Ekran yenilenme zamanı

// MQTT topic tamponları
static char topicSensor[64];
static char topicKomut[64];
static char topicDurum[64];

// ─────────────────────────────────────────────────────────────────────────────
// Yardımcı: NAN kontrolü
// ─────────────────────────────────────────────────────────────────────────────

static bool gecerli(float v) { return !isnan(v) && !isinf(v); }

// ─────────────────────────────────────────────────────────────────────────────
// MQTT Callback — Gelen mesajları işle
// ─────────────────────────────────────────────────────────────────────────────

void mqttMesaj(char* topic, byte* payload, unsigned int uzunluk) {
  // Null-terminate
  char tampon[512];
  unsigned int n = uzunluk < sizeof(tampon) - 1 ? uzunluk : sizeof(tampon) - 1;
  memcpy(tampon, payload, n);
  tampon[n] = '\0';

  Serial.printf("[MQTT] %s → %s\n", topic, tampon);

  // Sensör verisi
  if (strcmp(topic, topicSensor) == 0) {
    JsonDocument doc;
    if (deserializeJson(doc, tampon) == DeserializationError::Ok) {
      if (doc["T"].is<float>())      sensor.T      = doc["T"].as<float>();
      if (doc["H"].is<float>())      sensor.H      = doc["H"].as<float>();
      if (doc["co2"].is<float>())    sensor.co2    = doc["co2"].as<float>();
      if (doc["isik"].is<float>())   sensor.isik   = doc["isik"].as<float>();
      if (doc["toprak"].is<float>()) sensor.toprak = doc["toprak"].as<float>();
      sensor.zaman = millis();
    }
    return;
  }

  // Aktüatör durum güncellemesi
  if (strcmp(topic, topicDurum) == 0) {
    JsonDocument doc;
    if (deserializeJson(doc, tampon) == DeserializationError::Ok) {
      for (int i = 0; i < AKTUATOR_SAYISI; i++) {
        // Komut isimlerini durum anahtarlarına çevir
        String key;
        if (i == 0) key = "sulama";
        else if (i == 1) key = "isitici";
        else if (i == 2) key = "sogutma";
        else if (i == 3) key = "fan";
        else if (i == 4) key = "isik";

        if (doc[key].is<bool>()) {
          aktuatorler[i].durum = doc[key].as<bool>();
        }
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// WiFi Bağlantı
// ─────────────────────────────────────────────────────────────────────────────

void wifiBaglan() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SIFRE);
  Serial.printf("[WIFI] Bağlanıyor: %s", WIFI_SSID);
  unsigned long bitis = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < bitis) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  wifiBagli = (WiFi.status() == WL_CONNECTED);
  if (wifiBagli) {
    Serial.printf("[WIFI] Bağlandı — IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[WIFI] Bağlantı başarısız");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// MQTT Bağlantı
// ─────────────────────────────────────────────────────────────────────────────

void mqttBaglan() {
  if (!wifiBagli) return;
  mqttIstemci.setServer(MQTT_SUNUCU, MQTT_PORT);
  mqttIstemci.setCallback(mqttMesaj);
  mqttIstemci.setBufferSize(1024);

  char clientId[32];
  snprintf(clientId, sizeof(clientId), "crowpanel-%06lx", (unsigned long)ESP.getEfuseMac());

  Serial.printf("[MQTT] Bağlanıyor %s:%d\n", MQTT_SUNUCU, MQTT_PORT);

  bool ok;
  if (strlen(MQTT_KULLANICI) > 0) {
    ok = mqttIstemci.connect(clientId, MQTT_KULLANICI, MQTT_SIFRE_STR);
  } else {
    ok = mqttIstemci.connect(clientId);
  }

  if (ok) {
    mqttBagli = true;
    mqttIstemci.subscribe(topicSensor);
    mqttIstemci.subscribe(topicDurum);
    Serial.printf("[MQTT] Bağlandı — topic: %s\n", topicSensor);
  } else {
    mqttBagli = false;
    Serial.printf("[MQTT] Bağlantı başarısız — rc=%d\n", mqttIstemci.state());
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Komut Gönder
// ─────────────────────────────────────────────────────────────────────────────

void komutGonder(const char* komut) {
  if (!mqttBagli) {
    Serial.println("[KOMUT] MQTT bağlı değil");
    return;
  }
  char json[128];
  snprintf(json, sizeof(json), "{\"komut\":\"%s\",\"kaynak\":\"hmi_panel\"}", komut);
  bool ok = mqttIstemci.publish(topicKomut, json);
  Serial.printf("[KOMUT] %s → %s\n", komut, ok ? "OK" : "HATA");
}

// ─────────────────────────────────────────────────────────────────────────────
// Alarm Tespiti
// ─────────────────────────────────────────────────────────────────────────────

struct AlarmDurumu {
  bool var;
  char mesaj[80];
};

AlarmDurumu alarmKontrol() {
  AlarmDurumu a = { false, "" };
  if (gecerli(sensor.T)) {
    if (sensor.T > ALARM_SICAKLIK_MAX) {
      a.var = true; snprintf(a.mesaj, sizeof(a.mesaj), "SICAKLIK YÜKSEK: %.1f°C (max %.0f°C)", sensor.T, ALARM_SICAKLIK_MAX);
      return a;
    }
    if (sensor.T < ALARM_SICAKLIK_MIN) {
      a.var = true; snprintf(a.mesaj, sizeof(a.mesaj), "SICAKLIK DÜŞÜK: %.1f°C (min %.0f°C)", sensor.T, ALARM_SICAKLIK_MIN);
      return a;
    }
  }
  if (gecerli(sensor.H) && sensor.H < ALARM_NEM_MIN) {
    a.var = true; snprintf(a.mesaj, sizeof(a.mesaj), "NEM DÜŞÜK: %.0f%% (min %.0f%%)", sensor.H, ALARM_NEM_MIN);
    return a;
  }
  if (gecerli(sensor.co2) && sensor.co2 > ALARM_CO2_MAX) {
    a.var = true; snprintf(a.mesaj, sizeof(a.mesaj), "CO2 YÜKSEK: %.0f ppm (max %.0f ppm)", sensor.co2, ALARM_CO2_MAX);
    return a;
  }
  return a;
}

// ─────────────────────────────────────────────────────────────────────────────
// Çizim Fonksiyonları (Sprite üzerine — sonra ekrana aktarılır)
// ─────────────────────────────────────────────────────────────────────────────

// Üst başlık çubuğu
void cizHeader(LGFX_Sprite& sp) {
  sp.fillRect(0, 0, 800, HEADER_H, COL_CARD);
  sp.drawFastHLine(0, HEADER_H - 1, 800, COL_BORDER);

  // Başlık
  sp.setTextColor(COL_WHITE);
  sp.setTextSize(1);
  sp.setFont(&fonts::FreeSansBold9pt7b);
  sp.setCursor(14, 14);
  sp.printf("SERA HMI — %s  (%s)", SERA_ISIM, SERA_ID);

  // Bağlantı göstergeleri (sağ)
  int rx = 680;
  sp.setFont(&fonts::FreeSans9pt7b);
  // WiFi
  sp.setTextColor(wifiBagli ? COL_GREEN : COL_RED);
  sp.setCursor(rx, 14); sp.print(wifiBagli ? "WiFi OK" : "WiFi!");
  // MQTT
  sp.setTextColor(mqttBagli ? COL_GREEN : COL_YELLOW);
  sp.setCursor(rx, 30); sp.print(mqttBagli ? "MQTT OK" : "MQTT...");
}

// Tek sensör kartı
void cizSensorKart(LGFX_Sprite& sp,
                   int x, int y, int w, int h,
                   const char* baslik, const char* birim,
                   float deger, float min_deger, float max_deger,
                   uint32_t renk) {
  // Kart arka plan + kenarlık
  sp.fillRoundRect(x, y, w, h, 8, COL_CARD);
  sp.drawRoundRect(x, y, w, h, 8, COL_BORDER);

  sp.setFont(&fonts::FreeSans9pt7b);
  sp.setTextColor(COL_GRAY);
  sp.setCursor(x + 12, y + 16);
  sp.print(baslik);

  if (!gecerli(deger)) {
    // Veri yok
    sp.setFont(&fonts::FreeSansBold9pt7b);
    sp.setTextColor(COL_GRAY);
    sp.setCursor(x + 12, y + 70);
    sp.print("---");
    return;
  }

  // Büyük değer yazısı
  sp.setFont(&fonts::FreeSansBold18pt7b);
  sp.setTextColor(renk);
  sp.setCursor(x + 12, y + 45);
  if (strcmp(birim, "°C") == 0 || strcmp(birim, "%") == 0) {
    sp.printf("%.1f", deger);
  } else {
    sp.printf("%.0f", deger);
  }
  // Birim
  sp.setFont(&fonts::FreeSans9pt7b);
  sp.setTextColor(COL_GRAY);
  sp.print(birim);

  // Progress bar
  int barY  = y + h - 34;
  int barX  = x + 12;
  int barW  = w - 24;
  int barH  = 6;
  sp.fillRoundRect(barX, barY, barW, barH, 3, COL_BORDER);

  float pct = (deger - min_deger) / (max_deger - min_deger);
  if (pct < 0) pct = 0;
  if (pct > 1) pct = 1;
  int doldu = (int)(barW * pct);
  if (doldu > 0) {
    sp.fillRoundRect(barX, barY, doldu, barH, 3, renk);
  }

  // Min/max etiketleri
  sp.setFont(&fonts::Font2);
  sp.setTextColor(COL_GRAY);
  sp.setCursor(barX, barY + 10);
  sp.printf("%.0f", min_deger);
  char maxStr[12];
  snprintf(maxStr, sizeof(maxStr), "%.0f", max_deger);
  sp.setCursor(barX + barW - strlen(maxStr) * 7, barY + 10);
  sp.print(maxStr);
}

// Sensör kartlar satırı
void cizSensorlar(LGFX_Sprite& sp) {
  int y  = SENSOR_Y + 4;
  int h  = SENSOR_H - 8;
  int x  = 10;

  // Veri tazeliği — 10 saniyeden eskiyse soluk göster
  bool taze = (millis() - sensor.zaman) < 10000 && sensor.zaman > 0;
  uint32_t alpha = taze ? 255 : 128;

  // Sıcaklık
  uint32_t tRenk = (!gecerli(sensor.T)) ? COL_GRAY
                 : (sensor.T > ALARM_SICAKLIK_MAX || sensor.T < ALARM_SICAKLIK_MIN) ? COL_RED
                 : COL_ACCENT;
  cizSensorKart(sp, x, y, KART_W, h, "Sıcaklık", "°C", sensor.T, -10, 50, tRenk);
  x += KART_W + KART_BOSLUK;

  // Nem
  uint32_t hRenk = (!gecerli(sensor.H)) ? COL_GRAY
                 : (sensor.H < ALARM_NEM_MIN) ? COL_RED
                 : COL_GREEN;
  cizSensorKart(sp, x, y, KART_W, h, "Nem", "%", sensor.H, 0, 100, hRenk);
  x += KART_W + KART_BOSLUK;

  // CO₂
  uint32_t co2Renk = (!gecerli(sensor.co2)) ? COL_GRAY
                   : (sensor.co2 > ALARM_CO2_MAX) ? COL_RED
                   : (sensor.co2 > 1500) ? COL_YELLOW
                   : COL_GREEN;
  cizSensorKart(sp, x, y, KART_W, h, "CO2", "ppm", sensor.co2, 400, 2500, co2Renk);
  x += KART_W + KART_BOSLUK;

  // Işık
  uint32_t isikRenk = (!gecerli(sensor.isik)) ? COL_GRAY
                    : (sensor.isik < ALARM_ISIK_MIN) ? COL_YELLOW
                    : COL_ACCENT;
  cizSensorKart(sp, x, y, KART_W, h, "Işık", "lux", sensor.isik, 0, 10000, isikRenk);
}

// Alarm banner
void cizAlarmBanner(LGFX_Sprite& sp, const AlarmDurumu& alarm) {
  int y = SENSOR_Y + SENSOR_H;
  if (alarm.var) {
    sp.fillRect(0, y, 800, ALARM_H, COL_RED);
    sp.setFont(&fonts::FreeSansBold9pt7b);
    sp.setTextColor(COL_WHITE);
    sp.setCursor(14, y + 9);
    sp.printf("⚠ ALARM: %s", alarm.mesaj);
  } else {
    sp.fillRect(0, y, 800, ALARM_H, 0x1B2A1B);  // Koyu yeşil — normal
    sp.setFont(&fonts::FreeSans9pt7b);
    sp.setTextColor(COL_GREEN);
    sp.setCursor(14, y + 9);
    sp.print("✓ Tüm değerler normal sınırlarda");
    // Son güncelleme zamanı (sağ)
    if (sensor.zaman > 0) {
      sp.setTextColor(COL_GRAY);
      unsigned long gecen = (millis() - sensor.zaman) / 1000;
      char zaman[32];
      if (gecen < 60) snprintf(zaman, sizeof(zaman), "%lus önce", gecen);
      else snprintf(zaman, sizeof(zaman), "%lum önce", gecen / 60);
      sp.setCursor(650, y + 9);
      sp.print(zaman);
    }
  }
}

// Aktüatör butonları
// Butonların koordinatlarını döndürür — dokunma tespitinde kullanılır
struct BtnRect { int x, y, w, h; };
BtnRect btnRektler[AKTUATOR_SAYISI];

void cizButonlar(LGFX_Sprite& sp) {
  int y = BTN_Y + 4;
  int h = BTN_H - 8;
  int startX = (800 - (AKTUATOR_SAYISI * BTN_W + (AKTUATOR_SAYISI - 1) * BTN_BOSLUK)) / 2;

  // Başlık
  sp.setFont(&fonts::FreeSans9pt7b);
  sp.setTextColor(COL_GRAY);
  sp.setCursor(startX, y - 2);
  sp.print("AKTÜATÖRLER");

  y += 14;
  h -= 14;

  for (int i = 0; i < AKTUATOR_SAYISI; i++) {
    int x = startX + i * (BTN_W + BTN_BOSLUK);
    btnRektler[i] = { x, y, BTN_W, h };

    bool ac = aktuatorler[i].durum;
    uint32_t bgRenk = ac ? aktuatorler[i].renk_ac : COL_BTN_OFF;
    uint32_t txtRenk = ac ? COL_WHITE : COL_GRAY;
    uint32_t kenarlik = ac ? aktuatorler[i].renk_ac : COL_BORDER;

    sp.fillRoundRect(x, y, BTN_W, h, 8, bgRenk);
    sp.drawRoundRect(x, y, BTN_W, h, 8, kenarlik);

    // Durum noktası
    sp.fillCircle(x + BTN_W - 14, y + 14, 6, ac ? COL_GREEN : COL_GRAY);

    // İsim
    sp.setFont(&fonts::FreeSansBold9pt7b);
    sp.setTextColor(txtRenk);
    sp.setCursor(x + 12, y + h / 2 - 6);
    sp.print(aktuatorler[i].isim);

    // Durum yazısı
    sp.setFont(&fonts::FreeSans9pt7b);
    sp.setTextColor(ac ? COL_GREEN : COL_GRAY);
    sp.setCursor(x + 12, y + h / 2 + 12);
    sp.print(ac ? "AÇIK" : "KAPALI");
  }

  // Alt ayraç çizgisi
  sp.drawFastHLine(0, BTN_Y, 800, COL_BORDER);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tam Ekran Yenileme
// ─────────────────────────────────────────────────────────────────────────────

void ekranYenile() {
  sprite.fillScreen(COL_BG);

  AlarmDurumu alarm = alarmKontrol();

  cizHeader(sprite);
  cizSensorlar(sprite);
  cizAlarmBanner(sprite, alarm);
  cizButonlar(sprite);

  sprite.pushSprite(0, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dokunma İşleme
// ─────────────────────────────────────────────────────────────────────────────

static uint32_t sonDokunma = 0;
static const uint32_t DOKUNMA_DEBOUNCE = 300;  // ms

void dokunmaKontrol() {
  lgfx::v1::touch_point_t tp;
  if (!ekran.getTouch(&tp)) return;

  uint32_t simdi = millis();
  if (simdi - sonDokunma < DOKUNMA_DEBOUNCE) return;
  sonDokunma = simdi;

  int px = tp.x;
  int py = tp.y;

  Serial.printf("[DOKUNMA] x=%d y=%d\n", px, py);

  // Buton kontrolü
  for (int i = 0; i < AKTUATOR_SAYISI; i++) {
    BtnRect& r = btnRektler[i];
    if (px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h) {
      bool yeniDurum = !aktuatorler[i].durum;
      const char* komut = yeniDurum ? aktuatorler[i].komut_ac : aktuatorler[i].komut_kapat;
      Serial.printf("[BTN] %s → %s\n", aktuatorler[i].isim, komut);
      komutGonder(komut);
      aktuatorler[i].durum = yeniDurum;  // Optimistik güncelleme
      ekranYenile();
      return;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Setup
// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== CrowPanel 7 Sera HMI ===");

  // MQTT topic'lerini oluştur
  snprintf(topicSensor, sizeof(topicSensor), "sera/%s/sensor", SERA_ID);
  snprintf(topicKomut,  sizeof(topicKomut),  "sera/%s/komut",  SERA_ID);
  snprintf(topicDurum,  sizeof(topicDurum),  "sera/%s/durum",  SERA_ID);

  // Ekranı başlat
  ekran.begin();
  ekran.setRotation(0);
  ekran.setBrightness(200);
  ekran.fillScreen(COL_BG);

  // Sprite oluştur (çift tampon — flicker yok)
  sprite.setColorDepth(16);
  if (!sprite.createSprite(800, 480)) {
    Serial.println("[HATA] Sprite oluşturulamadı — PSRAM yetersiz?");
    // PSRAM yoksa sprite olmadan devam et
  }

  // Başlangıç ekranı
  ekran.setFont(&fonts::FreeSansBold18pt7b);
  ekran.setTextColor(COL_ACCENT);
  ekran.setCursor(260, 180);
  ekran.print("SERA HMI");
  ekran.setFont(&fonts::FreeSans9pt7b);
  ekran.setTextColor(COL_GRAY);
  ekran.setCursor(300, 220);
  ekran.printf("Sera: %s  (%s)", SERA_ISIM, SERA_ID);
  ekran.setCursor(310, 250);
  ekran.print("WiFi bağlanıyor...");

  // WiFi bağlan
  wifiBaglan();

  ekran.setCursor(310, 270);
  if (wifiBagli) {
    ekran.setTextColor(COL_GREEN);
    ekran.printf("WiFi OK — %s", WiFi.localIP().toString().c_str());
  } else {
    ekran.setTextColor(COL_RED);
    ekran.print("WiFi başarısız!");
  }
  delay(1500);

  // MQTT bağlan
  mqttBaglan();

  // Ana ekranı çiz
  ekranYenile();

  Serial.println("[HAZIR] HMI panel çalışıyor.");
  Serial.printf("  MQTT Sensor topic: %s\n", topicSensor);
  Serial.printf("  MQTT Komut  topic: %s\n", topicKomut);
}

// ─────────────────────────────────────────────────────────────────────────────
// Loop
// ─────────────────────────────────────────────────────────────────────────────

void loop() {
  // WiFi kontrolü
  if (WiFi.status() != WL_CONNECTED) {
    if (wifiBagli) {
      wifiBagli = false;
      mqttBagli = false;
      Serial.println("[WIFI] Bağlantı kesildi");
    }
    static uint32_t sonWifiDeneme = 0;
    if (millis() - sonWifiDeneme > 10000) {
      sonWifiDeneme = millis();
      wifiBaglan();
    }
  }

  // MQTT kontrolü
  if (wifiBagli && !mqttIstemci.connected()) {
    if (mqttBagli) {
      mqttBagli = false;
      Serial.println("[MQTT] Bağlantı kesildi");
    }
    static uint32_t sonMqttDeneme = 0;
    if (millis() - sonMqttDeneme > 5000) {
      sonMqttDeneme = millis();
      mqttBaglan();
    }
  }

  // MQTT mesaj işle
  if (mqttIstemci.connected()) {
    mqttIstemci.loop();
  }

  // Dokunma kontrolü
  dokunmaKontrol();

  // Ekranı periyodik yenile (her 1 saniyede bir — animasyon + durum güncellemesi)
  if (millis() - sonYenilenme > 1000) {
    sonYenilenme = millis();
    ekranYenile();
  }
}
