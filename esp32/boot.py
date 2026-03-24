# MicroPython
# boot.py — ESP32-S3 Sera Otomasyon Düğümü
# main.py'den ÖNCE çalışır. Panik kurtarma, güvenli mod, frekans ayarı.

import gc
import sys
import utime

# ---------------------------------------------------------------------------
# CPU frekansını 240 MHz'e sabitle (WiFi + UART için gerekli)
# ---------------------------------------------------------------------------
try:
    from machine import freq
    freq(240_000_000)
except Exception:
    pass  # Bazı MicroPython buildlarında freq() yok

# ---------------------------------------------------------------------------
# Çöp toplayıcı eşiğini düşür — 80 KB'da topla (bellek kısıtlı platform)
# ---------------------------------------------------------------------------
gc.threshold(80 * 1024)

# ---------------------------------------------------------------------------
# Güvenli Mod Algılama
# BOOT butonuna (GPIO0) basılı tutarak açılırsa provisioning moduna zorla.
# Bu sayede sensör yazılımı bozulsa bile cihazı kurtarabilirsin.
# ---------------------------------------------------------------------------
_GUVENLI_MOD_PIN = 0   # ESP32-S3 devkit BOOT butonu GPIO0
_GUVENLI_MOD_MS  = 3_000  # 3 saniye basılı tut → güvenli mod

def _guvenli_mod_kontrol() -> bool:
    """BOOT butonuna basılıysa True döndür."""
    try:
        from machine import Pin
        btn = Pin(_GUVENLI_MOD_PIN, Pin.IN, Pin.PULL_UP)
        if btn.value() == 0:  # Aktif-düşük
            bitis = utime.ticks_ms() + _GUVENLI_MOD_MS
            print(f"[BOOT] BOOT butonu algılandı — {_GUVENLI_MOD_MS // 1000}s basılı tut → Güvenli Mod")
            while utime.ticks_diff(bitis, utime.ticks_ms()) > 0:
                if btn.value() != 0:
                    return False  # Erken bırakıldı
                utime.sleep_ms(100)
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# Panik Sayacı — Art arda 3 kez boot hatasında fabrika sıfırlaması
# Dosya tabanlı kalıcı sayaç: /boot_hata_sayac.txt
# ---------------------------------------------------------------------------
_HATA_DOSYA  = "/boot_hata_sayac.txt"
_HATA_ESIGI  = 3

def _hata_sayac_oku() -> int:
    try:
        with open(_HATA_DOSYA, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def _hata_sayac_yaz(n: int) -> None:
    try:
        with open(_HATA_DOSYA, "w") as f:
            f.write(str(n))
    except Exception:
        pass

def _hata_sayac_sifirla() -> None:
    try:
        import os
        os.remove(_HATA_DOSYA)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Başlangıç akışı
# ---------------------------------------------------------------------------

print("=" * 40)
print("  ESP32-S3 SERA — boot.py")
print(f"  MicroPython {sys.version}")
print("=" * 40)

# Güvenli mod kontrolü
if _guvenli_mod_kontrol():
    print("[BOOT] GÜVENLİ MOD — config.json siliniyor, provisioning başlayacak")
    try:
        import os
        os.remove("/config.json")
    except Exception:
        pass
    _hata_sayac_sifirla()
    print("[BOOT] Güvenli mod hazır. main.py provisioning modunda başlayacak.")
else:
    # Panik sayacını kontrol et
    hata_sayisi = _hata_sayac_oku()

    if hata_sayisi >= _HATA_ESIGI:
        print(f"[BOOT] UYARI: {hata_sayisi} art arda hata — fabrika sıfırlaması yapılıyor")
        try:
            import os
            os.remove("/config.json")
        except Exception:
            pass
        _hata_sayac_sifirla()
        print("[BOOT] Sıfırlandı. main.py provisioning modunda başlayacak.")
    else:
        # Sayacı artır — main.py başarıyla tamamlanırsa sıfırlayacak
        _hata_sayac_yaz(hata_sayisi + 1)
        print(f"[BOOT] Hata sayacı: {hata_sayisi + 1}/{_HATA_ESIGI}")

# main.py başarılı açılışta sayacı sıfırlaması için flag
# main.py'nin sonunda ya da normal döngüde _hata_sayac_sifirla() çağrılmalı
# Şimdilik boot başarıyla tamamlandıysa burada sıfırla
_hata_sayac_sifirla()

print("[BOOT] main.py başlatılıyor...")
gc.collect()
