# MicroPython
# actuators.py — SSR röle üzerinden aktüatör kontrolü
# GPIO pinleri LOW = kapalı, HIGH = açık (aktif-yüksek SSR)

try:
    from machine import Pin
    _MACHINE_MEVCUT = True
except ImportError:
    # Geliştirme/test ortamında machine modülü yoksa mock
    _MACHINE_MEVCUT = False
    print("[AKTÜATÖR] UYARI: machine modülü yok — mock mod aktif")

# ---------------------------------------------------------------------------
# Pin haritası — Donanım şemasıyla eşleşmelidir
# ---------------------------------------------------------------------------
_PIN_HARITA = {
    "SULAMA":  25,   # Sulama vanası SSR
    "ISITICI": 26,   # Isıtıcı SSR
    "SOGUTMA": 27,   # Soğutma/klima SSR
    "FAN":     14,   # Havalandırma fanı SSR
    "ISIK":    12,   # Yapay aydınlatma SSR
}

# ---------------------------------------------------------------------------
# Mock Pin — machine modülü olmadan test için
# ---------------------------------------------------------------------------

class _MockPin:
    """machine.Pin davranışını simüle eden sınıf."""
    OUT = 1

    def __init__(self, numara: int, mod: int = 1):
        self._numara = numara
        self._deger  = 0

    def value(self, v: int = None) -> int:
        if v is not None:
            self._deger = int(v)
        return self._deger

    def on(self)  -> None: self._deger = 1
    def off(self) -> None: self._deger = 0

    def __repr__(self) -> str:
        return f"MockPin({self._numara}, deger={self._deger})"

# ---------------------------------------------------------------------------
# Aktüatör Kontrolcüsü
# ---------------------------------------------------------------------------

class AktuatorKontrolcu:
    """
    Tüm SSR rölelerini merkezi olarak yönetir.

    Komut formatları:
      - "SULAMA_AC"     → sulama vanasını aç
      - "SULAMA_KAPAT"  → sulama vanasını kapat
      - "ISITICI_AC"    → ısıtıcıyı aç
      - "ISITICI_KAPAT" → ısıtıcıyı kapat
      - "SOGUTMA_AC"    / "SOGUTMA_KAPAT"
      - "FAN_AC"        / "FAN_KAPAT"
      - "ISIK_AC"       / "ISIK_KAPAT"
      - "TUMU_KAPAT"    → acil durdurma — tüm aktüatörleri kapat
    """

    def __init__(self):
        PinSinifi = Pin if _MACHINE_MEVCUT else _MockPin
        PinModu   = Pin.OUT if _MACHINE_MEVCUT else _MockPin.OUT

        self._pinler: dict = {}
        for ad, numara in _PIN_HARITA.items():
            pin = PinSinifi(numara, PinModu)
            pin.value(0)  # Başlangıçta tüm aktüatörler kapalı
            self._pinler[ad] = pin
            print(f"[AKTÜATÖR] {ad} → GPIO{numara} — KAPALI")

        print("[AKTÜATÖR] Tüm pinler başlatıldı")

    # -----------------------------------------------------------------------
    # Komut işleme
    # -----------------------------------------------------------------------

    def komut_isle(self, komut_str: str) -> bool:
        """
        Metin komutunu ayrıştır ve ilgili GPIO'yu değiştir.

        Döndürür: komut tanındıysa True, tanınmadıysa False.
        """
        komut_str = komut_str.strip().upper()
        print(f"[AKTÜATÖR] Komut alındı: {komut_str}")

        # Özel komut: acil durdurma
        if komut_str in ("TUMU_KAPAT", "ACİL_DURDUR", "ACIL_DURDUR"):
            for ad, pin in self._pinler.items():
                pin.value(0)
                print(f"[AKTÜATÖR] {ad} → KAPALI (acil)")
            return True

        # Standart format: {CİHAZ}_{EYLEM}
        if "_" not in komut_str:
            print(f"[AKTÜATÖR] Bilinmeyen komut formatı: {komut_str}")
            return False

        # Son parçayı ayır — "FAN" + "AC" veya "SULAMA" + "KAPAT"
        parcalar = komut_str.rsplit("_", 1)
        if len(parcalar) != 2:
            print(f"[AKTÜATÖR] Komut ayrıştırılamadı: {komut_str}")
            return False

        cihaz, eylem = parcalar

        if cihaz not in self._pinler:
            print(f"[AKTÜATÖR] Bilinmeyen cihaz: {cihaz}")
            return False

        if eylem == "AC":
            self._pinler[cihaz].value(1)
            print(f"[AKTÜATÖR] {cihaz} → AÇIK")
            return True
        elif eylem == "KAPAT":
            self._pinler[cihaz].value(0)
            print(f"[AKTÜATÖR] {cihaz} → KAPALI")
            return True
        elif eylem == "TOGGLE":
            mevcut = self._pinler[cihaz].value()
            self._pinler[cihaz].value(0 if mevcut else 1)
            yeni = "AÇIK" if self._pinler[cihaz].value() else "KAPALI"
            print(f"[AKTÜATÖR] {cihaz} → {yeni} (toggle)")
            return True
        else:
            print(f"[AKTÜATÖR] Bilinmeyen eylem: {eylem}")
            return False

    # -----------------------------------------------------------------------
    # Durum sorgulama
    # -----------------------------------------------------------------------

    def durum(self) -> dict:
        """
        Tüm aktüatörlerin mevcut durumunu döndür.
        {"SULAMA": True, "ISITICI": False, ...}
        """
        return {ad: bool(pin.value()) for ad, pin in self._pinler.items()}

    def acik_mi(self, cihaz: str) -> bool:
        """Belirli bir aktüatörün açık olup olmadığını döndür."""
        cihaz = cihaz.upper()
        if cihaz in self._pinler:
            return bool(self._pinler[cihaz].value())
        return False

    def tumu_kapat(self) -> None:
        """Güvenli kapatma — tüm aktüatörleri kapat."""
        for ad, pin in self._pinler.items():
            pin.value(0)
        print("[AKTÜATÖR] Tüm aktüatörler kapatıldı")
