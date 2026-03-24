"""
Mock Kamera & Hastalık Tespiti — Test ve Demo

MockKamera:
  Gerçek kamera donanımı olmadan JPEG benzeri bytes üretir.
  Yapılandırılabilir hata oranı (IOError simülasyonu).

MockHastalıkTespit:
  Yapılandırılabilir hastalık dağılımı ile deterministik tespit.
  epsilon=0.0 → hep aynı sonuç (birim test için).
  epsilon>0.0 → sınıflar arasında rasgele seçim.

Kullanım (birim test):
    kamera  = MockKamera()
    tespit  = MockHastalıkTespit(hastalik="saglikli", guven=0.92)
    servis  = GorüntuServisi(kamera, tespit)
    sonuc   = servis.kontrol_et("s1")
    assert sonuc.hastalik == "saglikli"
"""
from __future__ import annotations

import random
import struct
import time
from typing import Optional

from .base import (
    GorüntuServisi,
    HastalikTespitBase,
    HASTALIK_SINIFLARI,
    KameraBase,
    TespitSonucu,
)


# ── Minimal JPEG ─────────────────────────────────────────────────

def _minimal_jpeg(genislik: int = 8, yukseklik: int = 8) -> bytes:
    """
    Geçerli ama boş bir JPEG döndürür (SOI + APP0 + EOI).
    Gerçek piksel içermez — sadece format başlık testi için.
    """
    soi  = b"\xff\xd8"          # Start of Image
    eoi  = b"\xff\xd9"          # End of Image
    # Minimal APP0 marker (JFIF)
    app0 = (
        b"\xff\xe0"             # APP0 marker
        + struct.pack(">H", 16) # uzunluk
        + b"JFIF\x00"           # identifier
        + b"\x01\x01"           # version
        + b"\x00"               # density unit
        + struct.pack(">HH", genislik, yukseklik)
        + b"\x00\x00"           # thumbnail
    )
    return soi + app0 + eoi


# ── Mock Kamera ──────────────────────────────────────────────────

class MockKamera(KameraBase):
    """
    Sahte kamera. Her goruntu_al() çağrısında minimal JPEG döndürür.

    Args:
        hata_orani  — 0.0–1.0, IOError fırlatma olasılığı
        gecikme_sn  — Her okumada bekleme süresi (test yavaşlatma)
        cagri_sayac — Kaç kez çağrıldığını sayar
    """

    def __init__(
        self,
        hata_orani: float = 0.0,
        gecikme_sn: float = 0.0,
    ):
        self.hata_orani  = hata_orani
        self.gecikme_sn  = gecikme_sn
        self.cagri_sayac = 0

    def goruntu_al(self) -> bytes:
        self.cagri_sayac += 1
        if self.gecikme_sn:
            time.sleep(self.gecikme_sn)
        if random.random() < self.hata_orani:
            raise IOError("MockKamera: simüle edilmiş bağlantı hatası")
        return _minimal_jpeg()

    def __repr__(self) -> str:
        return f"MockKamera(hata_orani={self.hata_orani})"


# ── Mock Hastalık Tespiti ────────────────────────────────────────

class MockHastalıkTespit(HastalikTespitBase):
    """
    Yapılandırılabilir sonuçlar döndüren sahte tespit modeli.

    Mod 1 — Deterministik (epsilon=0.0):
        Her çağrıda aynı hastalik + guven döner. Birim test için.

    Mod 2 — Senaryo listesi (senaryolar=[...]):
        Her çağrıda sıradaki elemanı döner (round-robin).
        Sıralı senaryo testi için.

    Mod 3 — Rastgele (epsilon>0.0):
        epsilon olasılıkla rasgele sınıf seçer, 1-epsilon ile sabit sınıf.

    Args:
        hastalik    — Varsayılan tespit sınıfı
        guven       — Varsayılan güven skoru (0.0–1.0)
        epsilon     — Rastgele keşif oranı
        senaryolar  — [(hastalik, guven), ...] — sıralı senaryo listesi
    """

    def __init__(
        self,
        hastalik:   str   = "saglikli",
        guven:      float = 0.92,
        epsilon:    float = 0.0,
        senaryolar: Optional[list[tuple[str, float]]] = None,
    ):
        assert hastalik in HASTALIK_SINIFLARI, (
            f"Geçersiz hastalık: {hastalik!r}. "
            f"Geçerli: {HASTALIK_SINIFLARI}"
        )
        self.hastalik    = hastalik
        self.guven       = guven
        self.epsilon     = epsilon
        self.senaryolar  = senaryolar or []
        self._indeks     = 0
        self.cagri_sayac = 0

    def tespit_et(self, goruntu: bytes, sera_id: str) -> TespitSonucu:
        self.cagri_sayac += 1

        # Senaryo modu: sırayla tüket
        if self.senaryolar:
            hastalik, guven = self.senaryolar[self._indeks % len(self.senaryolar)]
            self._indeks   += 1
            return TespitSonucu(sera_id=sera_id, hastalik=hastalik, guven=guven)

        # Rastgele keşif
        if self.epsilon > 0.0 and random.random() < self.epsilon:
            hastalik = random.choice(HASTALIK_SINIFLARI)
            guven    = round(random.uniform(0.45, 0.75), 3)
            return TespitSonucu(sera_id=sera_id, hastalik=hastalik, guven=guven)

        return TespitSonucu(sera_id=sera_id, hastalik=self.hastalik, guven=self.guven)

    def __repr__(self) -> str:
        return f"MockHastalıkTespit(hastalik={self.hastalik!r}, guven={self.guven})"


# ── Hazır Servis Fabrikası ───────────────────────────────────────

def mock_goruntu_servisi_olustur(
    hastalik: str = "saglikli",
    guven:    float = 0.92,
    **kwargs,
) -> GorüntuServisi:
    """Test için tek satırda hazır servis oluştur."""
    return GorüntuServisi(
        kamera  = MockKamera(),
        tespit  = MockHastalıkTespit(hastalik=hastalik, guven=guven),
        **kwargs,
    )
