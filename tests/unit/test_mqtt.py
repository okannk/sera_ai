"""
MQTT Altyapı Testleri

Kapsam:
  - Wildcard eşleştirme (MockMQTTBroker)
  - MockMQTTIstemci pub/sub yaşam döngüsü
  - Birden fazla istemci arası mesaj yönlendirme
  - ESP32Simulatoru sensör yayını ve ACK yanıtı
  - MQTTKomutKoprusu dis_komut → callback akışı
  - PahoMQTTIstemci yapısı (bağlantı olmadan)
  - SeraTopics topic string'leri
"""
from __future__ import annotations

import json
import pytest

from sera_ai.domain.models import BitkilProfili, Komut, SensorOkuma
from sera_ai.infrastructure.mqtt import (
    ESP32Simulatoru,
    MockMQTTBroker,
    MockMQTTIstemci,
    MQTTKomutKoprusu,
    PahoMQTTIstemci,
    SeraTopics,
)
from sera_ai.infrastructure.mqtt.mock import _wildcard_eslesir


# ── Fixture'lar ───────────────────────────────────────────────────

@pytest.fixture
def broker() -> MockMQTTBroker:
    return MockMQTTBroker()


@pytest.fixture
def istemci(broker) -> MockMQTTIstemci:
    c = MockMQTTIstemci("test_istemci", broker)
    c.baglan()
    return c


@pytest.fixture
def profil_domates() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )


@pytest.fixture
def sim(broker, profil_domates) -> ESP32Simulatoru:
    s = ESP32Simulatoru("esp32_sera_a", "s1", profil_domates, broker)
    s.baslat()
    return s


# ── Wildcard Eşleştirme ───────────────────────────────────────────

class TestWildcardEslestirme:

    def test_tam_eslesme(self):
        assert _wildcard_eslesir("sera/abc/sensor", "sera/abc/sensor")

    def test_tek_seviye_wildcard(self):
        assert _wildcard_eslesir("sera/+/sensor", "sera/esp32_a/sensor")
        assert _wildcard_eslesir("sera/+/sensor", "sera/esp32_b/sensor")

    def test_tek_seviye_wildcard_yanlış_seviye(self):
        assert not _wildcard_eslesir("sera/+/sensor", "sera/abc/komut")

    def test_cok_seviye_wildcard(self):
        assert _wildcard_eslesir("sera/#", "sera/abc/sensor")
        assert _wildcard_eslesir("sera/#", "sera/abc/sensor/extra")

    def test_farklı_uzunluklar(self):
        assert not _wildcard_eslesir("sera/+/sensor", "sera/abc")

    def test_wildcard_yok_farklı_değer(self):
        assert not _wildcard_eslesir("sera/abc/sensor", "sera/xyz/sensor")


# ── MockMQTTBroker ────────────────────────────────────────────────

class TestMockMQTTBroker:

    def test_yayinla_abone_olmayan_yok(self, broker):
        # Subscriber yoksa hata vermemeli
        broker.yayinla("sera/abc/sensor", b"veri")
        assert broker.mesaj_sayisi == 1

    def test_mesaj_aboneye_ulasir(self, broker):
        alinan = []
        c = MockMQTTIstemci("c1", broker)
        c.baglan()
        c.abone_ol("sera/s1/sensor", lambda t, p: alinan.append((t, p)))

        broker.yayinla("sera/s1/sensor", b"merhaba")
        assert len(alinan) == 1
        assert alinan[0] == ("sera/s1/sensor", b"merhaba")

    def test_gonderici_kendi_mesajini_almaz(self, broker):
        alinan = []
        c = MockMQTTIstemci("c1", broker)
        c.baglan()
        c.abone_ol("sera/s1/sensor", lambda t, p: alinan.append(p))

        # c kendisi yayınlıyor
        c.yayinla("sera/s1/sensor", "merhaba")
        assert alinan == []

    def test_wildcard_abonelik(self, broker):
        alinan = []
        c = MockMQTTIstemci("c1", broker)
        c.baglan()
        c.abone_ol("sera/+/sensor", lambda t, p: alinan.append(t))

        broker.yayinla("sera/esp32_a/sensor", b"a")
        broker.yayinla("sera/esp32_b/sensor", b"b")
        broker.yayinla("sera/esp32_a/komut", b"c")  # Eşleşmemeli

        assert len(alinan) == 2
        assert "sera/esp32_a/sensor" in alinan
        assert "sera/esp32_b/sensor" in alinan

    def test_birden_fazla_abone(self, broker):
        c1 = MockMQTTIstemci("c1", broker); c1.baglan()
        c2 = MockMQTTIstemci("c2", broker); c2.baglan()
        alinan1, alinan2 = [], []
        c1.abone_ol("test/topic", lambda t, p: alinan1.append(p))
        c2.abone_ol("test/topic", lambda t, p: alinan2.append(p))

        # c3 yayınlıyor (kaynak değil)
        c3 = MockMQTTIstemci("c3", broker); c3.baglan()
        c3.yayinla("test/topic", "x")

        assert len(alinan1) == 1
        assert len(alinan2) == 1

    def test_mesaj_gecmisi_temizle(self, broker):
        broker.yayinla("t", b"1")
        broker.yayinla("t", b"2")
        assert broker.mesaj_sayisi == 2
        broker.gecmis_temizle()
        assert broker.mesaj_sayisi == 0


