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
