"""
API Kimlik Doğrulama — X-API-Key

Flask'tan bağımsız test edilebilir çekirdek mantık.
Flask decorator'ı ve before_request hook'u buradaki
check_api_key() fonksiyonunu çağırır.

Neden ayrı dosya?
  Flask yüklü olmasa bile unit testler çalışır.
  Auth mantığı route'lardan bağımsız değişebilir.
"""
from __future__ import annotations


# Auth'dan muaf endpoint isimleri (Flask endpoint adları)
MUAF_ENDPOINTLER = frozenset({"saglik", "metrics", "static"})


def check_api_key(gelen_key: str, beklenen_key: str) -> bool:
    """
    API anahtarı doğrula.

    Args:
        gelen_key:   İstek header'ından gelen değer (boş string = header yok)
        beklenen_key: Sistemde tanımlı anahtar

    Returns:
        True  → izin ver
        False → reddet (401)

    Kurallar:
      - beklenen_key boşsa → her şeye izin ver (dev modu, uyarıyla başlatılır)
      - beklenen_key varsa → tam eşleşme zorunlu
    """
    if not beklenen_key:
        # Key tanımlı değil = geliştirme modu → izin ver
        return True
    return gelen_key == beklenen_key
