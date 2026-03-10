"""
API Pydantic Modelleri

Request ve response şemalarını tanımlar.
FastAPI /docs endpoint'inde otomatik gösterilir.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator


# ── Request modelleri ──────────────────────────────────────────

class KomutIstek(BaseModel):
    """POST /api/v1/seralar/{sid}/komut request body."""

    komut: str
    kaynak: str = "api"

    @field_validator("komut")
    @classmethod
    def komut_gecerli(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("komut boş olamaz")
        return v


class SeraEkleme(BaseModel):
    """POST /api/v1/seralar request body."""

    isim: str
    bitki: str = "Diğer"
    alan: float = 100.0
    esp32_ip: str = ""

    @field_validator("isim")
    @classmethod
    def isim_gecerli(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("sera adı boş olamaz")
        return v

    @field_validator("alan")
    @classmethod
    def alan_pozitif(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("alan pozitif olmalı")
        return v


class SeraGuncelleme(BaseModel):
    """PUT /api/v1/seralar/{sid} request body — tüm alanlar isteğe bağlı."""

    isim: Optional[str] = None
    bitki: Optional[str] = None
    alan: Optional[float] = None
    esp32_ip: Optional[str] = None

    @model_validator(mode="after")
    def en_az_bir_alan(self) -> "SeraGuncelleme":
        if all(v is None for v in [self.isim, self.bitki, self.alan, self.esp32_ip]):
            raise ValueError("en az bir alan güncellenmeli")
        return self


# ── Response modelleri ─────────────────────────────────────────

class ApiMeta(BaseModel):
    ts: str = ""

    model_config = {"extra": "allow"}

    def __init__(self, **data: Any) -> None:
        if "ts" not in data:
            data["ts"] = datetime.now().isoformat()
        super().__init__(**data)


class ApiYanit(BaseModel):
    """Başarılı yanıt zarfı."""

    success: bool = True
    data: Any = None
    hata: Optional[str] = None
    kod: Optional[str] = None
    meta: ApiMeta = None  # type: ignore[assignment]

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data: Any) -> None:
        if data.get("meta") is None:
            data["meta"] = ApiMeta()
        super().__init__(**data)


class HataYanit(BaseModel):
    """Hata yanıt zarfı — {"success": false, "hata": ..., "kod": ...}"""

    success: bool = False
    hata: str
    kod: str = "HATA"
    meta: ApiMeta = None  # type: ignore[assignment]

    def __init__(self, **data: Any) -> None:
        if data.get("meta") is None:
            data["meta"] = ApiMeta()
        super().__init__(**data)
