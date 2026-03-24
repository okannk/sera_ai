# MicroPython
# main.py — ESP32-S3 Sera Otomasyon Düğümü — Ana Giriş Noktası
# Provisioning → Normal mod akışı

import utime
import ujson

import config
import provisioning
import mqtt_client
import sensors
import actuators
import watchdog

# ---------------------------------------------------------------------------
# Zamanlama sabitleri
# ---------------------------------------------------------------------------
_SENSOR_ARALIK_MS   = 5_000   # 5 saniyede bir sensör oku + yayınla
_KALP_ARALIK_MS     = 30_000  # 30 saniyede bir kalp atışı
_WATCHDOG_ARALIK_MS = 5_000   # 5 saniyede bir watchdog kontrol


# ---------------------------------------------------------------------------
# Ana kontrol döngüsü
# ---------------------------------------------------------------------------

def loop(
    mqtt:           mqtt_client.MQTTIstemci,
    sensor_okuyucu: sensors.SensorOkuyucu,
    aktuator:       actuators.AktuatorKontrolcu,
    wd:             watchdog.Watchdog,
) -> None:
    """
    Sürekli çalışan kontrol döngüsü.
    Her 5s: sensör oku → yayınla
    Her 30s: kalp atışı
    Her 5s: watchdog kontrol
    """
    son_sensor_zaman   = utime.ticks_ms()
    son_kalp_zaman     = utime.ticks_ms()
    son_watchdog_zaman = utime.ticks_ms()
    dongu_sayaci       = 0

    print("[ANA] Kontrol döngüsü başladı")
    print(f"[ANA] Cihaz ID : {config.CIHAZ_ID}")
    print(f"[ANA] Tesis    : {config.TESIS_KODU} / Sera: {config.SERA_ID}")

    while True:
        simdi = utime.ticks_ms()

        # ------------------------------------------------------------------
        # Watchdog besle (her iterasyonda)
        # ------------------------------------------------------------------
        wd.besle()

        # ------------------------------------------------------------------
        # MQTT mesajlarını işle (non-blocking)
        # ------------------------------------------------------------------
        try:
            mqtt.mesajlari_isle()
        except Exception as e:
            print(f"[ANA] MQTT mesaj işleme hatası: {e}")

        # ------------------------------------------------------------------
        # Sensör oku ve yayınla (her 5 saniyede)
        # ------------------------------------------------------------------
        if utime.ticks_diff(simdi, son_sensor_zaman) >= _SENSOR_ARALIK_MS:
            son_sensor_zaman = simdi

            try:
                veri = sensor_okuyucu.oku()

                if sensor_okuyucu.gecerli_mi(veri):
                    # Aktüatör durumunu sensör paketiyle birlikte gönder
                    veri["aktuatorler"] = aktuator.durum()
                    tamam = mqtt.sensor_yayinla(veri)
                    if tamam:
                        wd.mqtt_mesaj_alindi()  # Başarılı yayın = canlı bağlantı
                        dongu_sayaci += 1
                        if dongu_sayaci % 12 == 0:  # Her ~1 dakikada özet
                            print(
                                f"[ANA] Döngü #{dongu_sayaci} — "
                                f"T={veri['T']}°C H={veri['H']}% "
                                f"CO₂={veri['co2']}ppm Işık={veri['isik']}lux"
                            )
                    else:
                        print("[ANA] Sensör yayını başarısız")
                else:
                    print(f"[ANA] Geçersiz sensör verisi atlandı: {veri}")

            except Exception as e:
                print(f"[ANA] Sensör okuma hatası: {e}")

        # ------------------------------------------------------------------
        # Kalp atışı (her 30 saniyede)
        # ------------------------------------------------------------------
        if utime.ticks_diff(simdi, son_kalp_zaman) >= _KALP_ARALIK_MS:
            son_kalp_zaman = simdi
            try:
                mqtt.kalp_atisi_gonder()
            except Exception as e:
                print(f"[ANA] Kalp atışı hatası: {e}")

        # ------------------------------------------------------------------
        # Watchdog kontrolü (her 5 saniyede)
        # ------------------------------------------------------------------
        if utime.ticks_diff(simdi, son_watchdog_zaman) >= _WATCHDOG_ARALIK_MS:
            son_watchdog_zaman = simdi
            try:
                wd.kontrol_et(mqtt)
            except Exception as e:
                print(f"[ANA] Watchdog kontrol hatası: {e}")

        # Ana döngüyü CPU'ya boğmamak için kısa bekleme
        utime.sleep_ms(200)


# ---------------------------------------------------------------------------
# Komut callback
# ---------------------------------------------------------------------------

