"""
Loglama Altyapısı Testleri

Kapsam:
  - LogKayit.to_dict() formatı
  - JSONLLogger yazma / okuma / temizle
  - LokiLogger buffer / payload formatı
  - MockLogger filtreleme
  - LogDispatcher EventBus aboneliği ve seviye eşlemesi
  - /metrics endpoint Prometheus formatı
"""
from __future__ import annotations

import json
import tempfile
import os
from datetime import datetime
from pathlib import Path

import pytest

from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.infrastructure.logging import (
    JSONLLogger,
    LogDispatcher,
    LogKayit,
    LogSeviye,
    LokiLogger,
    MockLogger,
)


# ── LogKayit ─────────────────────────────────────────────────────

class TestLogKayit:

    def test_to_dict_zorunlu_alanlar(self):
        k = LogKayit(LogSeviye.INFO, "DURUM_DEGISTI", {"yeni": "ALARM"}, "s1")
        d = k.to_dict()
        assert "ts" in d
        assert d["seviye"]  == "INFO"
        assert d["olay"]    == "DURUM_DEGISTI"
        assert d["sera_id"] == "s1"
        assert d["yeni"]    == "ALARM"

    def test_to_dict_json_serializeable(self):
        k = LogKayit(LogSeviye.HATA, "CB_ACILDI", {"hata": "timeout"}, "s2")
        d = k.to_dict()
        json.dumps(d)  # istisna fırlatmamalı

    def test_varsayilan_zaman(self):
        k = LogKayit(LogSeviye.DEBUG, "TEST")
        assert isinstance(k.zaman, datetime)


# ── JSONLLogger ───────────────────────────────────────────────────

class TestJSONLLogger:

    def test_kayit_yazar_ve_okur(self, tmp_path):
        logger = JSONLLogger(str(tmp_path / "test.jsonl"))
        k = LogKayit(LogSeviye.INFO, "DURUM_DEGISTI", {"yeni": "ALARM"}, "s1")
        logger.yaz(k)
        satirlar = logger.satirlari_oku()
        assert len(satirlar) == 1
        assert satirlar[0]["seviye"] == "INFO"
        assert satirlar[0]["olay"]   == "DURUM_DEGISTI"

    def test_birden_fazla_kayit(self, tmp_path):
        logger = JSONLLogger(str(tmp_path / "test.jsonl"))
        for i in range(5):
            logger.yaz(LogKayit(LogSeviye.INFO, f"OLAY_{i}"))
        assert len(logger.satirlari_oku()) == 5

    def test_gecerli_json_her_satir(self, tmp_path):
        yol = tmp_path / "test.jsonl"
        logger = JSONLLogger(str(yol))
        logger.yaz(LogKayit(LogSeviye.UYARI, "TEST", {"msg": "merhaba dünya"}, "s1"))
        with open(yol) as f:
            for satir in f:
                json.loads(satir)  # parse edilebilmeli

    def test_temizle(self, tmp_path):
        logger = JSONLLogger(str(tmp_path / "test.jsonl"))
        logger.yaz(LogKayit(LogSeviye.INFO, "X"))
        logger.temizle()
        assert logger.satirlari_oku() == []

    def test_dosya_yoksa_bos_liste(self, tmp_path):
        logger = JSONLLogger(str(tmp_path / "yok.jsonl"))
        assert logger.satirlari_oku() == []

    def test_thread_safe_coklu_yazma(self, tmp_path):
        import threading
        logger = JSONLLogger(str(tmp_path / "test.jsonl"))
        def yaz_10():
            for _ in range(10):
                logger.yaz(LogKayit(LogSeviye.DEBUG, "T"))
        threadler = [threading.Thread(target=yaz_10) for _ in range(5)]
        for t in threadler: t.start()
        for t in threadler: t.join()
        satirlar = logger.satirlari_oku()
        assert len(satirlar) == 50


# ── LokiLogger ────────────────────────────────────────────────────