# ── MockMQTTIstemci ───────────────────────────────────────────────

class TestMockMQTTIstemci:

    def test_baglan_kes(self, broker):
        c = MockMQTTIstemci("c", broker)
        assert not c.bagli_mi
        assert c.baglan()
        assert c.bagli_mi
        c.kes()
        assert not c.bagli_mi

    def test_baglanmadan_yayinla_false(self, broker):
        c = MockMQTTIstemci("c", broker)
        assert not c.yayinla("t", "x")

    def test_str_payload_encode(self, broker):
        alinan = []
        dinleyici = MockMQTTIstemci("dinleyici", broker); dinleyici.baglan()
        dinleyici.abone_ol("t", lambda _, p: alinan.append(p))

        yayinci = MockMQTTIstemci("yayinci", broker); yayinci.baglan()
        yayinci.yayinla("t", "merhaba")

        assert alinan == [b"merhaba"]

    def test_abonelikten_cik(self, broker):
        alinan = []
        c = MockMQTTIstemci("c", broker); c.baglan()
        c.abone_ol("t", lambda _, p: alinan.append(p))
        c.abonelikten_cik("t")

        broker.yayinla("t", b"x")
        assert alinan == []

    def test_kes_abonelikleri_temizler(self, broker):
        alinan = []
        c = MockMQTTIstemci("c", broker); c.baglan()
        c.abone_ol("t", lambda _, p: alinan.append(p))
        c.kes()

        broker.yayinla("t", b"x")
        assert alinan == []


# ── ESP32Simulatoru ───────────────────────────────────────────────

class TestESP32Simulatoru:

    def test_veri_gonder_json_gecerli(self, sim, broker, profil_domates):
        alinan = []
        topics = SeraTopics("esp32_sera_a")

        dinleyici = MockMQTTIstemci("merkez", broker)
        dinleyici.baglan()
        dinleyici.abone_ol(topics.sensor, lambda t, p: alinan.append(p))

        sim.veri_gonder()

        assert len(alinan) == 1
        veri = json.loads(alinan[0].decode())
        assert "T" in veri and "H" in veri and "co2" in veri

    def test_veri_fiziksel_sinirlar(self, sim, broker):
        alinan = []
        topics = SeraTopics("esp32_sera_a")
        dinleyici = MockMQTTIstemci("merkez", broker); dinleyici.baglan()
        dinleyici.abone_ol(topics.sensor, lambda t, p: alinan.append(p))

        for _ in range(10):
            sim.veri_gonder()

        for raw in alinan:
            v = json.loads(raw.decode())
            assert 5 <= v["T"] <= 45
            assert 20 <= v["H"] <= 98
            assert 300 <= v["co2"] <= 2000

    def test_komut_gonder_ack_ok(self, sim, broker):
        topics = SeraTopics("esp32_sera_a")
        ackler = []

        dinleyici = MockMQTTIstemci("merkez", broker); dinleyici.baglan()
        dinleyici.abone_ol(topics.ack, lambda t, p: ackler.append(p.decode()))

        # Merkez → ESP32 komut yayınlıyor
        dinleyici.yayinla(topics.komut, Komut.FAN_BASLAT.value)

        assert len(ackler) == 1
        assert ackler[0] == "OK"
        assert sim.alinan_komut_sayisi == 1

    def test_bilinmeyen_komut_err_ack(self, sim, broker):
        topics = SeraTopics("esp32_sera_a")
        ackler = []
        dinleyici = MockMQTTIstemci("merkez", broker); dinleyici.baglan()
        dinleyici.abone_ol(topics.ack, lambda t, p: ackler.append(p.decode()))

        dinleyici.yayinla(topics.komut, "BILINMEYEN_KOMUT")

        assert ackler[0].startswith("ERR:")

    def test_tum_komutlar_ack_ok(self, sim, broker):
        topics = SeraTopics("esp32_sera_a")
        ackler = []
        dinleyici = MockMQTTIstemci("merkez", broker); dinleyici.baglan()
        dinleyici.abone_ol(topics.ack, lambda t, p: ackler.append(p.decode()))

        for komut in Komut:
            dinleyici.yayinla(topics.komut, komut.value)

        assert all(a == "OK" for a in ackler)
        assert len(ackler) == len(list(Komut))

    def test_gonderilen_veri_sayaci(self, sim):
        assert sim.gonderilen_veri_sayisi == 0
        sim.veri_gonder()
        sim.veri_gonder()
        assert sim.gonderilen_veri_sayisi == 2

    def test_durdur_sonrasi_yayinlamaz(self, broker, profil_domates):
        alinan = []
        sim2 = ESP32Simulatoru("esp32_b", "s2", profil_domates, broker)
        sim2.baslat()

        dinleyici = MockMQTTIstemci("merkez", broker); dinleyici.baglan()
        dinleyici.abone_ol("sera/esp32_b/sensor", lambda t, p: alinan.append(p))

        sim2.durdur()
        sim2.veri_gonder()  # Kesildi — mesaj ulaşmamalı
        assert alinan == []


