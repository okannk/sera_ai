# MicroPython
# watchdog.py — Donanım ve yazılım watchdog yönetimi
# MQTT sessizliği ve genel sistem donması algılar, otomatik kurtarma yapar.

import utime

try:
    from machine import WDT, reset as machine_reset
    _MACHINE_MEVCUT = True
except ImportError:
    _MACHINE_MEVCUT = False
    print("[WATCHDOG] UYARI: machine modülü yok — mock mod aktif")
    def machine_reset():
        print("[WATCHDOG] machine.reset() çağrılır (mock)")

# ---------------------------------------------------------------------------
# Eşik değerleri
# ---------------------------------------------------------------------------
_MQTT_SESSIZLIK_MS  = 90  * 1000   # 90 saniye — MQTT mesajı yoksa yeniden bağlan
_SISTEM_DONMA_MS    = 300 * 1000   # 5 dakika — toplam arıza süresi → sert sıfırlama
_HW_WATCHDOG_MS     = 8_388       # ~8.3 saniye — ESP32-S3 WDT maksimumu (WDT(timeout=8388))


class Watchdog:
    """
    İki katmanlı watchdog:
    1. Donanım WDT (machine.WDT) — besle() ile beslenmezse sert sıfırlama
    2. Yazılım WDT — MQTT sessizliği veya uzun arıza → yeniden bağlan / sıfırla
    """

    def __init__(self):
        # Donanım watchdog başlat
        if _MACHINE_MEVCUT:
            try:
                self._hw_wdt = WDT(timeout=_HW_WATCHDOG_MS)
                print(f"[WATCHDOG] Donanım WDT başlatıldı — {_HW_WATCHDOG_MS}ms")
            except Exception as e:
                print(f"[WATCHDOG] Donanım WDT başlatılamadı: {e}")
                self._hw_wdt = None
        else:
            self._hw_wdt = None

        now = utime.ticks_ms()
        self._son_mqtt_mesaj:   int  = now   # Son MQTT mesajı zamanı
        self._baglanti_baslangic: int = now  # Mevcut bağlantı oturumunun başlangıcı
        self._ilk_baslangic:    int  = now   # Cihaz açılış zamanı
        self._yeniden_baglandi: bool = False # Bu oturumda yeniden bağlanma yapıldı mı

    # -----------------------------------------------------------------------
    # Donanım WDT besleme
    # -----------------------------------------------------------------------

    def besle(self) -> None:
        """
        Donanım watchdog'unu besle (timeout'u sıfırla).
        Ana döngünün her iterasyonunda çağrılmalıdır.
        """
        if self._hw_wdt is not None:
            try:
                self._hw_wdt.feed()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # MQTT mesaj damgası güncelleme
    # -----------------------------------------------------------------------

    def mqtt_mesaj_alindi(self) -> None:
        """MQTT üzerinden mesaj alındığında çağrılır."""
        self._son_mqtt_mesaj    = utime.ticks_ms()
        self._yeniden_baglandi  = False
        self._baglanti_baslangic = utime.ticks_ms()

    # -----------------------------------------------------------------------
    # Yazılım watchdog kontrolü
    # -----------------------------------------------------------------------

    def kontrol_et(self, mqtt_istemci) -> None:
        """
        Periyodik olarak çağrılır (örn. her 5 saniyede bir).

        - 90s MQTT sessizliği → yeniden bağlan
        - 5 dakika toplam arıza → machine.reset()
        - Her çağrıda donanım WDT beslenir
        """
        self.besle()  # Her durumda donanım WDT besle

        simdi = utime.ticks_ms()

        # --- MQTT bağlantı kontrolü ---
        mqtt_sessizlik = utime.ticks_diff(simdi, self._son_mqtt_mesaj)
        sistem_suresi  = utime.ticks_diff(simdi, self._ilk_baslangic)

        if not mqtt_istemci.bagli:
            # Bağlantı kesildi — toplam arıza süresini kontrol et
            ariza_suresi = utime.ticks_diff(simdi, self._baglanti_baslangic)

            print(f"[WATCHDOG] MQTT bağlantısı yok — arıza süresi: {ariza_suresi // 1000}s")

            if ariza_suresi >= _SISTEM_DONMA_MS:
                print("[WATCHDOG] KRİTİK: 5 dakikadır bağlantı yok — sert sıfırlama")
                utime.sleep(1)
                machine_reset()
                return

            # Yeniden bağlan
            print("[WATCHDOG] Yeniden bağlanılıyor...")
            if mqtt_istemci.yeniden_baglan():
                print("[WATCHDOG] Yeniden bağlantı başarılı")
                self.mqtt_mesaj_alindi()
            return

        # Bağlı ama sessiz — 90 saniye mesaj gelmediyse
        if mqtt_sessizlik >= _MQTT_SESSIZLIK_MS:
            print(f"[WATCHDOG] {mqtt_sessizlik // 1000}s MQTT sessizliği — yeniden bağlanılıyor")
            self._baglanti_baslangic = simdi  # Arıza sayacını sıfırla
            if mqtt_istemci.yeniden_baglan():
                print("[WATCHDOG] Sessizlik sonrası yeniden bağlantı başarılı")
                self.mqtt_mesaj_alindi()
            return

        # Her şey yolunda — periyodik log (her ~60 saniyede bir)
        if mqtt_sessizlik < 5000:  # Yeni mesaj var
            print(f"[WATCHDOG] OK — MQTT aktif, çalışma süresi: {sistem_suresi // 1000}s")

    # -----------------------------------------------------------------------
    # Durum bilgisi
    # -----------------------------------------------------------------------

    def durum(self) -> dict:
        """Watchdog durum bilgisini döndür (debug/log için)."""
        simdi = utime.ticks_ms()
        return {
            "mqtt_sessizlik_s": utime.ticks_diff(simdi, self._son_mqtt_mesaj) // 1000,
            "calisma_suresi_s": utime.ticks_diff(simdi, self._ilk_baslangic) // 1000,
            "hw_wdt_aktif":     self._hw_wdt is not None,
        }
