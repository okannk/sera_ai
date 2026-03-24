"""
ESP32-CAM Kamera — HTTP Snapshot Entegrasyonu

ESP32-CAM modülü "/capture" endpoint'i üzerinden JPEG görüntü sağlar.
Her goruntu_al() çağrısında HTTP GET atar, JPEG bytes döndürür.

Donanım:
  ESP32-CAM (AI Thinker), OV2640 sensör
  WiFi üzerinden erişim: http://<ip>/capture

Konfigürasyon (config.yaml):
  goruntu:
    kamera: esp32_cam
    seralar:
      - id: s1
        url: http://192.168.1.201/capture
        zaman_asimi_sn: 5

Bağımlılık:
  httpx (lazy import) — pip install httpx
  Yoksa IOError fırlatır.
"""
from __future__ import annotations

from .base import KameraBase


class ESP32Kamera(KameraBase):
    """
    ESP32-CAM HTTP snapshot istemcisi.

    Args:
        url              — Tam snapshot URL'i (örn: http://192.168.1.201/capture)
        zaman_asimi_sn   — HTTP timeout saniyesi (varsayılan: 5)
        cozunurluk       — ESP32-CAM'e gönderilecek çözünürlük parametresi
                           (opsiyonel, bazı firmware'lar ?framesize=X destekler)
    """

    def __init__(
        self,
        url:            str,
        zaman_asimi_sn: float = 5.0,
        cozunurluk:     str   = "",
    ):
        self.url            = url
        self.zaman_asimi_sn = zaman_asimi_sn
        self.cozunurluk     = cozunurluk
        self._istemci       = None  # lazy init

    def baglan(self) -> bool:
        """httpx istemcisini başlat ve erişilebilirliği kontrol et."""
        try:
            import httpx
            self._istemci = httpx.Client(timeout=self.zaman_asimi_sn)
            # Basit bağlantı testi — kamera yanıt veriyor mu?
            r = self._istemci.get(self.url, follow_redirects=True)
            return r.status_code == 200
        except ImportError:
            raise IOError(
                "httpx bulunamadı. Yüklemek için: pip install httpx"
            )
        except Exception as e:
            print(f"[ESP32Kamera] Bağlantı hatası {self.url}: {e}")
            return False

    def goruntu_al(self) -> bytes:
        """
        ESP32-CAM'den JPEG görüntü al.

        Returns:
            bytes — JPEG formatında ham görüntü

        Raises:
            IOError — Bağlantı hatası, timeout veya httpx yok
        """
        try:
            import httpx
        except ImportError:
            raise IOError("httpx bulunamadı. Yüklemek için: pip install httpx")

        istemci = self._istemci
        if istemci is None:
            istemci = httpx.Client(timeout=self.zaman_asimi_sn)

        hedef = self.url
        if self.cozunurluk:
            hedef = f"{self.url}?framesize={self.cozunurluk}"

        try:
            r = istemci.get(hedef, follow_redirects=True)
            if r.status_code != 200:
                raise IOError(
                    f"ESP32-CAM HTTP {r.status_code}: {self.url}"
                )
            veri = r.content
            if len(veri) < 10:
                raise IOError(f"ESP32-CAM boş yanıt: {self.url}")
            return veri
        except IOError:
            raise
        except Exception as e:
            raise IOError(f"ESP32-CAM bağlantı hatası ({self.url}): {e}") from e

    def kapat(self) -> None:
        if self._istemci is not None:
            try:
                self._istemci.close()
            except Exception:
                pass
            self._istemci = None

    def __repr__(self) -> str:
        return f"ESP32Kamera(url={self.url!r})"