class TestLokiLogger:

    def test_buffer_biriktirir(self):
        logger = LokiLogger(buffer_boyut=10, aktif=True)
        for i in range(5):
            logger.yaz(LogKayit(LogSeviye.INFO, f"OLAY_{i}", sera_id="s1"))
        assert logger.buffer_boyutu() == 5

    def test_buffer_dolunca_flush_tetiklenir(self):
        """Buffer dolarsa otomatik flush → buffer sıfırlanır.
        Loki'ye bağlanamayacak (test ortamı) ama buffer temizlenmeli."""
        logger = LokiLogger(loki_url="http://localhost:19999", buffer_boyut=3, aktif=True)
        for i in range(3):
            logger.yaz(LogKayit(LogSeviye.INFO, f"OLAY_{i}"))
        # Flush denenmiş → başarısız ama buffer temizlenmiş
        assert logger.buffer_boyutu() == 0

    def test_aktif_false_yaz_etki_etmez(self):
        logger = LokiLogger(aktif=False)
        logger.yaz(LogKayit(LogSeviye.INFO, "TEST"))
        assert logger.buffer_boyutu() == 0

    def test_payload_format_dogru(self):
        logger = LokiLogger(is_etiketi="sera_ai", aktif=True)
        kayitlar = [
            LogKayit(LogSeviye.INFO,  "DURUM_DEGISTI", sera_id="s1"),
            LogKayit(LogSeviye.HATA,  "CB_ACILDI",     sera_id="s1"),
            LogKayit(LogSeviye.UYARI, "SISTEM_HATASI", sera_id="s2"),
        ]
        payload = logger._payload_olustur(kayitlar)
        assert "streams" in payload
        assert len(payload["streams"]) >= 2  # Farklı (seviye, sera) kombinasyonları

        for stream in payload["streams"]:
            assert "stream" in stream
            assert "values" in stream
            assert stream["stream"]["job"] == "sera_ai"
            for ts_ns, satir in stream["values"]:
                int(ts_ns)          # Nanosecond integer string
                json.loads(satir)   # Geçerli JSON

    def test_payload_sera_id_etiketi(self):
        logger = LokiLogger(aktif=True)
        kayitlar = [LogKayit(LogSeviye.INFO, "X", sera_id="s1")]
        payload = logger._payload_olustur(kayitlar)
        assert payload["streams"][0]["stream"]["sera_id"] == "s1"

    def test_sera_id_bos_sistem_olur(self):
        logger = LokiLogger(aktif=True)
        kayitlar = [LogKayit(LogSeviye.INFO, "X", sera_id="")]
        payload = logger._payload_olustur(kayitlar)
        assert payload["streams"][0]["stream"]["sera_id"] == "sistem"


# ── MockLogger ────────────────────────────────────────────────────

class TestMockLogger:

    def test_kayit_ekler(self):
        logger = MockLogger()
        k = LogKayit(LogSeviye.ALARM if hasattr(LogSeviye, 'ALARM') else LogSeviye.HATA, "X")
        logger.yaz(LogKayit(LogSeviye.HATA, "X"))
        assert len(logger.kayitlar) == 1

    def test_temizle(self):
        logger = MockLogger()
        logger.yaz(LogKayit(LogSeviye.INFO, "X"))
        logger.temizle()
        assert logger.kayitlar == []

    def test_seviyeye_gore_filtrele(self):
        logger = MockLogger()
        logger.yaz(LogKayit(LogSeviye.INFO,  "A"))
        logger.yaz(LogKayit(LogSeviye.HATA,  "B"))
        logger.yaz(LogKayit(LogSeviye.UYARI, "C"))
        hatalar = logger.seviyeye_gore_filtrele(LogSeviye.HATA)
        assert len(hatalar) == 1
        assert hatalar[0].olay == "B"

    def test_olaya_gore_filtrele(self):
        logger = MockLogger()
        logger.yaz(LogKayit(LogSeviye.INFO, "DURUM_DEGISTI"))
        logger.yaz(LogKayit(LogSeviye.INFO, "CB_ACILDI"))
        logger.yaz(LogKayit(LogSeviye.INFO, "DURUM_DEGISTI"))
        assert len(logger.olaya_gore_filtrele("DURUM_DEGISTI")) == 2


# ── LogDispatcher ─────────────────────────────────────────────────

