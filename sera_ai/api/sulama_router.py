"""
Sulama Sistemi Router — /api/v1/sulama

Endpoint'ler:
  GET  /sulama/gruplar              → Tüm gruplar (faz + hedef hesaplanmış)
  POST /sulama/gruplar              → Yeni grup
  PUT  /sulama/gruplar/{id}         → Güncelle
  DELETE /sulama/gruplar/{id}       → Sil
  POST /sulama/gruplar/oto-grupla   → Bitki+faz bazında oto grupla
  GET  /sulama/program              → Bugünün takvimi
  POST /sulama/gruplar/{id}/baslat  → Hemen sula (JWT gerekli)
  POST /sulama/gruplar/{id}/durdur  → Sulamayı durdur
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .jwt_auth import get_aktif_kullanici
from .models import ApiYanit

# ── Bitki profil sabitleri ─────────────────────────────────────────────────────

BITKI_PROFIL: dict[str, dict[str, dict]] = {
    'Domates': {
        'fide':      {'gun_aralik': [0, 20],    'ec': 1.5, 'ph': 6.3, 'sure': 6,  'gunluk': 2},
        'vejatatif': {'gun_aralik': [21, 45],   'ec': 2.0, 'ph': 6.2, 'sure': 8,  'gunluk': 2},
        'cicek':     {'gun_aralik': [46, 70],   'ec': 2.8, 'ph': 6.2, 'sure': 10, 'gunluk': 3},
        'meyve':     {'gun_aralik': [71, 90],   'ec': 3.2, 'ph': 6.0, 'sure': 12, 'gunluk': 3},
        'hasat':     {'gun_aralik': [91, 999],  'ec': 2.5, 'ph': 6.1, 'sure': 8,  'gunluk': 2},
    },
    'Biber': {
        'fide':      {'gun_aralik': [0, 25],    'ec': 1.8, 'ph': 6.5, 'sure': 6,  'gunluk': 2},
        'vejatatif': {'gun_aralik': [26, 50],   'ec': 2.2, 'ph': 6.2, 'sure': 8,  'gunluk': 2},
        'cicek':     {'gun_aralik': [51, 75],   'ec': 3.0, 'ph': 6.0, 'sure': 12, 'gunluk': 3},
        'meyve':     {'gun_aralik': [76, 100],  'ec': 3.5, 'ph': 5.8, 'sure': 12, 'gunluk': 3},
        'hasat':     {'gun_aralik': [101, 999], 'ec': 3.0, 'ph': 6.0, 'sure': 10, 'gunluk': 2},
    },
    'Marul': {
        'fide':      {'gun_aralik': [0, 15],   'ec': 1.2, 'ph': 6.5, 'sure': 4,  'gunluk': 2},
        'vejatatif': {'gun_aralik': [16, 35],  'ec': 1.8, 'ph': 6.5, 'sure': 6,  'gunluk': 2},
        'hasat':     {'gun_aralik': [36, 999], 'ec': 1.5, 'ph': 6.5, 'sure': 5,  'gunluk': 2},
    },
}

FAZ_ETIKET: dict[str, str] = {
    'fide': 'FİDE', 'vejatatif': 'VEJETATİF', 'cicek': 'ÇİÇEK',
    'meyve': 'MEYVE', 'hasat': 'HASAT', 'bilinmiyor': '?',
}

FAZ_SIRA: list[str] = ['fide', 'vejatatif', 'cicek', 'meyve', 'hasat']


def faz_hesapla(bitki_turu: str, ekilis_tarihi_str: str) -> tuple[str, int, dict]:
    gun = (date.today() - date.fromisoformat(ekilis_tarihi_str)).days
    gun = max(gun, 0)
    profil = BITKI_PROFIL.get(bitki_turu, {})
    for faz, deger in profil.items():
        if deger['gun_aralik'][0] <= gun <= deger['gun_aralik'][1]:
            return faz, gun, deger
    # Varsayılan: son faz
    if profil:
        son_faz = list(profil.keys())[-1]
        return son_faz, gun, profil[son_faz]
    return 'bilinmiyor', gun, {}


# ── SQLite ─────────────────────────────────────────────────────────────────────

DB_PATH = Path('data/sulama.db')


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sulama_gruplari (
            id              TEXT PRIMARY KEY,
            ad              TEXT NOT NULL,
            bitki_turu      TEXT NOT NULL DEFAULT 'Domates',
            ekilis_tarihi   TEXT NOT NULL,
            sera_idler      TEXT NOT NULL DEFAULT '[]',
            aktif           INTEGER NOT NULL DEFAULT 1,
            olusturma_zaman TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sulama_program (
            id             TEXT PRIMARY KEY,
            grup_id        TEXT NOT NULL,
            baslangic_saat TEXT NOT NULL DEFAULT '08:00',
            sure_dakika    INTEGER NOT NULL DEFAULT 10,
            tekrar         TEXT NOT NULL DEFAULT 'gunluk',
            aktif          INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (grup_id) REFERENCES sulama_gruplari(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sulama_log (
            id         TEXT PRIMARY KEY,
            grup_id    TEXT NOT NULL,
            sera_idler TEXT NOT NULL DEFAULT '[]',
            baslangic  TEXT NOT NULL,
            bitis      TEXT,
            ec_hedef   REAL,
            ph_hedef   REAL,
            durum      TEXT NOT NULL DEFAULT 'devam_ediyor',
            FOREIGN KEY (grup_id) REFERENCES sulama_gruplari(id) ON DELETE CASCADE
        );
        """)