def _komut_callback_olustur(aktuator: actuators.AktuatorKontrolcu, wd: watchdog.Watchdog):
    """
    MQTT komut callback'i döndür.
    Closure ile aktuator ve watchdog erişimi sağlar.
    """
    def komut_callback(konu: bytes, mesaj: bytes) -> None:
        try:
            komut_str = mesaj.decode("utf-8").strip()
            print(f"[ANA] Komut alındı: {komut_str}")
            aktuator.komut_isle(komut_str)
            wd.mqtt_mesaj_alindi()  # Komut mesajı da canlılık kanıtı
        except Exception as e:
            print(f"[ANA] Komut işleme hatası: {e}")

    return komut_callback


# ---------------------------------------------------------------------------
# Başlangıç — Normal mod
# ---------------------------------------------------------------------------

def normal_mod() -> None:
    """WiFi + MQTT + sensör + aktüatör başlatma."""
    print("[ANA] Normal mod başlatılıyor...")
    config.durum_yazdir()

    # WiFi bağlantısı (zaten provisioning'de bağlandıysa mevcut bağlantıyı kullan)
    import network
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    if not sta.isconnected():
        print(f"[ANA] WiFi'ye bağlanılıyor: {config.WIFI_SSID}")
        sta.connect(config.WIFI_SSID, config.WIFI_SIFRE)
        bitis = utime.time() + 30
        while utime.time() < bitis:
            if sta.isconnected():
                break
            utime.sleep(1)

        if not sta.isconnected():
            print("[ANA] WiFi bağlantısı başarısız — 10s sonra yeniden başlatılıyor")
            utime.sleep(10)
            import machine
            machine.reset()
            return

    print(f"[ANA] WiFi bağlandı — IP: {sta.ifconfig()[0]}")

    # MQTT istemcisi
    mqtt = mqtt_client.MQTTIstemci(
        cihaz_id   = config.CIHAZ_ID,
        token      = config.TOKEN,
        tesis_kodu = config.TESIS_KODU,
        sera_id    = config.SERA_ID,
        broker_ip  = config.MQTT_HOST,
        broker_port= config.MQTT_PORT,
    )

    if not mqtt.baglan():
        print("[ANA] MQTT bağlantısı başarısız — devam ediliyor (watchdog kurtaracak)")

    # Sensör okuyucu ve aktüatör
    sensor_okuyucu = sensors.SensorOkuyucu()
    aktuator       = actuators.AktuatorKontrolcu()

    # Watchdog
    wd = watchdog.Watchdog()

    # Komut callback'i kaydet
    komut_cb = _komut_callback_olustur(aktuator, wd)
    mqtt.komut_dinle(komut_cb)

    # Ana döngü — bu fonksiyon dönmez
    loop(mqtt, sensor_okuyucu, aktuator, wd)


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Cihaz başlatma mantığı:
    1. Token var mı?  → Normal mod
    2. Token yok      → Provisioning modu (AP aç, web form, Pi kaydı)
    """
    print("=" * 40)
    print("  ESP32-S3 Sera Otomasyon Düğümü")
    print("  MicroPython v1.20+")
    print("=" * 40)

    # Kısa bekleme — dosya sistemi ve ağ arabirimlerinin hazır olması için
    utime.sleep_ms(500)

    token = config.oku_token()

    if not token:
        # İlk açılış veya fabrika sıfırlaması sonrası
        print("[ANA] Token bulunamadı — Provisioning modu başlatılıyor")
        print(f"[ANA] Lütfen 'SERA-SETUP-xxxx' WiFi ağına bağlanın")
        print(f"[ANA] Ardından http://192.168.4.1 adresini açın")

        try:
            provisioning.baslat(
                pi_ip  = config.PI_IP,
                pi_port= config.PI_PORT,
            )
        except Exception as e:
            print(f"[ANA] Provisioning hatası: {e}")
            utime.sleep(5)
            import machine
            machine.reset()

        # Provisioning başarıyla tamamlandıysa machine.reset() çağrılır.
        # Bu satıra yalnızca hata durumunda gelinir.
        return

    # Token mevcut — normal çalışma modu
    print(f"[ANA] Token bulundu — Normal mod başlatılıyor")
    try:
        normal_mod()
    except Exception as e:
        print(f"[ANA] Kritik hata: {e}")
        print("[ANA] 5 saniye sonra yeniden başlatılıyor...")
        utime.sleep(5)
        import machine
        machine.reset()


# ---------------------------------------------------------------------------
# MicroPython'da main.py doğrudan çalıştırılır
# ---------------------------------------------------------------------------
main()
