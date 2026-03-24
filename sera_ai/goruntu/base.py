"""
Görüntü İşleme — Kamera & Hastalık Tespiti Soyutlama Katmanı

Mimarideki yeri:
  sensors/ → anlık sayısal sensör ölçümleri (T, H, CO₂, ışık)
  goruntu/ → görsel analiz (kamera → hastalık tespiti)

KameraBase:
  Görüntü yakalama soyutlaması.
    ESP32Kamera  → ESP32-CAM HTTP snapshot (JPEG bytes)
    MockKamera   → test için sabit/rastgele JPEG bytes

HastalikTespitBase:
  Model inference soyutlaması.
    HastalikModeli   → RandomForest, renk histogramı tabanlı
    MockHastalıkTespit → test için yapılandırılabilir sonuçlar

TespitSonucu:
  Tek tespiti temsil eden domain nesnesi (stdlib only).

GorüntuServisi:
  Kamera + Tespit + EventBus entegrasyon köprüsü.
  RaspberryPiMerkez tarafından per-sera kullanılır.

Hastalık sınıfları:
  saglikli          → Normal, işlem gerekmez
  yaprak_sararmasi  → Besin eksikliği / aşırı sulama
  kurtcuk           → Böcek / haşere hasarı
  mantar            → Fungal enfeksiyon
  yaniklık          → Ateş yanıklığı / kuraklık stresi
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Sabitler ────────────────────────────────────────────────────

HASTALIK_SINIFLARI: list[str] = [
    "saglikli",
    "yaprak_sararmasi",
    "kurtcuk",
    "mantar",
    "yaniklık",
]

HASTALIK_ONERILERI: dict[str, str] = {
    "saglikli":         "İzlemeye devam edin, işlem gerekmez.",
    "yaprak_sararmasi": "Besin çözeltisi konsantrasyonunu ve sulama sıklığını kontrol edin.",
    "kurtcuk":          "Etkilenen bitkileri izole edin; biyolojik veya kimyasal ilaçlama planlayın.",
    "mantar":           "Havalandırmayı artırın, nem düşürün, antifungal uygulayın.",
    "yaniklık":         "ACİL: Etkilenen bitkileri derhal ayırın, sulama durdurun, danışmanlık alın.",
}

VARSAYILAN_GUVEN_ESIGI = 0.60


# ── Domain Nesnesi ───────────────────────────────────────────────

@dataclass
class TespitSonucu:
    """
    Tek görüntü analizinin sonucu.

    Alanlar:
      sera_id       → Hangi seraya ait
      hastalik      → Tespit edilen sınıf (HASTALIK_SINIFLARI listesinden)
      guven         → Model güven skoru 0.0–1.0
      zaman         → Tespit zamanı
      oneri         → Operatöre önerilen aksiyon
      goruntu_yolu  → Kaydedilen görüntü dosyası (opsiyonel)
      anomali       → True → güven eşiğinin altında (düşük güvenilirlik)
    """
    sera_id:      str
    hastalik:     str
    guven:        float
    zaman:        datetime = field(default_factory=datetime.now)
    oneri:        str      = ""
    goruntu_yolu: Optional[str] = None
    anomali:      bool     = False

    def __post_init__(self):
        if not self.oneri:
            self.oneri = HASTALIK_ONERILERI.get(self.hastalik, "Belirsiz sonuç — manuel kontrol önerilir.")
        self.anomali = self.guven < VARSAYILAN_GUVEN_ESIGI

    def to_dict(self) -> dict:
        return {
            "sera_id":      self.sera_id,
            "hastalik":     self.hastalik,
            "guven":        round(self.guven, 3),
            "zaman":        self.zaman.isoformat(),
            "oneri":        self.oneri,
            "goruntu_yolu": self.goruntu_yolu,
            "anomali":      self.anomali,
        }

    @property
    def kritik_mi(self) -> bool:
        """Acil müdahale gerektiren bir hastalık mı?"""
        return self.hastalik == "yaniklık" and self.guven >= VARSAYILAN_GUVEN_ESIGI


# ── ABC'ler ──────────────────────────────────────────────────────

class KameraBase(ABC):
    """
    Görüntü yakalama soyutlaması.

    goruntu_al() → JPEG/PNG formatında ham bytes döner.
    baglan() / kapat() → lifecycle, opsiyonel override.
    """

    @abstractmethod
    def goruntu_al(self) -> bytes:
        """
        Kameradan anlık görüntü al.

        Returns:
            bytes — JPEG veya PNG formatında ham görüntü verisi

        Raises:
            IOError: Kamera yanıt vermedi, bağlantı hatası
        """
        ...

    def baglan(self) -> bool:
        """Kamera donanımını başlat. True → hazır."""
        return True

    def kapat(self) -> None:
        """Kaynakları serbest bırak."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class HastalikTespitBase(ABC):
    """
    Görüntüden hastalık tespiti soyutlaması.

    tespit_et(goruntu_bytes, sera_id) → TespitSonucu döner.
    modeli_yukle() → Eğitilmiş model dosyasını yükle (opsiyonel).
    """

    @abstractmethod
    def tespit_et(self, goruntu: bytes, sera_id: str) -> TespitSonucu:
        """
        Görüntüyü analiz ederek hastalık tespiti yap.

        Args:
            goruntu  — KameraBase.goruntu_al() çıktısı (JPEG bytes)
            sera_id  — Hangi sera (TespitSonucu.sera_id için)

        Returns:
            TespitSonucu — hastalık sınıfı, güven skoru, öneri
        """
        ...

    def modeli_yukle(self, yol: str) -> None:
        """
        Eğitilmiş model dosyasını yükle.
        Varsayılan: no-op (mock / kural tabanlı implementasyonlar için).
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ── Entegrasyon Servisi ──────────────────────────────────────────

class GorüntuServisi:
    """
    Kamera + Tespit + EventBus entegrasyonu.

    RaspberryPiMerkez tarafından her sera için ayrı örnek oluşturulur.
    _kamera_kontrol() → belirli aralıklarla çağrılır.
    HASTALIK_TESPIT olayı → bildirim + log zincirini tetikler.

    Kullanım:
        servis = GorüntuServisi(kamera=MockKamera(), tespit=MockHastalıkTespit())
        sonuc  = servis.kontrol_et("s1")
    """

    def __init__(
        self,
        kamera:   KameraBase,
        tespit:   HastalikTespitBase,
        olay_bus=None,
        guven_esigi: float = VARSAYILAN_GUVEN_ESIGI,
    ):
        self.kamera      = kamera
        self.tespit      = tespit
        self.olay_bus    = olay_bus
        self.guven_esigi = guven_esigi
        self._son_sonuc: Optional[TespitSonucu] = None

    def kontrol_et(self, sera_id: str) -> TespitSonucu:
        """
        Kameradan görüntü al → tespit yap → event yayınla.

        Raises:
            IOError: Kamera bağlantı hatası (çağıran yakalamaktan sorumlu)
        """
        goruntu = self.kamera.goruntu_al()
        sonuc   = self.tespit.tespit_et(goruntu, sera_id)
        self._son_sonuc = sonuc

        if self.olay_bus is not None:
            self._olay_yayinla(sonuc)

        return sonuc

    def _olay_yayinla(self, sonuc: TespitSonucu) -> None:
        try:
            from ..application.event_bus import OlayTur
            olay = (
                OlayTur.HASTALIK_KRITIK
                if sonuc.kritik_mi
                else OlayTur.HASTALIK_TESPIT
            )
            self.olay_bus.yayinla(olay, sonuc.to_dict())
        except Exception as e:
            print(f"[GorüntuServisi] Olay yayınlama hatası: {e}")

    @property
    def son_sonuc(self) -> Optional[TespitSonucu]:
        return self._son_sonuc

    def __repr__(self) -> str:
        return f"GorüntuServisi(kamera={self.kamera!r}, tespit={self.tespit!r})"