_init_db()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_grup(row: sqlite3.Row, conn: sqlite3.Connection) -> dict[str, Any]:
    r = dict(row)
    r['sera_idler'] = json.loads(r.get('sera_idler', '[]'))

    ekilis = r.get('ekilis_tarihi', date.today().isoformat())
    faz, gun, deger = faz_hesapla(r['bitki_turu'], ekilis)

    r['faz']           = faz
    r['faz_etiket']    = FAZ_ETIKET.get(faz, faz)
    r['faz_sira']      = FAZ_SIRA.index(faz) if faz in FAZ_SIRA else 0
    r['ekim_gunu']     = gun
    r['ec_hedef']      = deger.get('ec')
    r['ph_hedef']      = deger.get('ph')
    r['sure_dakika']   = deger.get('sure')
    r['gunluk_tekrar'] = deger.get('gunluk')

    son = conn.execute(
        "SELECT * FROM sulama_log WHERE grup_id=? ORDER BY baslangic DESC LIMIT 1",
        (r['id'],),
    ).fetchone()
    if son:
        son_dict = dict(son)
        r['son_sulama'] = son_dict['baslangic']
        r['sulama_durum'] = son_dict['durum']
    else:
        r['son_sulama']   = None
        r['sulama_durum'] = 'bekliyor'

    return r


# ── Pydantic şemalar ───────────────────────────────────────────────────────────

class GrupOlustur(BaseModel):
    ad: str
    bitki_turu: str = 'Domates'
    ekilis_tarihi: str
    sera_idler: list[str] = []


class GrupGuncelle(BaseModel):
    ad: str | None = None
    bitki_turu: str | None = None
    ekilis_tarihi: str | None = None
    sera_idler: list[str] | None = None
    aktif: bool | None = None


# ── Router ─────────────────────────────────────────────────────────────────────

sulama_router = APIRouter(prefix='/sulama', tags=['Sulama'])


@sulama_router.get('/gruplar')
async def gruplar_listele():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sulama_gruplari ORDER BY olusturma_zaman"
        ).fetchall()
        data = [_row_to_grup(r, conn) for r in rows]
    return ApiYanit(data=data).model_dump()


@sulama_router.post('/gruplar', status_code=201)
async def grup_olustur(body: GrupOlustur):
    yeni_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sulama_gruplari "
            "(id, ad, bitki_turu, ekilis_tarihi, sera_idler, olusturma_zaman) "
            "VALUES (?,?,?,?,?,?)",
            (yeni_id, body.ad, body.bitki_turu, body.ekilis_tarihi,
             json.dumps(body.sera_idler), now),
        )
        row = conn.execute(
            "SELECT * FROM sulama_gruplari WHERE id=?", (yeni_id,)
        ).fetchone()
        data = _row_to_grup(row, conn)
    return ApiYanit(data=data).model_dump()


