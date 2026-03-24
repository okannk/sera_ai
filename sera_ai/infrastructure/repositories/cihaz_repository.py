"""
SQLite Cihaz Repository

ESP32-S3 cihaz kimlik ve kayıt bilgilerini saklar.
MQTT broker auth, bağlantı takibi ve provisioning bileşenleri bu repo'yu kullanır.

Tablolar:
  cihazlar      — CihazKimlik: kimlik, donanım, son görülme
  cihaz_kayitlar — CihazKayit: sifre_hash, topic whitelist
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from sera_ai.domain.models import CihazKimlik, CihazKayit

_ZAMAN_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def _to_dt(s: str) -> datetime:
    try:
        return datetime.strptime(s, _ZAMAN_FMT)
    except ValueError:
        return datetime.fromisoformat(s)


def _from_dt(dt: datetime) -> str:
    return dt.strftime(_ZAMAN_FMT)


class SQLiteCihazRepository:
    """
    CihazKimlik ve CihazKayit kayıtlarını SQLite'a yazar/okur.

    Kullanım:
        repo = SQLiteCihazRepository("sera_data.db")
        repo.kayit_et(cihaz, kayit)
        c = repo.bul("SERA-IST01-001")
    """

    _CREATE_CIHAZLAR = """
    CREATE TABLE IF NOT EXISTS cihazlar (
        cihaz_id          TEXT PRIMARY KEY,
        tesis_kodu        TEXT NOT NULL,
        sera_id           TEXT NOT NULL,
        seri_no           TEXT NOT NULL,
        mac_adresi        TEXT NOT NULL DEFAULT '',
        baglanti_tipi     TEXT NOT NULL DEFAULT 'WiFi',
        firmware_versiyon TEXT NOT NULL DEFAULT '1.0.0',
        son_gorulen       TEXT NOT NULL,
        aktif             INTEGER NOT NULL DEFAULT 1
    );
    """

    _CREATE_KAYITLAR = """
    CREATE TABLE IF NOT EXISTS cihaz_kayitlar (
        cihaz_id              TEXT PRIMARY KEY,
        sifre_hash            TEXT NOT NULL,
        izin_verilen_konular  TEXT NOT NULL DEFAULT '[]',
        kayit_tarihi          TEXT NOT NULL,
        FOREIGN KEY (cihaz_id) REFERENCES cihazlar(cihaz_id)
    );
    """

    def __init__(self, db_yolu: str) -> None:
        self._db_yolu = db_yolu
        self._lock    = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._baglanti() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(self._CREATE_CIHAZLAR)
            conn.execute(self._CREATE_KAYITLAR)

    @contextmanager
    def _baglanti(self):
        conn = sqlite3.connect(self._db_yolu, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with self._lock:
                yield conn
                conn.commit()
        finally:
            conn.close()

    # ── Yazma ─────────────────────────────────────────────────

    def kayit_et(self, cihaz: CihazKimlik, kayit: CihazKayit) -> None:
        """Yeni cihazı ve kimlik doğrulama kaydını ekle (idempotent)."""
        with self._baglanti() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cihazlar
                  (cihaz_id, tesis_kodu, sera_id, seri_no,
                   mac_adresi, baglanti_tipi, firmware_versiyon, son_gorulen, aktif)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cihaz.cihaz_id, cihaz.tesis_kodu, cihaz.sera_id, cihaz.seri_no,
                    cihaz.mac_adresi, cihaz.baglanti_tipi, cihaz.firmware_versiyon,
                    _from_dt(cihaz.son_gorulen), int(cihaz.aktif),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO cihaz_kayitlar
                  (cihaz_id, sifre_hash, izin_verilen_konular, kayit_tarihi)
                VALUES (?, ?, ?, ?)
                """,
                (
                    kayit.cihaz_id,
                    kayit.sifre_hash,
                    json.dumps(kayit.izin_verilen_konular),
                    _from_dt(kayit.kayit_tarihi),
                ),
            )

    def guncelle(self, cihaz: CihazKimlik) -> None:
        """Cihaz kimlik bilgilerini güncelle (son_gorulen dahil)."""
        with self._baglanti() as conn:
            conn.execute(
                """
                UPDATE cihazlar SET
                  tesis_kodu=?, sera_id=?, mac_adresi=?,
                  baglanti_tipi=?, firmware_versiyon=?, son_gorulen=?, aktif=?
                WHERE cihaz_id=?
                """,
                (
                    cihaz.tesis_kodu, cihaz.sera_id, cihaz.mac_adresi,
                    cihaz.baglanti_tipi, cihaz.firmware_versiyon,
                    _from_dt(cihaz.son_gorulen), int(cihaz.aktif),
                    cihaz.cihaz_id,
                ),
            )

    def son_gorulen_guncelle(self, cihaz_id: str, zaman: Optional[datetime] = None) -> None:
        """Sadece son_gorulen alanını güncelle (kalp atışı için)."""
        t = _from_dt(zaman or datetime.now())
        with self._baglanti() as conn:
            conn.execute(
                "UPDATE cihazlar SET son_gorulen=? WHERE cihaz_id=?",
                (t, cihaz_id),
            )

    def sifre_guncelle(self, cihaz_id: str, yeni_hash: str) -> None:
        """Cihaz şifre hash'ini güncelle (parola sıfırlama)."""
        with self._baglanti() as conn:
            conn.execute(
                "UPDATE cihaz_kayitlar SET sifre_hash=? WHERE cihaz_id=?",
                (yeni_hash, cihaz_id),
            )

    def sil(self, cihaz_id: str) -> bool:
        """Cihazı ve kayıt bilgisini sil. True → silindi, False → bulunamadı."""
        with self._baglanti() as conn:
            c = conn.execute("DELETE FROM cihaz_kayitlar WHERE cihaz_id=?", (cihaz_id,))
            conn.execute("DELETE FROM cihazlar WHERE cihaz_id=?", (cihaz_id,))
            return c.rowcount > 0

    # ── Okuma ─────────────────────────────────────────────────

    def listele(self, tesis_kodu: Optional[str] = None) -> list[CihazKimlik]:
        """Tüm (veya tesise ait) cihazları döndür."""
        with self._baglanti() as conn:
            if tesis_kodu:
                rows = conn.execute(
                    "SELECT * FROM cihazlar WHERE tesis_kodu=? ORDER BY cihaz_id",
                    (tesis_kodu,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cihazlar ORDER BY cihaz_id"
                ).fetchall()
            return [self._row_to_cihaz(r) for r in rows]

    def bul(self, cihaz_id: str) -> Optional[CihazKimlik]:
        """Tek cihaz; yoksa None."""
        with self._baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM cihazlar WHERE cihaz_id=?", (cihaz_id,)
            ).fetchone()
            return self._row_to_cihaz(row) if row else None

    def kayit_bul(self, cihaz_id: str) -> Optional[CihazKayit]:
        """Cihazın auth kaydını döndür; yoksa None."""
        with self._baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM cihaz_kayitlar WHERE cihaz_id=?", (cihaz_id,)
            ).fetchone()
            if not row:
                return None
            return CihazKayit(
                cihaz_id=row["cihaz_id"],
                sifre_hash=row["sifre_hash"],
                izin_verilen_konular=json.loads(row["izin_verilen_konular"]),
                kayit_tarihi=_to_dt(row["kayit_tarihi"]),
            )

    def tesis_cihaz_sayisi(self, tesis_kodu: str) -> int:
        """Bir tesiste kayıtlı cihaz sayısı (provisioning sıra no için)."""
        with self._baglanti() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM cihazlar WHERE tesis_kodu=?", (tesis_kodu,)
            ).fetchone()
            return row[0] if row else 0

    # ── Yardımcı ──────────────────────────────────────────────

    @staticmethod
    def _row_to_cihaz(row) -> CihazKimlik:
        return CihazKimlik(
            cihaz_id=row["cihaz_id"],
            tesis_kodu=row["tesis_kodu"],
            sera_id=row["sera_id"],
            seri_no=row["seri_no"],
            mac_adresi=row["mac_adresi"],
            baglanti_tipi=row["baglanti_tipi"],
            firmware_versiyon=row["firmware_versiyon"],
            son_gorulen=_to_dt(row["son_gorulen"]),
            aktif=bool(row["aktif"]),
        )
