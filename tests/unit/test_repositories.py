"""
SQLite Repository Testleri

Her test geçici (in-memory veya tmp) DB kullanır → yan etki yok.
"""
from __future__ import annotations

import tempfile
import os
from datetime import datetime, timedelta

import pytest

from sera_ai.domain.models import Komut, KomutSonucu, SensorOkuma
from sera_ai.infrastructure.repositories import (
    SQLiteKomutRepository,
    SQLiteSensorRepository,
)


# ── Fixture'lar ───────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Her test için izole geçici DB dosyası."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sensor_repo(tmp_db):
    return SQLiteSensorRepository(tmp_db)


@pytest.fixture
def komut_repo(tmp_db):
    return SQLiteKomutRepository(tmp_db)


@pytest.fixture
def ornek_okuma() -> SensorOkuma:
    return SensorOkuma(
        sera_id="s1", T=23.5, H=70.0, co2=950,
        isik=500, toprak_nem=512, ph=6.5, ec=1.8,
    )


@pytest.fixture
def ornek_komut_sonucu() -> KomutSonucu:
    return KomutSonucu(
        komut=Komut.SULAMA_BASLAT,
        basarili=True,
        mesaj="Sulama başlatıldı",
    )


# ── SQLiteSensorRepository Testleri ──────────────────────────────

class TestSQLiteSensorRepository:

    def test_kaydet_ve_son_okuma(self, sensor_repo, ornek_okuma):
        sensor_repo.kaydet(ornek_okuma)
        son = sensor_repo.son_okuma("s1")
        assert son is not None
        assert son.tx_id == ornek_okuma.tx_id
        assert son.T == pytest.approx(23.5)
        assert son.sera_id == "s1"

    def test_bos_db_son_okuma_none(self, sensor_repo):
        assert sensor_repo.son_okuma("yok") is None

    def test_idempotent_kaydet(self, sensor_repo, ornek_okuma):
        """Aynı tx_id iki kez yazılırsa ikinci INSERT OR IGNORE ile atlanır."""
        sensor_repo.kaydet(ornek_okuma)
        sensor_repo.kaydet(ornek_okuma)  # ikinci kez — hata vermemeli
        assert len(sensor_repo.aralik_oku(
            "s1",
            datetime.now() - timedelta(hours=1),
            datetime.now() + timedelta(hours=1),
        )) == 1

    def test_toplu_kaydet(self, sensor_repo):
        okumalar = [
            SensorOkuma("s1", T=20+i, H=60.0, co2=800, isik=300,
                        toprak_nem=400, ph=6.0, ec=1.5)
            for i in range(5)
        ]
        sensor_repo.toplu_kaydet(okumalar)
        assert sensor_repo.son_okuma("s1") is not None

    def test_aralik_oku_doğru_filtreler(self, sensor_repo):
        baz = datetime(2025, 1, 1, 12, 0, 0)
        okumalar = []
        for i in range(6):
            o = SensorOkuma("s1", T=20.0, H=60.0, co2=800, isik=300,
                            toprak_nem=400, ph=6.0, ec=1.5,
                            zaman=baz + timedelta(hours=i))
            okumalar.append(o)
        sensor_repo.toplu_kaydet(okumalar)

        # Saat 12–14 arası → 3 kayıt (12:00, 13:00, 14:00)
        aralik = sensor_repo.aralik_oku(
            "s1",
            baslangic=baz,
            bitis=baz + timedelta(hours=2),
        )
        assert len(aralik) == 3
        # Kronolojik sırada gelmiş olmalı
        zamanlar = [o.zaman for o in aralik]
        assert zamanlar == sorted(zamanlar)

    def test_tum_seralar(self, sensor_repo):
        for sid in ["s1", "s2", "s3"]:
            sensor_repo.kaydet(
                SensorOkuma(sid, T=22.0, H=65.0, co2=850, isik=400,
                            toprak_nem=500, ph=6.3, ec=1.6)
            )
        seralar = sensor_repo.tum_seralar()
        assert set(seralar) == {"s1", "s2", "s3"}

    def test_temizle(self, sensor_repo):
        baz = datetime(2025, 1, 1, 0, 0, 0)
        okumalar = [
            SensorOkuma("s1", T=20.0, H=60.0, co2=800, isik=300,
                        toprak_nem=400, ph=6.0, ec=1.5,
                        zaman=baz + timedelta(days=i))
            for i in range(10)
        ]
        sensor_repo.toplu_kaydet(okumalar)

        # 5 günden öncekileri sil → 5 kayıt silinmeli
        silinen = sensor_repo.temizle("s1", oncesi=baz + timedelta(days=5))
        assert silinen == 5

        kalan = sensor_repo.aralik_oku(
            "s1",
            baslangic=datetime.min,
            bitis=datetime.max,
        )
        assert len(kalan) == 5

    def test_farkli_seralar_karismaz(self, sensor_repo):
        sensor_repo.kaydet(
            SensorOkuma("s1", T=25.0, H=70.0, co2=900, isik=500,
                        toprak_nem=500, ph=6.5, ec=1.8)
        )
        sensor_repo.kaydet(
            SensorOkuma("s2", T=18.0, H=65.0, co2=800, isik=300,
                        toprak_nem=400, ph=6.0, ec=1.5)
        )
        assert sensor_repo.son_okuma("s1").T == pytest.approx(25.0)
        assert sensor_repo.son_okuma("s2").T == pytest.approx(18.0)