@sulama_router.put('/gruplar/{grup_id}')
async def grup_guncelle(grup_id: str, body: GrupGuncelle):
    fields: list[str] = []
    vals: list[Any]   = []

    if body.ad is not None:
        fields.append('ad=?');             vals.append(body.ad)
    if body.bitki_turu is not None:
        fields.append('bitki_turu=?');     vals.append(body.bitki_turu)
    if body.ekilis_tarihi is not None:
        fields.append('ekilis_tarihi=?');  vals.append(body.ekilis_tarihi)
    if body.sera_idler is not None:
        fields.append('sera_idler=?');     vals.append(json.dumps(body.sera_idler))
    if body.aktif is not None:
        fields.append('aktif=?');          vals.append(int(body.aktif))

    if not fields:
        raise HTTPException(status_code=400, detail='Güncellenecek alan yok')

    vals.append(grup_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE sulama_gruplari SET {', '.join(fields)} WHERE id=?", vals
        )
        row = conn.execute(
            "SELECT * FROM sulama_gruplari WHERE id=?", (grup_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Grup bulunamadı')
        data = _row_to_grup(row, conn)
    return ApiYanit(data=data).model_dump()


@sulama_router.delete('/gruplar/{grup_id}', status_code=204)
async def grup_sil(grup_id: str):
    with get_conn() as conn:
        r = conn.execute(
            "DELETE FROM sulama_gruplari WHERE id=?", (grup_id,)
        ).rowcount
    if r == 0:
        raise HTTPException(status_code=404, detail='Grup bulunamadı')


@sulama_router.post('/gruplar/oto-grupla')
async def oto_grupla():
    """Seraları bitki türü + büyüme fazı bazında otomatik grupla."""
    try:
        from ..config.settings import konfig_yukle
        konfig = konfig_yukle()
        seralar = konfig.seralar
    except Exception:
        seralar = []

    olusturulan: list[dict] = []
    # Bitki türü bazında grupla (ekiliş tarihi bilinmiyorsa bugün kullan)
    gruplar: dict[str, list[dict]] = {}
    for sera in seralar:
        bitki = getattr(sera, 'bitki', 'Domates')
        ekilis = getattr(sera, 'ekilis_tarihi', date.today().isoformat())
        faz, gun, _ = faz_hesapla(bitki, ekilis)
        anahtar = f"{bitki}__{faz}"
        if anahtar not in gruplar:
            gruplar[anahtar] = []
        gruplar[anahtar].append({
            'id': sera.id, 'isim': sera.isim,
            'ekilis': ekilis, 'gun': gun,
        })

    with get_conn() as conn:
        for anahtar, listesi in gruplar.items():
            bitki, faz = anahtar.split('__', 1)
            ad = f"{bitki} — {FAZ_ETIKET.get(faz, faz)}"
            yeni_id = str(uuid.uuid4())[:8]
            now = datetime.now().isoformat()
            ekilis = listesi[0]['ekilis']
            sera_idler = [s['id'] for s in listesi]
            conn.execute(
                "INSERT OR IGNORE INTO sulama_gruplari "
                "(id, ad, bitki_turu, ekilis_tarihi, sera_idler, olusturma_zaman) "
                "VALUES (?,?,?,?,?,?)",
                (yeni_id, ad, bitki, ekilis, json.dumps(sera_idler), now),
            )
            olusturulan.append({'grup': ad, 'seralar': sera_idler})

    return ApiYanit(data={'olusturulan': olusturulan}).model_dump()


@sulama_router.get('/program')
async def bugunku_program():
    """Bugünün sulama takvimi — tüm aktif gruplar sıralı."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT g.*, p.baslangic_saat
               FROM sulama_gruplari g
               LEFT JOIN sulama_program p ON p.grup_id = g.id AND p.aktif=1
               WHERE g.aktif=1
               ORDER BY COALESCE(p.baslangic_saat, '99:99')"""
        ).fetchall()
        data = [_row_to_grup(r, conn) for r in rows]
    return ApiYanit(data=data).model_dump()


@sulama_router.post('/gruplar/{grup_id}/baslat')
async def sulama_baslat(grup_id: str, kullanici=Depends(get_aktif_kullanici)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sulama_gruplari WHERE id=?", (grup_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Grup bulunamadı')

        grup = _row_to_grup(row, conn)
        _, _, deger = faz_hesapla(grup['bitki_turu'], grup['ekilis_tarihi'])

        log_id = str(uuid.uuid4())[:8]
        conn.execute(
            "INSERT INTO sulama_log "
            "(id, grup_id, sera_idler, baslangic, ec_hedef, ph_hedef, durum) "
            "VALUES (?,?,?,?,?,?,?)",
            (log_id, grup_id, json.dumps(grup['sera_idler']),
             datetime.now().isoformat(),
             deger.get('ec'), deger.get('ph'), 'devam_ediyor'),
        )

    return ApiYanit(data={
        'log_id': log_id,
        'grup_id': grup_id,
        'durum': 'devam_ediyor',
    }).model_dump()


@sulama_router.get('/kazan')
async def kazan_durumu():
    """Karışım kazanı anlık durumu.
    Mock veri döner — gerçek sensör bağlandığında buradan okunur.
    """
    return ApiYanit(data={
        'seviye_yuzde': 68,
        'ec':           2.4,
        'ph':           6.1,
        'isi':          21.2,
        'tank_a':       82,
        'tank_b':       74,
        'tank_ph':      55,
        'giris_ec':     0.12,
        'giris_ph':     7.1,
        'sulaniyor':    False,
    }).model_dump()


@sulama_router.post('/gruplar/{grup_id}/durdur')
async def sulama_durdur(grup_id: str, kullanici=Depends(get_aktif_kullanici)):
    with get_conn() as conn:
        r = conn.execute(
            "UPDATE sulama_log SET durum='tamamlandi', bitis=? "
            "WHERE grup_id=? AND durum='devam_ediyor'",
            (datetime.now().isoformat(), grup_id),
        ).rowcount
    return ApiYanit(data={'durduruldu': r > 0}).model_dump()
