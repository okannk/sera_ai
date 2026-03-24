"""
JWT Authentication — python-jose + passlib + SQLite

Tablolar:
  kullanicilar   (id, kullanici_adi, sifre_hash, rol, olusturulma)
  refresh_tokenlar (id, token_hash, kullanici_id, son_kullanma, iptal)

İlk çalıştırmada admin kullanıcı otomatik oluşturulur.
ADMIN_SIFRE env değişkeninden okunur, yoksa "sera2024!" kullanılır.
JWT_SECRET env değişkeninden okunur, yoksa rastgele üretilir.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt as _bcrypt_lib
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ── Sabitler ────────────────────────────────────────────────
ALGORITHM      = "HS256"
ACCESS_SURE_SA = 8 * 3600       # 8 saat (saniye)
REFRESH_SURE_SA= 7 * 24 * 3600  # 7 gün

_JWT_SECRET: Optional[str] = None

def _get_secret() -> str:
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
    return _JWT_SECRET

# ── Şifre hashleme (bcrypt doğrudan — passlib compat sorunu yok) ─
def sifre_hashle(sifre: str) -> str:
    return _bcrypt_lib.hashpw(sifre.encode(), _bcrypt_lib.gensalt()).decode()

def sifre_dogrula(sifre: str, hash_: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(sifre.encode(), hash_.encode())
    except Exception:
        return False

# ── SQLite ──────────────────────────────────────────────────
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "kullanicilar.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

def _baglanti() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _tablo_olustur(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi    TEXT UNIQUE NOT NULL,
            sifre_hash       TEXT NOT NULL,
            rol              TEXT NOT NULL DEFAULT 'operator',
            olusturulma      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS refresh_tokenlar (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash   TEXT UNIQUE NOT NULL,
            kullanici_id INTEGER NOT NULL,
            son_kullanma TEXT NOT NULL,
            iptal        INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id)
        );
    """)
    conn.commit()

def _admin_olustur(conn: sqlite3.Connection) -> None:
    """İlk çalıştırmada admin yoksa oluştur."""
    mevcut = conn.execute(
        "SELECT id FROM kullanicilar WHERE rol='admin' LIMIT 1"
    ).fetchone()
    if mevcut:
        return
    sifre = os.getenv("ADMIN_SIFRE", "sera2024!")
    conn.execute(
        "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol) VALUES (?,?,?)",
        ("admin", sifre_hashle(sifre), "admin"),
    )
    conn.commit()
    print(f"[JWT] Admin kullanıcı oluşturuldu (kullanici: admin)")

_db_conn: Optional[sqlite3.Connection] = None

def get_kullanici_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = _baglanti()
        _tablo_olustur(_db_conn)
        _admin_olustur(_db_conn)
    return _db_conn

# ── Token üretimi ────────────────────────────────────────────
def access_token_uret(kullanici_id: int, kullanici_adi: str, rol: str) -> str:
    bitis = datetime.now(timezone.utc) + timedelta(seconds=ACCESS_SURE_SA)
    return jwt.encode(
        {"sub": str(kullanici_id), "adi": kullanici_adi, "rol": rol, "exp": bitis},
        _get_secret(), algorithm=ALGORITHM,
    )

def refresh_token_uret(kullanici_id: int, db: sqlite3.Connection) -> str:
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    son_kullanma = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_SURE_SA)
    with _lock:
        db.execute(
            "INSERT INTO refresh_tokenlar (token_hash, kullanici_id, son_kullanma) VALUES (?,?,?)",
            (token_hash, kullanici_id, son_kullanma.isoformat()),
        )
        db.commit()
    return token

def refresh_token_dogrula(token: str, db: sqlite3.Connection) -> Optional[dict]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.execute(
        """SELECT rt.id, rt.kullanici_id, rt.son_kullanma, rt.iptal,
                  k.kullanici_adi, k.rol
           FROM refresh_tokenlar rt
           JOIN kullanicilar k ON k.id = rt.kullanici_id
           WHERE rt.token_hash = ?""",
        (token_hash,),
    ).fetchone()
    if not row:
        return None
    if row["iptal"]:
        return None
    if datetime.fromisoformat(row["son_kullanma"]) < datetime.now(timezone.utc):
        return None
    return dict(row)

def refresh_token_iptal(token: str, db: sqlite3.Connection) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        db.execute(
            "UPDATE refresh_tokenlar SET iptal=1 WHERE token_hash=?",
            (token_hash,),
        )
        db.commit()

# ── Brute force koruması (in-memory, IP bazlı) ──────────────
_PENCERE_SN   = 60    # 60 saniyelik pencere
_MAX_DENEME   = 10    # pencerede max başarısız giriş
_ENGEL_SN     = 300   # 5 dakika engelleme

# {ip: [timestamp, ...]}  ve  {ip: engel_bitis_timestamp}
_giris_denemeleri: dict[str, list[float]] = {}
_engellenen_ipler: dict[str, float] = {}
_bf_lock = threading.Lock()

import time as _time

def brute_force_kontrol(ip: str) -> None:
    """IP engellenmiş veya limit aşılmışsa 429 fırlat."""
    simdi = _time.time()
    with _bf_lock:
        # Engel süresi doldu mu?
        if ip in _engellenen_ipler:
            if simdi < _engellenen_ipler[ip]:
                kalan = int(_engellenen_ipler[ip] - simdi)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Çok fazla başarısız giriş. {kalan} saniye bekleyin.",
                )
            else:
                del _engellenen_ipler[ip]
                _giris_denemeleri.pop(ip, None)

def brute_force_basarisiz(ip: str) -> None:
    """Başarısız giriş kaydet, limit aşıldıysa IP'yi engelle."""
    simdi = _time.time()
    with _bf_lock:
        pencere_baslangic = simdi - _PENCERE_SN
        denemeler = [t for t in _giris_denemeleri.get(ip, []) if t > pencere_baslangic]
        denemeler.append(simdi)
        _giris_denemeleri[ip] = denemeler
        if len(denemeler) >= _MAX_DENEME:
            _engellenen_ipler[ip] = simdi + _ENGEL_SN
            _giris_denemeleri.pop(ip, None)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Çok fazla başarısız giriş. {_ENGEL_SN} saniye bekleyin.",
            )

def brute_force_sifirla(ip: str) -> None:
    """Başarılı girişte sayacı sıfırla."""
    with _bf_lock:
        _giris_denemeleri.pop(ip, None)
        _engellenen_ipler.pop(ip, None)

# ── FastAPI bağımlılığı ─────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Geçersiz veya eksik token",
    headers={"WWW-Authenticate": "Bearer"},
)

def get_aktif_kullanici(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Bearer token zorunlu — yoksa veya geçersizse 401."""
    if not credentials:
        raise _401
    try:
        payload = jwt.decode(credentials.credentials, _get_secret(), algorithms=[ALGORITHM])
        return {
            "id":             int(payload["sub"]),
            "kullanici_adi":  payload["adi"],
            "rol":            payload["rol"],
        }
    except JWTError:
        raise _401

def admin_gerektir(kullanici: dict = Depends(get_aktif_kullanici)) -> dict:
    if kullanici["rol"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin yetkisi gerekli")
    return kullanici

def token_coz(token: str) -> Optional[dict]:
    """Token doğrula; geçersizse None döner (exception fırlatmaz)."""
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
        return {
            "id":            int(payload["sub"]),
            "kullanici_adi": payload["adi"],
            "rol":           payload["rol"],
        }
    except JWTError:
        return None
