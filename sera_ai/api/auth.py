"""
API Kimlik Doğrulama — X-API-Key

check_api_key() Framework'ten bağımsız, saf mantık — unit testler bunu doğrudan test eder.
get_api_key_dep() FastAPI Depends factory'si döndürür.

Neden ayrı dosya?
  FastAPI yüklü olmasa bile unit testler çalışır.
  Auth mantığı route'lardan bağımsız değişebilir.
"""
from __future__ import annotations

from typing import Callable


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
      - beklened_key varsa → tam eşleşme zorunlu
    """
    if not beklenen_key:
        return True
    return gelen_key == beklenen_key


def get_api_key_dep(beklenen_key: str) -> Callable:
    """
    FastAPI Depends factory.

    Kullanım:
        auth = get_api_key_dep(api_key)

        @router.get("/endpoint")
        async def endpoint(_=Depends(auth)):
            ...
    """
    from fastapi import Depends, HTTPException, status
    from fastapi.security import APIKeyHeader

    _header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

    async def _dep(api_key: str = Depends(_header_scheme)) -> None:
        if not check_api_key(api_key or "", beklenen_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "hata": "Yetkisiz erişim — X-API-Key header'ı gerekli",
                    "kod": "YETKISIZ",
                },
            )

    return _dep
