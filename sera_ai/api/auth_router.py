"""
JWT Auth Router

POST /api/v1/auth/login           → access_token + refresh_token
POST /api/v1/auth/refresh         → yeni token pair (rotate)
POST /api/v1/auth/logout          → refresh_token iptal
GET  /api/v1/auth/me              → mevcut kullanıcı
POST /api/v1/auth/kullanici-ekle  → admin only
POST /api/v1/auth/sifre-dogrula   → token gerektirmez, şifreyi tüm kullanıcılarla karşılaştırır
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .jwt_auth import (
    access_token_uret,
    brute_force_basarisiz,
    brute_force_kontrol,
    brute_force_sifirla,
    get_aktif_kullanici,
    get_kullanici_db,
    refresh_token_dogrula,
    refresh_token_iptal,
    refresh_token_uret,
    sifre_dogrula,
    sifre_hashle,
    token_coz,
)

_bearer_opt = HTTPBearer(auto_error=False)

def _master_dogrula(x_master_key: str = Header(default="")) -> None:
    beklenen = os.getenv("MASTER_SIFRE", "SeraAI@Master2024")
    if x_master_key != beklenen:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master şifre hatalı")

def _admin_veya_master(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_opt),
    x_master_key: str = Header(default=""),
) -> None:
    """Bearer token (admin rol) VEYA X-Master-Key kabul et."""
    beklenen = os.getenv("MASTER_SIFRE", "SeraAI@Master2024")
    if x_master_key and x_master_key == beklenen:
        return
    if credentials:
        kullanici = token_coz(credentials.credentials)
        if kullanici and kullanici["rol"] == "admin":
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin token veya master şifre gerekli",
    )

auth_router = APIRouter()


class LoginIstek(BaseModel):
    kullanici_adi: str
    sifre: str

class RefreshIstek(BaseModel):
    refresh_token: str

class LogoutIstek(BaseModel):
    refresh_token: str

class KullaniciEkleIstek(BaseModel):
    kullanici_adi: str
    sifre: str
    rol: str = "operator"

class SifreSifirlaIstek(BaseModel):
    kullanici_adi: str
    yeni_sifre: str
    master_sifre: str = ""  # Bearer token ile de kabul edilir

class SifreDegistirIstek(BaseModel):
    mevcut_sifre: str
    yeni_sifre: str


def _ayni_sifre_kontrol(db, yeni_sifre: str, haric_id: Optional[int] = None) -> None:
    """Yeni şifre başka bir kullanıcı tarafından zaten kullanılıyorsa 409 fırlat."""
    query = "SELECT id, sifre_hash FROM kullanicilar"
    params: list = []
    if haric_id is not None:
        query += " WHERE id != ?"
        params.append(haric_id)
    rows = db.execute(query, params).fetchall()
    for row in rows:
        if sifre_dogrula(yeni_sifre, row["sifre_hash"]):
            raise HTTPException(
                status_code=409,
                detail="Bu şifre başka bir kullanıcı tarafından kullanılıyor. Farklı bir şifre seçin.",
            )


class SifreDogrulaIstek2(BaseModel):
    sifre: str

    model_config = {"str_min_length": 1}

@auth_router.post("/sifre-dogrula")
def sifre_dogrula_genel(istek: SifreDogrulaIstek2, request: Request):
    """Token gerektirmez. Şifreyi DB'deki tüm kullanıcılarla karşılaştırır.
    İlk eşleşen kullanıcının token'ını döner.
    """
    ip = request.client.host if request.client else "unknown"
    brute_force_kontrol(ip)
    db   = get_kullanici_db()
    rows = db.execute("SELECT * FROM kullanicilar ORDER BY id").fetchall()
    for row in rows:
        if sifre_dogrula(istek.sifre, row["sifre_hash"]):
            brute_force_sifirla(ip)
            access  = access_token_uret(row["id"], row["kullanici_adi"], row["rol"])
            refresh = refresh_token_uret(row["id"], db)
            return JSONResponse({
                "success":       True,
                "kullanici_adi": row["kullanici_adi"],
                "rol":           row["rol"],
                "access_token":  access,
                "refresh_token": refresh,
            })
    brute_force_basarisiz(ip)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Şifre hatalı")


@auth_router.post("/login")
def login(istek: LoginIstek, request: Request):
    ip = request.client.host if request.client else "unknown"
    brute_force_kontrol(ip)
    db  = get_kullanici_db()
    row = db.execute(
        "SELECT * FROM kullanicilar WHERE kullanici_adi=?",
        (istek.kullanici_adi,),
    ).fetchone()
    if not row or not sifre_dogrula(istek.sifre, row["sifre_hash"]):
        brute_force_basarisiz(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı",
        )
    brute_force_sifirla(ip)
    access  = access_token_uret(row["id"], row["kullanici_adi"], row["rol"])
    refresh = refresh_token_uret(row["id"], db)
    return JSONResponse({"access_token": access, "refresh_token": refresh, "token_type": "bearer"})


@auth_router.post("/refresh")
def refresh(istek: RefreshIstek):
    db   = get_kullanici_db()
    data = refresh_token_dogrula(istek.refresh_token, db)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz refresh token")
    # Rotate: eskiyi iptal et, yenisini üret
    refresh_token_iptal(istek.refresh_token, db)
    access  = access_token_uret(data["kullanici_id"], data["kullanici_adi"], data["rol"])
    refresh = refresh_token_uret(data["kullanici_id"], db)
    return JSONResponse({"access_token": access, "refresh_token": refresh, "token_type": "bearer"})


@auth_router.post("/logout")
def logout(istek: LogoutIstek):
    refresh_token_iptal(istek.refresh_token, get_kullanici_db())
    return JSONResponse({"mesaj": "Çıkış yapıldı"})


@auth_router.get("/me")
def me(kullanici: dict = Depends(get_aktif_kullanici)):
    return JSONResponse(kullanici)


class SifreDogrulaIstek(BaseModel):
    sifre: str

@auth_router.post("/verify-password")
def verify_password(
    istek: SifreDogrulaIstek,
    kullanici: dict = Depends(get_aktif_kullanici),
):
    db  = get_kullanici_db()
    row = db.execute(
        "SELECT sifre_hash FROM kullanicilar WHERE id=?",
        (kullanici["id"],),
    ).fetchone()
    if not row or not sifre_dogrula(istek.sifre, row["sifre_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Şifre hatalı",
        )
    return JSONResponse({"dogrulandi": True})


@auth_router.post("/kullanici-ekle")
def kullanici_ekle(
    istek: KullaniciEkleIstek,
    _: None = Depends(_admin_veya_master),
):
    db = get_kullanici_db()
    _ayni_sifre_kontrol(db, istek.sifre)
    try:
        db.execute(
            "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol) VALUES (?,?,?)",
            (istek.kullanici_adi, sifre_hashle(istek.sifre), istek.rol),
        )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Kullanıcı adı zaten mevcut")
    return JSONResponse({"mesaj": f"{istek.kullanici_adi} oluşturuldu", "rol": istek.rol})


@auth_router.post("/sifre-sifirla")
def sifre_sifirla(
    istek: SifreSifirlaIstek,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_opt),
):
    # Master şifre body'de VEYA admin Bearer token — ikisi de yoksa 403
    beklenen = os.getenv("MASTER_SIFRE", "SeraAI@Master2024")
    auth_ok = False
    if istek.master_sifre and istek.master_sifre == beklenen:
        auth_ok = True
    elif credentials:
        kullanici = token_coz(credentials.credentials)
        if kullanici and kullanici["rol"] == "admin":
            auth_ok = True
    if not auth_ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master şifre veya admin token gerekli",
        )
    db = get_kullanici_db()
    row = db.execute(
        "SELECT id FROM kullanicilar WHERE kullanici_adi=?", (istek.kullanici_adi,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    _ayni_sifre_kontrol(db, istek.yeni_sifre, haric_id=row["id"])
    db.execute(
        "UPDATE kullanicilar SET sifre_hash=? WHERE kullanici_adi=?",
        (sifre_hashle(istek.yeni_sifre), istek.kullanici_adi),
    )
    db.commit()
    return JSONResponse({"mesaj": f"{istek.kullanici_adi} şifresi güncellendi"})


@auth_router.get("/kullanicilar")
def kullanici_listele(_: None = Depends(_admin_veya_master)):
    db = get_kullanici_db()
    rows = db.execute(
        "SELECT id, kullanici_adi, rol, olusturulma FROM kullanicilar ORDER BY id"
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@auth_router.delete("/kullanici/{kid}")
def kullanici_sil(kid: int, _: None = Depends(_admin_veya_master)):
    db = get_kullanici_db()
    row = db.execute("SELECT id, rol FROM kullanicilar WHERE id=?", (kid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if row["rol"] == "admin":
        # son admin mi?
        admin_sayisi = db.execute(
            "SELECT COUNT(*) FROM kullanicilar WHERE rol='admin'"
        ).fetchone()[0]
        if admin_sayisi <= 1:
            raise HTTPException(status_code=400, detail="Son admin kullanıcı silinemez")
    db.execute("DELETE FROM kullanicilar WHERE id=?", (kid,))
    db.commit()
    return JSONResponse({"mesaj": f"Kullanıcı {kid} silindi"})


@auth_router.post("/sifre-degistir")
def sifre_degistir(
    istek: SifreDegistirIstek,
    kullanici: dict = Depends(get_aktif_kullanici),
):
    db = get_kullanici_db()
    row = db.execute(
        "SELECT sifre_hash FROM kullanicilar WHERE id=?", (kullanici["id"],)
    ).fetchone()
    if not row or not sifre_dogrula(istek.mevcut_sifre, row["sifre_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mevcut şifre hatalı")
    _ayni_sifre_kontrol(db, istek.yeni_sifre, haric_id=kullanici["id"])
    db.execute(
        "UPDATE kullanicilar SET sifre_hash=? WHERE id=?",
        (sifre_hashle(istek.yeni_sifre), kullanici["id"]),
    )
    db.commit()
    return JSONResponse({"mesaj": "Şifre güncellendi"})
