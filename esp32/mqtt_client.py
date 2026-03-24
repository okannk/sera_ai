# MicroPython
# mqtt_client.py — MQTT istemcisi (umqtt.simple)
# Broker kimlik doğrulaması: cihaz_id = kullanıcı adı, token = şifre

import utime
import ujson

try:
    from umqtt.simple import MQTTClient
    _UMQTT_MEVCUT = True
except ImportError:
    _UMQTT_MEVCUT = False
    print("[MQTT] UYARI: umqtt.simple bulunamadı — mock mod aktif")

# ---------------------------------------------------------------------------
# Yeniden bağlanma geri çekilme süreleri (saniye)
# ---------------------------------------------------------------------------
_BACKOFF_SURELERI = (5, 15, 30, 60)


class MQTTIstemci:
    """
    ESP32-S3 MQTT istemcisi.

    Konu yapısı:
      - Yayın  : sera/{tesis_kodu}/{sera_id}/sensor
      - Abone  : sera/{tesis_kodu}/{sera_id}/komut
      - Kalp   : cihaz/{cihaz_id}/kalp_atisi
    """

    def __init__(
        self,
        cihaz_id: str,
        token: str,
        tesis_kodu: str,
        sera_id: str,
        broker_ip: str,
        broker_port: int = 1883,
    ):
        self._cihaz_id    = cihaz_id
        self._token       = token
        self._tesis_kodu  = tesis_kodu
        self._sera_id     = sera_id
        self._broker_ip   = broker_ip
        self._broker_port = broker_port

        # Konu adları
        self._sensor_konu     = f"sera/{tesis_kodu}/{sera_id}/sensor"
        self._komut_konu      = f"sera/{tesis_kodu}/{sera_id}/komut"
        self._kalp_atisi_konu = f"cihaz/{cihaz_id}/kalp_atisi"

        # Dahili durum
        self._istemci:      object = None
        self._bagli:        bool   = False
        self._komut_cb              = None  # komut gelince çağrılacak fonksiyon
        self._son_mesaj_zaman: int = 0      # ticks_ms — watchdog için

    # -----------------------------------------------------------------------
    # Bağlantı
    # -----------------------------------------------------------------------

    def baglan(self) -> bool:
        """
        Broker'a bağlan.
        Başarısız olursa üstel geri çekilme ile tekrar dener.
        True = bağlandı, False = tüm denemeler tükendi.
        """
        if not _UMQTT_MEVCUT:
            print("[MQTT] Mock mod — bağlantı simüle ediliyor")
            self._bagli = True
            return True

        for deneme, bekleme in enumerate(_BACKOFF_SURELERI, start=1):
            try:
                print(f"[MQTT] Bağlanıyor {self._broker_ip}:{self._broker_port} "
                      f"(deneme {deneme}/{len(_BACKOFF_SURELERI)})...")

                istemci = MQTTClient(
                    client_id = self._cihaz_id,
                    server    = self._broker_ip,
                    port      = self._broker_port,
                    user      = self._cihaz_id,   # kullanıcı adı = cihaz kimliği
                    password  = self._token,       # şifre = JWT token
                    keepalive = 60,
                )
                istemci.set_callback(self._mesaj_alindi)
                istemci.connect()
                self._istemci = istemci
                self._bagli   = True
                self._son_mesaj_zaman = utime.ticks_ms()
                print(f"[MQTT] Bağlantı başarılı — broker={self._broker_ip}")
                return True

            except Exception as e:
                print(f"[MQTT] Bağlantı hatası: {e} — {bekleme}s bekleniyor")
                self._bagli = False
                utime.sleep(bekleme)

        print("[MQTT] Tüm bağlantı denemeleri başarısız")
        return False

    def yeniden_baglan(self) -> bool:
        """Mevcut bağlantıyı kapat ve yeniden bağlan."""
        print("[MQTT] Yeniden bağlanılıyor...")
        self._bagli = False
        try:
            if self._istemci:
                self._istemci.disconnect()
        except Exception:
            pass
        self._istemci = None
        return self.baglan()

    # -----------------------------------------------------------------------
    # Mesaj alma — callback
    # -----------------------------------------------------------------------

    def _mesaj_alindi(self, konu: bytes, mesaj: bytes) -> None:
        """umqtt.simple geri çağrısı — gelen mesajları işle."""
        self._son_mesaj_zaman = utime.ticks_ms()
        konu_str = konu.decode("utf-8") if isinstance(konu, bytes) else konu
        print(f"[MQTT] Mesaj alındı — konu={konu_str}, uzunluk={len(mesaj)}B")

        if self._komut_cb is not None:
            try:
                self._komut_cb(konu, mesaj)
            except Exception as e:
                print(f"[MQTT] Komut callback hatası: {e}")

    # -----------------------------------------------------------------------
    # Yayın (Publish)
    # -----------------------------------------------------------------------

    def sensor_yayinla(self, veri: dict) -> bool:
        """
        Sensör ölçümlerini yayınla.
        veri: {"T": float, "H": float, "co2": int, ...}
        Döndürür: başarı durumu
        """
        if not _UMQTT_MEVCUT:
            print(f"[MQTT] Mock yayın → {self._sensor_konu}: {veri}")
            return True

        if not self._bagli or self._istemci is None:
            print("[MQTT] Yayın başarısız — bağlı değil")
            return False

        try:
            # Zaman damgası ekle
            veri["zaman"] = utime.time()
            veri["cihaz_id"] = self._cihaz_id
            mesaj = ujson.dumps(veri)
            self._istemci.publish(self._sensor_konu, mesaj, retain=False, qos=0)
            return True
        except Exception as e:
            print(f"[MQTT] Yayın hatası: {e}")
            self._bagli = False
            return False

    def kalp_atisi_gonder(self) -> bool:
        """Cihazın çevrimiçi olduğunu bildiren kalp atışı yayınla (QoS 0)."""
        if not _UMQTT_MEVCUT:
            print(f"[MQTT] Mock kalp atışı → {self._kalp_atisi_konu}")
            return True

        if not self._bagli or self._istemci is None:
            return False

        try:
            durum = ujson.dumps({
                "cihaz_id": self._cihaz_id,
                "sera_id":  self._sera_id,
                "zaman":    utime.time(),
                "durum":    "canlı",
            })
            self._istemci.publish(self._kalp_atisi_konu, durum, retain=False, qos=0)
            return True
        except Exception as e:
            print(f"[MQTT] Kalp atışı hatası: {e}")
            self._bagli = False
            return False

    # -----------------------------------------------------------------------
    # Abone (Subscribe)
    # -----------------------------------------------------------------------

    def komut_dinle(self, callback) -> None:
        """
        Komut konusuna abone ol.
        callback(konu: bytes, mesaj: bytes) şeklinde çağrılır.
        """
        self._komut_cb = callback

        if not _UMQTT_MEVCUT:
            print(f"[MQTT] Mock abone → {self._komut_konu}")
            return

        if not self._bagli or self._istemci is None:
            print("[MQTT] Abone başarısız — bağlı değil")
            return

        try:
            self._istemci.subscribe(self._komut_konu)
            print(f"[MQTT] Abone olundu → {self._komut_konu}")
        except Exception as e:
            print(f"[MQTT] Abone hatası: {e}")
            self._bagli = False

    # -----------------------------------------------------------------------
    # Ana döngüde çağrılacak — bekleyen mesajları işle
    # -----------------------------------------------------------------------

    def mesajlari_isle(self) -> None:
        """
        Bekleyen MQTT mesajlarını kontrol et.
        Ana döngüde her iterasyonda çağrılmalıdır (non-blocking check_msg).
        """
        if not _UMQTT_MEVCUT or not self._bagli or self._istemci is None:
            return

        try:
            self._istemci.check_msg()  # Non-blocking
        except Exception as e:
            print(f"[MQTT] Mesaj kontrol hatası: {e}")
            self._bagli = False

    # -----------------------------------------------------------------------
    # Özellikler
    # -----------------------------------------------------------------------

    @property
    def bagli(self) -> bool:
        return self._bagli

    @property
    def son_mesaj_zaman(self) -> int:
        """Son MQTT mesajının alındığı zaman (ticks_ms). Watchdog için."""
        return self._son_mesaj_zaman

    @son_mesaj_zaman.setter
    def son_mesaj_zaman(self, deger: int) -> None:
        self._son_mesaj_zaman = deger
