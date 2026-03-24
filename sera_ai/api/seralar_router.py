"""DB-tabanlı sera CRUD router'ı.

create_seralar_router(servis) factory'si app.py'ye enjekte edilir.
SQLite backend: data/seralar.db
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).parent.parent.parent / "data" / "seralar.db"


# ── Pydantic modeller ─────────────────────────────────────────────

class SeraEklemeIstek(BaseModel):
    isim: str = Field(..., min_length=1, max_length=100)
    alan: float = Field(100.0, gt=0)
    bitki: str = "Domates"
    sensor_tipi: str = "mock"
    mqtt_topic: Optional[str] = None
    aciklama: Optional[str] = None


class SeraGuncelleIstek(BaseModel):
    isim: Optional[str] = None
    alan: Optional[float] = None
    bitki: Optional[str] = None
    sensor_tipi: Optional[str] = None
    mqtt_topic: Optional[str] = None
    aciklama: Optional[str] = None
    aktif: Optional[bool] = None


class BitkiProfilIstek(BaseModel):
    isim: str = Field(..., min_length=1)
    min_T: float = 10.0
    max_T: float = 35.0
    opt_T: float = 22.0
    min_H: float = 50.0
    max_H: float = 90.0
    opt_H: float = 70.0
    opt_CO2: float = 1000.0
    min_ph: float = 5.5
    max_ph: float = 7.5
    opt_ph: float = 6.5
    min_ec: float = 1.0
    max_ec: float = 3.5
    min_isik: float = 200.0
    max_isik: float = 8000.0
    renk: str = "#10b981"


# ── DB yönetimi ───────────────────────────────────────────────────

@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seralar (
                id          TEXT PRIMARY KEY,
                isim        TEXT NOT NULL,
                alan        REAL NOT NULL DEFAULT 100.0,
                bitki       TEXT NOT NULL DEFAULT 'Domates',
                sensor_tipi TEXT NOT NULL DEFAULT 'mock',
                mqtt_topic  TEXT,
                aktif       INTEGER NOT NULL DEFAULT 1,
                aciklama    TEXT,
                olusturma   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bitki_profilleri (
                isim     TEXT PRIMARY KEY,
                min_T    REAL, max_T  REAL, opt_T  REAL,
                min_H    REAL, max_H  REAL, opt_H  REAL,
                opt_CO2  REAL,
                min_ph   REAL, max_ph REAL, opt_ph REAL,
                min_ec   REAL, max_ec REAL,
                min_isik REAL, max_isik REAL,
                renk     TEXT
            )
        """)

        # Seed seralar — yalnızca tablo boşsa
        count = conn.execute("SELECT COUNT(*) FROM seralar").fetchone()[0]
        if count == 0:
            now = datetime.now().isoformat()
            for sid, isim, alan, bitki, mqtt_topic in [
                ("s1", "Sera A", 500.0, "Domates",  "sera/s1/#"),
                ("s2", "Sera B", 300.0, "Biber",    "sera/s2/#"),
                ("s3", "Sera C", 200.0, "Marul",    "sera/s3/#"),
            ]:
                conn.execute(
                    "INSERT OR IGNORE INTO seralar "
                    "(id,isim,alan,bitki,sensor_tipi,mqtt_topic,aktif,olusturma) "
                    "VALUES (?,?,?,?,?,?,1,?)",
                    (sid, isim, alan, bitki, "mock", mqtt_topic, now),
                )

        # Seed bitki profilleri — yalnızca tablo boşsa
        profil_count = conn.execute("SELECT COUNT(*) FROM bitki_profilleri").fetchone()[0]
        if profil_count == 0:
            for row in [
                ("Domates",   15, 30, 23, 60, 85, 70, 1000, 5.8, 6.8, 6.2, 1.5, 3.0, 400,  8000, "#ef4444"),
                ("Biber",     18, 32, 25, 55, 80, 67,  900, 5.8, 6.5, 6.0, 1.5, 3.0, 500,  8000, "#f97316"),
                ("Marul",     10, 22, 16, 65, 85, 75,  800, 5.5, 7.0, 6.3, 0.8, 2.0, 200,  5000, "#22c55e"),
                ("Salatalık", 18, 30, 24, 60, 85, 72,  950, 6.0, 7.0, 6.5, 1.5, 2.8, 400,  7000, "#84cc16"),
                ("Diğer",     12, 30, 21, 55, 85, 70, 1000, 5.5, 7.5, 6.5, 1.0, 3.5, 200,  8000, "#6b7280"),
            ]:
                conn.execute(
                    """INSERT OR IGNORE INTO bitki_profilleri
                    (isim,min_T,max_T,opt_T,min_H,max_H,opt_H,opt_CO2,
                     min_ph,max_ph,opt_ph,min_ec,max_ec,min_isik,max_isik,renk)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    row,
                )


def load_seralar(db_path: Path = DB_PATH) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM seralar WHERE aktif=1 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Router factory ────────────────────────────────────────────────

def create_seralar_router(servis: Any, db_path: Path = DB_PATH) -> APIRouter:
    """DB-tabanlı sera CRUD router'ı oluşturur."""
    router = APIRouter(tags=["Seralar"])
    init_db(db_path)

    def _profil(bitki: str) -> dict:
        try:
            with get_conn(db_path) as conn:
                r = conn.execute(
                    "SELECT * FROM bitki_profilleri WHERE isim=?", (bitki,)
                ).fetchone()
            return dict(r) if r else {}
        except Exception:
            return {}

    def _sera_ozet(row: dict, include_profil: bool = False) -> dict:
        sid = row["id"]
        sensor = servis._sensor.get(sid, {}) if hasattr(servis, "_sensor") else {}
        durum  = servis._durum.get(sid, "NORMAL") if hasattr(servis, "_durum") else "NORMAL"
        result = {**row, "sensor": sensor, "durum": durum, "aktif": bool(row.get("aktif", 1))}
        if include_profil:
            result["profil"] = _profil(row.get("bitki", "Domates"))
        return result

    def _sync_servis() -> None:
        if not hasattr(servis, "_seralar"):
            return
        rows = load_seralar(db_path)
        servis._seralar = {r["id"]: r for r in rows}
        if hasattr(servis, "_durum"):
            for r in rows:
                servis._durum.setdefault(r["id"], "NORMAL")

    # İlk senkronizasyon
    _sync_servis()

    from .jwt_auth import get_aktif_kullanici
    from .models import ApiYanit

    # ── Inline hata yardımcıları ──────────────────────────────────
    class _HataKod:
        BULUNAMADI = "BULUNAMADI"

    def _hata(mesaj: str, kod: str = _HataKod.BULUNAMADI) -> dict:
        return {"success": False, "hata": mesaj, "kod": kod, "data": None, "meta": None}

    auth = get_aktif_kullanici

    @router.get("/seralar", summary="Tüm seralar", tags=["Seralar"])
    async def tum_seralar(_: None = Depends(auth)) -> JSONResponse:
        with get_conn(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM seralar WHERE aktif=1 ORDER BY id"
            ).fetchall()
        data = [_sera_ozet(dict(r)) for r in rows]
        return JSONResponse(content=ApiYanit(data=data).model_dump())

    @router.get("/seralar/{sid}", summary="Sera detayı", tags=["Seralar"])
    async def sera_detay(sid: str, _: None = Depends(auth)) -> JSONResponse:
        with get_conn(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM seralar WHERE id=? AND aktif=1", (sid,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_hata(f"Sera bulunamadı: {sid}"))
        return JSONResponse(content=ApiYanit(data=_sera_ozet(dict(row), include_profil=True)).model_dump())

    @router.post("/seralar", status_code=201, summary="Yeni sera ekle", tags=["Seralar"])
    async def sera_ekle(
        istek: SeraEklemeIstek, _: None = Depends(auth)
    ) -> JSONResponse:
        sid = f"s{uuid.uuid4().hex[:6]}"
        now = datetime.now().isoformat()
        with get_conn(db_path) as conn:
            conn.execute(
                "INSERT INTO seralar "
                "(id,isim,alan,bitki,sensor_tipi,mqtt_topic,aktif,aciklama,olusturma) "
                "VALUES (?,?,?,?,?,?,1,?,?)",
                (sid, istek.isim, istek.alan, istek.bitki,
                 istek.sensor_tipi, istek.mqtt_topic, istek.aciklama, now),
            )
            row = conn.execute(
                "SELECT * FROM seralar WHERE id=?", (sid,)
            ).fetchone()
        _sync_servis()
        return JSONResponse(
            status_code=201,
            content=ApiYanit(data=_sera_ozet(dict(row))).model_dump(),
        )

    @router.put("/seralar/{sid}", summary="Sera güncelle", tags=["Seralar"])
    async def sera_guncelle(
        sid: str, istek: SeraGuncelleIstek, _: None = Depends(auth)
    ) -> JSONResponse:
        with get_conn(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM seralar WHERE id=? AND aktif=1", (sid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=_hata(f"Sera bulunamadı: {sid}"))
            updates = {k: v for k, v in istek.model_dump().items() if v is not None}
            if "aktif" in updates:
                updates["aktif"] = 1 if updates["aktif"] else 0
            if updates:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                conn.execute(
                    f"UPDATE seralar SET {set_clause} WHERE id=?",
                    (*updates.values(), sid),
                )
            row = conn.execute(
                "SELECT * FROM seralar WHERE id=?", (sid,)
            ).fetchone()
        _sync_servis()
        return JSONResponse(content=ApiYanit(data=_sera_ozet(dict(row))).model_dump())

    @router.delete("/seralar/{sid}", status_code=204, summary="Sera sil", tags=["Seralar"])
    async def sera_sil(sid: str, _: None = Depends(auth)) -> Response:
        with get_conn(db_path) as conn:
            row = conn.execute(
                "SELECT id FROM seralar WHERE id=? AND aktif=1", (sid,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=_hata(f"Sera bulunamadı: {sid}"))
            conn.execute("UPDATE seralar SET aktif=0 WHERE id=?", (sid,))
        _sync_servis()
        return Response(status_code=204)

    @router.get("/seralar/{sid}/test", summary="Sera bağlantı testi", tags=["Seralar"])
    async def sera_test(sid: str, _: None = Depends(auth)) -> JSONResponse:
        with get_conn(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM seralar WHERE id=? AND aktif=1", (sid,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_hata(f"Sera bulunamadı: {sid}"))
        d = dict(row)
        sensor_tipi = d.get("sensor_tipi", "mock")
        if sensor_tipi == "mock":
            return JSONResponse(
                content=ApiYanit(
                    data={"basarili": True, "mesaj": "Mock simülasyon aktif", "gecikme_ms": 0}
                ).model_dump()
            )
        return JSONResponse(
            content=ApiYanit(
                data={
                    "basarili": False,
                    "mesaj": f"Bağlantı testi '{sensor_tipi}' için desteklenmiyor (ESP32 gerçek donanımda test edilmeli)",
                }
            ).model_dump()
        )

    @router.get("/bitki-profilleri", summary="Bitki profilleri listesi", tags=["Seralar"])
    async def bitki_profilleri(_: None = Depends(auth)) -> JSONResponse:
        with get_conn(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM bitki_profilleri ORDER BY isim"
            ).fetchall()
        return JSONResponse(content=ApiYanit(data=[dict(r) for r in rows]).model_dump())

    @router.post(
        "/bitki-profilleri",
        status_code=201,
        summary="Bitki profili ekle veya güncelle",
        tags=["Seralar"],
    )
    async def bitki_profili_ekle(
        istek: BitkiProfilIstek, _: None = Depends(auth)
    ) -> JSONResponse:
        d = istek.model_dump()
        cols = list(d.keys())
        vals = list(d.values())
        with get_conn(db_path) as conn:
            existing = conn.execute(
                "SELECT isim FROM bitki_profilleri WHERE isim=?", (istek.isim,)
            ).fetchone()
            if existing:
                set_clause = ", ".join(f"{k}=?" for k in cols[1:])
                conn.execute(
                    f"UPDATE bitki_profilleri SET {set_clause} WHERE isim=?",
                    (*vals[1:], istek.isim),
                )
            else:
                placeholders = ", ".join("?" * len(cols))
                col_names = ", ".join(cols)
                conn.execute(
                    f"INSERT INTO bitki_profilleri ({col_names}) VALUES ({placeholders})",
                    vals,
                )
            row = conn.execute(
                "SELECT * FROM bitki_profilleri WHERE isim=?", (istek.isim,)
            ).fetchone()
        return JSONResponse(
            status_code=201,
            content=ApiYanit(data=dict(row)).model_dump(),
        )

    return router
