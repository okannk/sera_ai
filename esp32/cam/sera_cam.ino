/**
 * sera_cam.ino — ESP32-CAM (AI Thinker) Sera Kamera Nodu
 *
 * Görev:
 *   WiFi'ye bağlan → HTTP sunucu aç → GET /capture → JPEG döndür
 *
 * Donanım: AI Thinker ESP32-CAM (OV2640 kamera, 4MB PSRAM)
 *
 * Arduino IDE Ayarları:
 *   Board   : AI Thinker ESP32-CAM  (ya da ESP32 Wrover Module)
 *   CPU     : 240 MHz
 *   Flash   : 4MB (32Mb)
 *   Partition: Huge APP (3MB No OTA)
 *
 * Gerekli kütüphane: "ESP32" board paketi (Espressif)
 *   https://dl.espressif.com/dl/package_esp32_index.json
 *
 * Raspberry Pi config.yaml'a ekle:
 *   goruntu:
 *     kamera: esp32_cam
 *     seralar:
 *       - id: s1
 *         url: http://<KAMERA_IP>/capture
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>

// ── WiFi Kimlik Bilgileri ────────────────────────────────────────────────────
// İlk flash öncesinde buraya yaz; sonraki yüklemelerde Preferences'tan okunur.
#define VARSAYILAN_WIFI_SSID   "WIFI_ADINIZI_YAZIN"
#define VARSAYILAN_WIFI_SIFRE  "WIFI_SIFRENIZI_YAZIN"

// Sera ID — hangi seraya ait olduğunu belirtir (heartbeat'e eklenir)
#define SERA_ID  "s1"

// ── AI Thinker ESP32-CAM Pin Haritası ───────────────────────────────────────
#define CAM_PIN_PWDN    32
#define CAM_PIN_RESET   -1
#define CAM_PIN_XCLK     0
#define CAM_PIN_SIOD    26
#define CAM_PIN_SIOC    27
#define CAM_PIN_D7      35
#define CAM_PIN_D6      34
#define CAM_PIN_D5      39
#define CAM_PIN_D4      38
#define CAM_PIN_D3      37
#define CAM_PIN_D2      36
#define CAM_PIN_D1       5
#define CAM_PIN_D0       4
#define CAM_PIN_VSYNC   25
#define CAM_PIN_HREF    23
#define CAM_PIN_PCLK    22

// ── Dahili LED (flash) ───────────────────────────────────────────────────────
#define LED_PIN  4   // GPIO4 — AI Thinker'da dahili flash LED

// ── Global Nesneler ──────────────────────────────────────────────────────────
WebServer sunucu(80);
Preferences prefs;

String wifi_ssid;
String wifi_sifre;

// ── Kamera başlatma ──────────────────────────────────────────────────────────

bool kamera_baslat() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = CAM_PIN_D0;
  config.pin_d1       = CAM_PIN_D1;
  config.pin_d2       = CAM_PIN_D2;
  config.pin_d3       = CAM_PIN_D3;
  config.pin_d4       = CAM_PIN_D4;
  config.pin_d5       = CAM_PIN_D5;
  config.pin_d6       = CAM_PIN_D6;
  config.pin_d7       = CAM_PIN_D7;
  config.pin_xclk     = CAM_PIN_XCLK;
  config.pin_pclk     = CAM_PIN_PCLK;
  config.pin_vsync    = CAM_PIN_VSYNC;
  config.pin_href     = CAM_PIN_HREF;
  config.pin_sccb_sda = CAM_PIN_SIOD;
  config.pin_sccb_scl = CAM_PIN_SIOC;
  config.pin_pwdn     = CAM_PIN_PWDN;
  config.pin_reset    = CAM_PIN_RESET;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // PSRAM varsa yüksek çözünürlük
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_VGA;   // 640×480 — yeterli kalite, düşük bellek
    config.jpeg_quality = 12;              // 0 (en iyi) – 63 (en kötü)
    config.fb_count     = 2;
    config.grab_mode    = CAMERA_GRAB_LATEST;
  } else {
    config.frame_size   = FRAMESIZE_QVGA;  // 320×240
    config.jpeg_quality = 15;
    config.fb_count     = 1;
    config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[KAMERA] Başlatma hatası 0x%x\n", err);
    return false;
  }

  // OV2640 sensor ince ayar
  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 0);   // -2 ile 2 arası
  s->set_contrast(s, 0);
  s->set_saturation(s, 0);
  s->set_sharpness(s, 0);
  s->set_whitebal(s, 1);     // Otomatik beyaz denge aç
  s->set_awb_gain(s, 1);
  s->set_exposure_ctrl(s, 1); // Otomatik pozlama aç
  s->set_aec2(s, 1);
  s->set_gain_ctrl(s, 1);
  s->set_agc_gain(s, 0);
  s->set_aec_value(s, 300);
  s->set_bpc(s, 0);
  s->set_wpc(s, 1);
  s->set_raw_gma(s, 1);
  s->set_lenc(s, 1);
  s->set_hmirror(s, 0);
  s->set_vflip(s, 0);
  s->set_dcw(s, 1);
  s->set_colorbar(s, 0);

  Serial.println("[KAMERA] Başlatıldı");
  return true;
}

// ── HTTP Handler'lar ─────────────────────────────────────────────────────────

// GET /capture → JPEG görüntü
void handle_capture() {
  // LED yak
  digitalWrite(LED_PIN, HIGH);

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    digitalWrite(LED_PIN, LOW);
    sunucu.send(500, "text/plain", "Kamera hatasi: frame alinamadi");
    return;
  }

  sunucu.sendHeader("Content-Type",        "image/jpeg");
  sunucu.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  sunucu.sendHeader("Access-Control-Allow-Origin", "*");
  sunucu.sendHeader("Cache-Control",       "no-cache, no-store");
  sunucu.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);

  esp_camera_fb_return(fb);
  digitalWrite(LED_PIN, LOW);

  Serial.printf("[KAMERA] Goruntu gonderildi — %u byte\n", fb->len);
}

// GET /status → JSON sağlık bilgisi
void handle_status() {
  String json = "{";
  json += "\"sera_id\":\"" + String(SERA_ID) + "\",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"sinyal_dbm\":" + String(WiFi.RSSI()) + ",";
  json += "\"psram\":" + String(psramFound() ? "true" : "false") + ",";
  json += "\"uptime_sn\":" + String(millis() / 1000);
  json += "}";
  sunucu.sendHeader("Access-Control-Allow-Origin", "*");
  sunucu.send(200, "application/json", json);
}

// GET / → Basit durum sayfası
void handle_root() {
  String html = "<html><head><meta charset='UTF-8'>";
  html += "<meta http-equiv='refresh' content='5'></head><body>";
  html += "<h2>&#127807; Sera Kamera — " + String(SERA_ID) + "</h2>";
  html += "<p>IP: " + WiFi.localIP().toString() + "</p>";
  html += "<p><a href='/capture'>Goruntu Al</a> | <a href='/status'>Durum</a></p>";
  html += "<img src='/capture' style='max-width:100%;margin-top:10px'>";
  html += "</body></html>";
  sunucu.send(200, "text/html", html);
}

// ── WiFi Bağlantı ─────────────────────────────────────────────────────────────

bool wifi_baglan(const String& ssid, const String& sifre) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), sifre.c_str());
  Serial.printf("[WIFI] Baglaniyor: %s", ssid.c_str());

  unsigned long bitis = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < bitis) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WIFI] Baglandi — IP: %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  Serial.println("[WIFI] Baglanti basarisiz");
  return false;
}

// ── Setup ────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== ESP32-CAM Sera Kamera Nodu ===");

  // Flash LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // WiFi kimlik bilgilerini Preferences'tan oku; yoksa varsayılanı kullan
  prefs.begin("sera_cam", false);
  wifi_ssid  = prefs.getString("ssid",  VARSAYILAN_WIFI_SSID);
  wifi_sifre = prefs.getString("sifre", VARSAYILAN_WIFI_SIFRE);
  prefs.end();

  // Kamera başlat
  if (!kamera_baslat()) {
    Serial.println("[HATA] Kamera baslatilmadi — 5s sonra yeniden baslatiliyor");
    delay(5000);
    ESP.restart();
  }

  // WiFi bağlan
  if (!wifi_baglan(wifi_ssid, wifi_sifre)) {
    Serial.println("[HATA] WiFi basarisiz — 10s sonra yeniden baslatiliyor");
    delay(10000);
    ESP.restart();
  }

  // HTTP sunucu endpoint'leri
  sunucu.on("/",        HTTP_GET, handle_root);
  sunucu.on("/capture", HTTP_GET, handle_capture);
  sunucu.on("/status",  HTTP_GET, handle_status);
  sunucu.begin();

  Serial.printf("[HTTP] Sunucu ayakta — http://%s/capture\n",
                WiFi.localIP().toString().c_str());
  Serial.println("[HAZIR] Raspberry Pi config.yaml'a ekle:");
  Serial.printf("  url: http://%s/capture\n", WiFi.localIP().toString().c_str());

  // LED'i 3 kez yak — hazır sinyali
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH); delay(200);
    digitalWrite(LED_PIN, LOW);  delay(200);
  }
}

// ── Loop ─────────────────────────────────────────────────────────────────────

void loop() {
  sunucu.handleClient();

  // WiFi bağlantısı kopunca yeniden bağlan
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] Baglanti kesildi — yeniden baglaniliyor");
    wifi_baglan(wifi_ssid, wifi_sifre);
  }

  delay(10);
}
