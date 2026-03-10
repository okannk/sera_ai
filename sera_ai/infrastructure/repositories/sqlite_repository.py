"""
SQLite Repository Implementasyonu

Neden SQLite?
  - Sıfır sunucu kurulumu: RPi 5 üzerinde tek dosya.
  - Yüzlerce okuma/dakika için fazlasıyla yeterli.
  - InfluxDB geçişinde sadece bu dosya değişir; arayüz aynı kalır.

Şema kararları:
  - sensor_okumalar: tx_id PRIMARY KEY → idempotent yeniden yazma
  - komut_gecmisi: AUTOINCREMENT id → sıralı geçmiş
  - WAL modu: eş zamanlı okuma/yazma çakışmasını önler
  - Thread-safe: check_same_thread=False + explicit lock
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from sera_ai.domain.models import Komut, KomutSonucu, SensorOkuma
from .base import KomutRepository, SensorRepository

# ISO-8601 zaman formatı — SQLite TEXT olarak saklanır, sıralanabilir
_ZAMAN_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def _to_dt(s: str) -> datetime:
    return datetime.strptime(s, _ZAMAN_FMT)


def _from_dt(dt: datetime) -> str:
    return dt.strftime(_ZAMAN_FMT)


class SQLiteSensorRepository(SensorRepository):
    """
    SensorOkuma kayıtlarını SQLite'a yazar/okur.

    Kullanım:
        repo = SQLiteSensorRepository("sera_data.db")
        repo.kaydet(okuma)
        son = repo.son_okuma("s1")
    """

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS sensor_okumalar (
        tx_id        TEXT PRIMARY KEY,
        sera_id      TEXT NOT NULL,
        zaman        TEXT NOT NULL,
        T            REAL NOT NULL,
        H            REAL NOT NULL,
        co2          INTEGER NOT NULL,
        isik         INTEGER NOT NULL,
        toprak_nem   INTEGER NOT NULL,
        ph           REAL NOT NULL,
        ec           REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sensor_sera_zaman
        ON sensor_okumalar(sera_id, zaman);
    """

    def __init__(self, db_yolu: str = "sera_data.db") -> None:
        self._db_yolu = db_yolu
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._baglanti() as conn:
            conn.executescript(self._CREATE_SQL)

    @contextmanager
    def _baglanti(self):
        conn = sqlite3.connect(
            self._db_yolu,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with self._lock:
                yield conn
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Yardımcı ──────────────────────────────────────────────────

    @staticmethod
    def _satir_to_okuma(row: tuple) -> SensorOkuma:
        tx_id, sera_id, zaman, T, H, co2, isik, toprak_nem, ph, ec = row
        return SensorOkuma(
            sera_id=sera_id,
            T=T, H=H, co2=co2, isik=isik,
            toprak_nem=toprak_nem, ph=ph, ec=ec,
            zaman=_to_dt(zaman),
            tx_id=tx_id,
        )

    @staticmethod
    def _okuma_to_tuple(o: SensorOkuma) -> tuple:
        return (
            o.tx_id, o.sera_id, _from_dt(o.zaman),
            o.T, o.H, o.co2, o.isik, o.toprak_nem, o.ph, o.ec,
        )

    # ── SensorRepository arayüzü ──────────────────────────────────

    def kaydet(self, okuma: SensorOkuma) -> None:
        sql = """
        INSERT OR IGNORE INTO sensor_okumalar
            (tx_id, sera_id, zaman, T, H, co2, isik, toprak_nem, ph, ec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._baglanti() as conn:
            conn.execute(sql, self._okuma_to_tuple(okuma))

    def toplu_kaydet(self, okumalar: list[SensorOkuma]) -> None:
        sql = """
        INSERT OR IGNORE INTO sensor_okumalar
            (tx_id, sera_id, zaman, T, H, co2, isik, toprak_nem, ph, ec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._baglanti() as conn:
            conn.executemany(sql, [self._okuma_to_tuple(o) for o in okumalar])

    def son_okuma(self, sera_id: str) -> Optional[SensorOkuma]:
        sql = """
        SELECT tx_id, sera_id, zaman, T, H, co2, isik, toprak_nem, ph, ec
        FROM sensor_okumalar
        WHERE sera_id = ?
        ORDER BY zaman DESC
        LIMIT 1
        """
        with self._baglanti() as conn:
            row = conn.execute(sql, (sera_id,)).fetchone()
        return self._satir_to_okuma(row) if row else None

    def aralik_oku(
        self,
        sera_id: str,
        baslangic: datetime,
        bitis: datetime,
    ) -> list[SensorOkuma]:
        sql = """
        SELECT tx_id, sera_id, zaman, T, H, co2, isik, toprak_nem, ph, ec
        FROM sensor_okumalar
        WHERE sera_id = ?
          AND zaman >= ?
          AND zaman <= ?
        ORDER BY zaman ASC
        """
        with self._baglanti() as conn:
            rows = conn.execute(
                sql,
                (sera_id, _from_dt(baslangic), _from_dt(bitis)),
            ).fetchall()
        return [self._satir_to_okuma(r) for r in rows]

    def tum_seralar(self) -> list[str]:
        sql = "SELECT DISTINCT sera_id FROM sensor_okumalar ORDER BY sera_id"
        with self._baglanti() as conn:
            rows = conn.execute(sql).fetchall()
        return [r[0] for r in rows]

    def temizle(self, sera_id: str, oncesi: datetime) -> int:
        sql = "DELETE FROM sensor_okumalar WHERE sera_id = ? AND zaman < ?"
        with self._baglanti() as conn:
            cur = conn.execute(sql, (sera_id, _from_dt(oncesi)))
            return cur.rowcount


class SQLiteKomutRepository(KomutRepository):
    """
    KomutSonucu kayıtlarını SQLite'a yazar/okur.

    Kullanım:
        repo = SQLiteKomutRepository("sera_data.db")
        repo.kaydet("s1", komut_sonucu)
        gecmis = repo.gecmis("s1", limit=50)
    """

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS komut_gecmisi (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        sera_id      TEXT NOT NULL,
        zaman        TEXT NOT NULL,
        komut        TEXT NOT NULL,
        basarili     INTEGER NOT NULL,
        mesaj        TEXT NOT NULL,
        kaynak       TEXT NOT NULL DEFAULT 'sistem',
        kullanici_id TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_komut_sera_zaman
        ON komut_gecmisi(sera_id, zaman);
    """

    def __init__(self, db_yolu: str = "sera_data.db") -> None:
        self._db_yolu = db_yolu
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._baglanti() as conn:
            conn.executescript(self._CREATE_SQL)
            # Mevcut DB'lere kolon ekle (migration)
            for stmt in [
                "ALTER TABLE komut_gecmisi ADD COLUMN kaynak TEXT NOT NULL DEFAULT 'sistem'",
                "ALTER TABLE komut_gecmisi ADD COLUMN kullanici_id TEXT NOT NULL DEFAULT ''",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # sütun zaten var

    @contextmanager
    def _baglanti(self):
        conn = sqlite3.connect(
            self._db_yolu,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            with self._lock:
                yield conn
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── KomutRepository arayüzü ───────────────────────────────────

    def kaydet(self, sera_id: str, sonuc: KomutSonucu) -> None:
        sql = """
        INSERT INTO komut_gecmisi (sera_id, zaman, komut, basarili, mesaj, kaynak, kullanici_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._baglanti() as conn:
            conn.execute(sql, (
                sera_id,
                _from_dt(sonuc.zaman),
                sonuc.komut.value,
                int(sonuc.basarili),
                sonuc.mesaj,
                sonuc.kaynak,
                sonuc.kullanici_id,
            ))

    def gecmis(self, sera_id: str, limit: int = 100) -> list[KomutSonucu]:
        sql = """
        SELECT zaman, komut, basarili, mesaj, kaynak, kullanici_id
        FROM komut_gecmisi
        WHERE sera_id = ?
        ORDER BY id DESC
        LIMIT ?
        """
        with self._baglanti() as conn:
            rows = conn.execute(sql, (sera_id, limit)).fetchall()
        return [
            KomutSonucu(
                komut=Komut(row[1]),
                basarili=bool(row[2]),
                mesaj=row[3],
                zaman=_to_dt(row[0]),
                kaynak=row[4] if len(row) > 4 else "sistem",
                kullanici_id=row[5] if len(row) > 5 else "",
            )
            for row in rows
        ]

    def basarisiz_sayisi(self, sera_id: str, son_n_dk: int = 60) -> int:
        sinir = datetime.now() - timedelta(minutes=son_n_dk)
        sql = """
        SELECT COUNT(*) FROM komut_gecmisi
        WHERE sera_id = ?
          AND zaman >= ?
          AND basarili = 0
        """
        with self._baglanti() as conn:
            row = conn.execute(sql, (sera_id, _from_dt(sinir))).fetchone()
        return row[0] if row else 0
