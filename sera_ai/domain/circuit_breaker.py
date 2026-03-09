"""
Circuit Breaker — Hata kaskatını engelle.

Neden gerekli?
  Arduino/ESP32 yanıt vermeyince sistem sürekli retry yapmaz,
  enerji/zaman harcamaz, log'u çöplemez.
  60 saniye sonra "yarı açık" → bir deneme → başarılıysa normale dön.

Üç durum:
  KAPALI    → Normal çalışma
  ACIK      → Eşik aşıldı, çağrılar reddedilir (60s bekle)
  YARI_ACIK → 60s geçti, bir deneme yapılıyor
"""
from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable, Optional


class CBDurum(Enum):
    KAPALI    = auto()   # Normal
    ACIK      = auto()   # Hata — geçici devre dışı
    YARI_ACIK = auto()   # Test: bir deneme izni


class CircuitBreaker:
    """
    Her sera için ayrı instance.
    Sera C'nin CB'si açılınca Sera A ve B etkilenmez.
    """

    def __init__(self, isim: str, hata_esigi: int = 5,
                 recovery_sn: int = 60):
        self.isim        = isim
        self.hata_esigi  = hata_esigi
        self.recovery_sn = recovery_sn
        self._durum      = CBDurum.KAPALI
        self._hata_sayisi = 0
        self._acilis_zaman: Optional[float] = None

    @property
    def durum(self) -> CBDurum:
        """
        ACIK durumda süre geçti mi kontrol et.
        Property olarak tanımlandı çünkü süre kontrolü zaman bağımlı.
        """
        if self._durum == CBDurum.ACIK:
            gecen = time.time() - self._acilis_zaman
            if gecen > self.recovery_sn:
                self._durum = CBDurum.YARI_ACIK
        return self._durum

    @property
    def kalan_sn(self) -> int:
        """ACIK durumdaysa kaç saniye kaldı."""
        if self._durum == CBDurum.ACIK and self._acilis_zaman:
            kalan = self.recovery_sn - int(time.time() - self._acilis_zaman)
            return max(0, kalan)
        return 0

    def cagir(self, fn: Callable, *args, **kwargs):
        """
        fn'i CB koruması altında çalıştır.
        ACIK durumda fn hiç çağrılmaz → RuntimeError.
        Başarısız → hata sayacını artır.
        Başarılı  → hata sayacını sıfırla.
        """
        if self.durum == CBDurum.ACIK:
            raise RuntimeError(
                f"[CB:{self.isim}] Devre açık — {self.kalan_sn}s kaldı"
            )
        try:
            sonuc = fn(*args, **kwargs)
            self._basari_kaydet()
            return sonuc
        except Exception as e:
            self._hata_kaydet(str(e))
            raise

    def hata_kaydet(self, hata: str = ""):
        """Dışarıdan (sensör doğrulama gibi) hata bildir."""
        self._hata_kaydet(hata)

    def sifirla(self):
        """Manuel sıfırlama — operatör müdahalesi."""
        self._durum = CBDurum.KAPALI
        self._hata_sayisi = 0
        self._acilis_zaman = None

    def _basari_kaydet(self):
        if self._durum == CBDurum.YARI_ACIK:
            # Test başarılı → normale dön
            self._durum = CBDurum.KAPALI
            self._hata_sayisi = 0
        elif self._durum == CBDurum.KAPALI:
            # Başarılar hata sayacını yavaşça düşürür
            self._hata_sayisi = max(0, self._hata_sayisi - 1)

    def _hata_kaydet(self, hata: str):
        self._hata_sayisi += 1
        if self._hata_sayisi >= self.hata_esigi:
            self._durum = CBDurum.ACIK
            self._acilis_zaman = time.time()

    def __repr__(self) -> str:
        return (
            f"CB({self.isim}:{self.durum.name}:"
            f"{self._hata_sayisi}/{self.hata_esigi})"
        )