# ── SQLiteKomutRepository Testleri ───────────────────────────────

class TestSQLiteKomutRepository:

    def test_kaydet_ve_gecmis(self, komut_repo, ornek_komut_sonucu):
        komut_repo.kaydet("s1", ornek_komut_sonucu)
        gecmis = komut_repo.gecmis("s1")
        assert len(gecmis) == 1
        assert gecmis[0].komut == Komut.SULAMA_BASLAT
        assert gecmis[0].basarili is True

    def test_gecmis_limit(self, komut_repo):
        for i in range(20):
            komut_repo.kaydet("s1", KomutSonucu(
                komut=Komut.FAN_BASLAT, basarili=True, mesaj=f"ok-{i}"
            ))
        assert len(komut_repo.gecmis("s1", limit=10)) == 10
        assert len(komut_repo.gecmis("s1", limit=100)) == 20

    def test_gecmis_yeni_eskiden_once(self, komut_repo):
        """Geçmiş yeni → eski sıralı gelmeli."""
        for komut in [Komut.FAN_BASLAT, Komut.ISITICI_BASLAT, Komut.SULAMA_BASLAT]:
            komut_repo.kaydet("s1", KomutSonucu(komut=komut, basarili=True, mesaj="ok"))
        gecmis = komut_repo.gecmis("s1")
        assert gecmis[0].komut == Komut.SULAMA_BASLAT  # en son yazılan

    def test_bos_gecmis(self, komut_repo):
        assert komut_repo.gecmis("yok") == []

    def test_basarisiz_sayisi(self, komut_repo):
        # 3 başarılı, 2 başarısız
        for i in range(3):
            komut_repo.kaydet("s1", KomutSonucu(
                komut=Komut.FAN_BASLAT, basarili=True, mesaj="ok"
            ))
        for i in range(2):
            komut_repo.kaydet("s1", KomutSonucu(
                komut=Komut.SULAMA_BASLAT, basarili=False, mesaj="hata"
            ))
        assert komut_repo.basarisiz_sayisi("s1", son_n_dk=60) == 2
        assert komut_repo.basarisiz_sayisi("s2", son_n_dk=60) == 0

    def test_farkli_seralar_karismaz(self, komut_repo):
        komut_repo.kaydet("s1", KomutSonucu(Komut.FAN_BASLAT, True, "ok"))
        komut_repo.kaydet("s2", KomutSonucu(Komut.ISITICI_BASLAT, True, "ok"))
        assert len(komut_repo.gecmis("s1")) == 1
        assert len(komut_repo.gecmis("s2")) == 1
        assert komut_repo.gecmis("s1")[0].komut == Komut.FAN_BASLAT

    def test_tum_komutlar_kaydedilebilir(self, komut_repo):
        """Her Komut enum değeri DB'ye yazılıp geri okunabilmeli."""
        for komut in Komut:
            komut_repo.kaydet("s1", KomutSonucu(komut=komut, basarili=True, mesaj="ok"))
        gecmis = komut_repo.gecmis("s1", limit=50)
        kaydedilen = {k.komut for k in gecmis}
        assert kaydedilen == set(Komut)

    def test_ayni_db_iki_repo(self, tmp_db):
        """Sensor ve Komut repoları aynı DB dosyasını paylaşabilir."""
        s_repo = SQLiteSensorRepository(tmp_db)
        k_repo = SQLiteKomutRepository(tmp_db)
        s_repo.kaydet(
            SensorOkuma("s1", T=22.0, H=65.0, co2=850, isik=400,
                        toprak_nem=500, ph=6.3, ec=1.6)
        )
        k_repo.kaydet("s1", KomutSonucu(Komut.FAN_BASLAT, True, "ok"))
        assert s_repo.son_okuma("s1") is not None
        assert len(k_repo.gecmis("s1")) == 1