# ── MQTTKomutKoprusu ─────────────────────────────────────────────

class TestMQTTKomutKoprusu:

    def test_dis_komut_callback_cagrilir(self, broker):
        alinan = []
        istemci = MockMQTTIstemci("merkez", broker); istemci.baglan()

        kopru = MQTTKomutKoprusu(
            istemci=istemci,
            node_sera_haritasi={"esp32_sera_a": "s1"},
            on_komut=lambda sera_id, komut: alinan.append((sera_id, komut)),
        )
        kopru.baslat()

        # Dashboard → dis_komut topic'ine yazar
        dis = MockMQTTIstemci("dashboard", broker); dis.baglan()
        dis.yayinla("sera/esp32_sera_a/dis_komut", Komut.SULAMA_BASLAT.value)

        assert len(alinan) == 1
        assert alinan[0] == ("s1", Komut.SULAMA_BASLAT)

    def test_bilinmeyen_node_yoksayilir(self, broker):
        alinan = []
        istemci = MockMQTTIstemci("merkez", broker); istemci.baglan()

        kopru = MQTTKomutKoprusu(
            istemci=istemci,
            node_sera_haritasi={"esp32_sera_a": "s1"},
            on_komut=lambda s, k: alinan.append((s, k)),
        )
        kopru.baslat()

        dis = MockMQTTIstemci("dashboard", broker); dis.baglan()
        dis.yayinla("sera/esp32_bilinmeyen/dis_komut", Komut.FAN_BASLAT.value)

        assert alinan == []

    def test_gecersiz_komut_yoksayilir(self, broker):
        alinan = []
        istemci = MockMQTTIstemci("merkez", broker); istemci.baglan()

        kopru = MQTTKomutKoprusu(
            istemci=istemci,
            node_sera_haritasi={"esp32_sera_a": "s1"},
            on_komut=lambda s, k: alinan.append((s, k)),
        )
        kopru.baslat()

        dis = MockMQTTIstemci("dashboard", broker); dis.baglan()
        dis.yayinla("sera/esp32_sera_a/dis_komut", "YANLIS_KOMUT")

        assert alinan == []

    def test_durdur_sonrasi_mesaj_almaz(self, broker):
        alinan = []
        istemci = MockMQTTIstemci("merkez", broker); istemci.baglan()

        kopru = MQTTKomutKoprusu(
            istemci=istemci,
            node_sera_haritasi={"esp32_sera_a": "s1"},
            on_komut=lambda s, k: alinan.append((s, k)),
        )
        kopru.baslat()
        kopru.durdur()

        dis = MockMQTTIstemci("dashboard", broker); dis.baglan()
        dis.yayinla("sera/esp32_sera_a/dis_komut", Komut.FAN_BASLAT.value)

        assert alinan == []


# ── SeraTopics ────────────────────────────────────────────────────

class TestSeraTopics:

    def test_topic_format(self):
        t = SeraTopics("esp32_sera_a")
        assert t.sensor    == "sera/esp32_sera_a/sensor"
        assert t.komut     == "sera/esp32_sera_a/komut"
        assert t.ack       == "sera/esp32_sera_a/ack"
        assert t.durum     == "sera/esp32_sera_a/durum"
        assert t.dis_komut == "sera/esp32_sera_a/dis_komut"

    def test_node_id_cozumle(self):
        assert SeraTopics.node_id_cozumle("sera/esp32_b/sensor") == "esp32_b"

    def test_node_id_cozumle_gecersiz(self):
        with pytest.raises(ValueError):
            SeraTopics.node_id_cozumle("kisa")


# ── PahoMQTTIstemci Yapı Testleri ────────────────────────────────

class TestPahoMQTTIstemciYapi:
    """Gerçek broker olmadan sadece sınıf yapısını test eder."""

    def test_baslangiçta_bagli_degil(self):
        c = PahoMQTTIstemci("test", "localhost", 1883)
        assert not c.bagli_mi

    def test_baglanmadan_yayinla_false(self):
        c = PahoMQTTIstemci("test", "localhost", 1883)
        assert not c.yayinla("t", "x")

    def test_abc_uyum(self):
        from sera_ai.infrastructure.mqtt.base import MQTTIstemciBase
        assert issubclass(PahoMQTTIstemci, MQTTIstemciBase)

    def test_mock_da_abc_uyum(self):
        from sera_ai.infrastructure.mqtt.base import MQTTIstemciBase
        assert issubclass(MockMQTTIstemci, MQTTIstemciBase)