class TestLogDispatcher:

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def mock_log(self):
        return MockLogger()

    @pytest.fixture
    def dispatcher(self, bus, mock_log):
        d = LogDispatcher([mock_log], bus)
        d.baslat()
        return d

    def test_baslat_abone_olur(self, bus, dispatcher):
        assert bus.abone_sayisi(OlayTur.DURUM_DEGISTI) >= 1
        assert bus.abone_sayisi(OlayTur.CB_ACILDI)     >= 1
        assert bus.abone_sayisi(OlayTur.SISTEM_HATASI)  >= 1

    def test_durum_degisti_info_yazar(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "NORMAL"
        })
        assert len(mock_log.kayitlar) == 1
        assert mock_log.kayitlar[0].seviye == LogSeviye.INFO

    def test_alarm_durumu_hata_seviyesi(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "UYARI", "yeni": "ALARM"
        })
        assert mock_log.kayitlar[0].seviye == LogSeviye.HATA

    def test_acil_durdur_kritik_seviyesi(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "ALARM", "yeni": "ACIL_DURDUR"
        })
        assert mock_log.kayitlar[0].seviye == LogSeviye.KRITIK

    def test_cb_acildi_hata_seviyesi(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s1"})
        assert mock_log.kayitlar[0].seviye == LogSeviye.HATA
        assert mock_log.kayitlar[0].olay   == "CB_ACILDI"

    def test_komut_gonderildi_info(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.KOMUT_GONDERILDI, {
            "sera_id": "s1", "komut": "FAN_AC", "basarili": True
        })
        assert mock_log.kayitlar[0].seviye == LogSeviye.INFO

    def test_sistem_hatasi_hata_seviyesi(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.SISTEM_HATASI, {
            "sera_id": "s1", "hata": "Timeout"
        })
        assert mock_log.kayitlar[0].seviye == LogSeviye.HATA

    def test_sensor_log_varsayilan_kapali(self, bus, mock_log, dispatcher):
        """SENSOR_OKUMA varsayılan olarak loglanmaz."""
        bus.yayinla(OlayTur.SENSOR_OKUMA, {"sera_id": "s1"})
        assert mock_log.kayitlar == []

    def test_sensor_log_aktif_edilince_yazar(self, bus):
        mock_log = MockLogger()
        d = LogDispatcher([mock_log], bus, sensor_log_aktif=True)
        d.baslat()
        bus.yayinla(OlayTur.SENSOR_OKUMA, {"sera_id": "s1", "T": 23.0})
        assert len(mock_log.kayitlar) == 1
        assert mock_log.kayitlar[0].seviye == LogSeviye.DEBUG

    def test_sera_id_kayita_yazilir(self, bus, mock_log, dispatcher):
        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s2"})
        assert mock_log.kayitlar[0].sera_id == "s2"

    def test_birden_fazla_yazici(self, bus):
        log1 = MockLogger()
        log2 = MockLogger()
        d = LogDispatcher([log1, log2], bus)
        d.baslat()
        bus.yayinla(OlayTur.DURUM_DEGISTI, {
            "sera_id": "s1", "eski": "NORMAL", "yeni": "ALARM"
        })
        assert len(log1.kayitlar) == 1
        assert len(log2.kayitlar) == 1


# ── /metrics Endpoint ─────────────────────────────────────────────

class TestMetricsEndpoint:

    @pytest.fixture
    def client(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from sera_ai.api.app import api_uygulamasi_olustur
        app = api_uygulamasi_olustur(api_key="")
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_200(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_content_type_prometheus(self, client):
        r = client.get("/metrics")
        assert "text/plain" in r.headers["content-type"]

    def test_help_satirlari_var(self, client):
        metin = client.get("/metrics").text
        assert "# HELP" in metin
        assert "# TYPE" in metin

    def test_sera_sicaklik_metrik_var(self, client):
        metin = client.get("/metrics").text
        assert "sera_sicaklik_celsius" in metin

    def test_sera_nem_metrik_var(self, client):
        metin = client.get("/metrics").text
        assert "sera_nem_yuzde" in metin

    def test_sera_co2_metrik_var(self, client):
        metin = client.get("/metrics").text
        assert "sera_co2_ppm" in metin

    def test_sera_durum_kodu_var(self, client):
        metin = client.get("/metrics").text
        assert "sera_durum_kodu" in metin

    def test_sistem_uptime_var(self, client):
        metin = client.get("/metrics").text
        assert "sistem_uptime_saniye" in metin

    def test_metrics_auth_gerektirmez(self):
        """Auth aktifken bile /metrics açık olmalı."""
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from sera_ai.api.app import api_uygulamasi_olustur
        app = api_uygulamasi_olustur(api_key="gizli_anahtar")
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/metrics")
        assert r.status_code == 200

    def test_her_sera_etiketlendi(self, client):
        """s1, s2, s3 seraları metriklerde görünmeli."""
        metin = client.get("/metrics").text
        assert 'sera_id="s1"' in metin
        assert 'sera_id="s2"' in metin
        assert 'sera_id="s3"' in metin
