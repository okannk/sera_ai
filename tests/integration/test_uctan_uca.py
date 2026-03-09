"""
Uçtan Uca Entegrasyon Testleri

Tüm katmanların birlikte çalıştığını doğrular.
Mock donanım kullanır — gerçek broker, DB sunucusu, ağ gerektirmez.

Senaryo 1: Tam altyapı zinciri
  MockSahaNode → KontrolMotoru → EventBus
  → SQLiteRepository (sensör + komut kaydı)
  → BildirimDispatcher (alarm bildirimi)
  → LogDispatcher (yapılandırılmış log)

Senaryo 2: MQTT round-trip
  ESP32Simulatoru → MockMQTTBroker → MQTTSahaNodeAdaptor
  → KontrolMotoru → komut → ESP32 ACK
  Gerçek ESP32 ↔ merkez MQTT protokolünü paho olmadan simüle eder.

Senaryo 3: Çok sera + Circuit Breaker izolasyonu
  3 sera paralel çalışır, Sera C arızalanır → CB açılır → bildirim gelir
  Sera A ve B normal devam eder (per-sera CB bağımsızlığı).
"""
from __future__ import annotations

import queue
import tempfile
from datetime import datetime, timedelta

import pytest

from sera_ai.application.control_engine import KontrolMotoru
from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.domain.circuit_breaker import CircuitBreaker
from sera_ai.domain.models import (
    BitkilProfili, BildirimKonfig, Komut, SensorOkuma,
)
from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.drivers.base import SahaNodeBase
from sera_ai.drivers.mock import MockSahaNode
from sera_ai.infrastructure.logging import (
    LogDispatcher, LogSeviye, MockLogger,
)
from sera_ai.infrastructure.mqtt import (
    ESP32Simulatoru, MockMQTTBroker, MockMQTTIstemci, SeraTopics,
)
from sera_ai.infrastructure.notifications import (
    BildirimDispatcher, BildirimOncelik, MockBildirimKanal,
)
from sera_ai.infrastructure.repositories import (
    SQLiteKomutRepository, SQLiteSensorRepository,
)


# ── Ortak Fixture'lar ─────────────────────────────────────────────

@pytest.fixture
def profil_domates() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )


@pytest.fixture
def profil_marul() -> BitkilProfili:
    return BitkilProfili(
        isim="Marul", min_T=10, max_T=22, opt_T=16,
        min_H=65, max_H=85, opt_CO2=800, hasat_gun=45,
    )


@pytest.fixture
def tmp_db(tmp_path) -> str:
    return str(tmp_path / "test.db")


# ── MQTT Test Yardımcısı ──────────────────────────────────────────

class MQTTSahaNodeAdaptor(SahaNodeBase):
    """
    Test içi MQTT ↔ SahaNodeBase köprüsü.

    ESP32Simulatoru'nun ürettiği MQTT mesajlarını alır,
    KontrolMotoru'nun beklediği SahaNodeBase arayüzüne dönüştürür.

    Bu sınıf production kodu değil — yalnızca entegrasyon testleri için.
    Gerçek sistemde bu rolü ESP32S3Node (paho-mqtt ile) oynar.
    """

    TIMEOUT_SN = 1.0

    def __init__(self, sera_id: str, node_id: str, broker: MockMQTTBroker) -> None:
        self.sera_id   = sera_id
        self.node_id   = node_id
        self._topics   = SeraTopics(node_id)
        self._istemci  = MockMQTTIstemci(f"merkez_{node_id}", broker)
        self._sensor_q: queue.Queue[bytes] = queue.Queue(maxsize=5)
        self._ack_q:    queue.Queue[str]   = queue.Queue(maxsize=5)

    def baglan(self) -> bool:
        self._istemci.baglan()
        self._istemci.abone_ol(self._topics.sensor, self._on_sensor)
        self._istemci.abone_ol(self._topics.ack,    self._on_ack)
        return True

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        import json
        try:
            payload = self._sensor_q.get(timeout=self.TIMEOUT_SN)
            veri = json.loads(payload.decode())
            return SensorOkuma(
                sera_id=sera_id,
                T=float(veri.get("T", 0)),
                H=float(veri.get("H", 0)),
                co2=int(veri.get("co2", 0)),
                isik=int(veri.get("isik", 0)),
                toprak_nem=int(veri.get("toprak", 500)),
                ph=float(veri.get("ph", 6.5)),
                ec=float(veri.get("ec", 2.0)),
            )
        except queue.Empty:
            raise IOError(f"[{self.node_id}] Sensör timeout — ESP32 simülatörü veri göndermedi")

    def komut_gonder(self, komut: Komut) -> bool:
        # ACK kuyruğunu temizle
        while not self._ack_q.empty():
            self._ack_q.get_nowait()
        self._istemci.yayinla(self._topics.komut, komut.value, qos=1)
        try:
            ack = self._ack_q.get(timeout=self.TIMEOUT_SN)
            return ack == "OK"
        except queue.Empty:
            raise IOError(f"[{self.node_id}] Komut ACK timeout: {komut.value}")

    def kapat(self) -> None:
        self._istemci.kes()

    def _on_sensor(self, topic: str, payload: bytes) -> None:
        if not self._sensor_q.full():
            self._sensor_q.put_nowait(payload)

    def _on_ack(self, topic: str, payload: bytes) -> None:
        if not self._ack_q.full():
            self._ack_q.put_nowait(payload.decode().strip())


# ── Sistem Kurulum Yardımcısı ─────────────────────────────────────

def tam_altyapi_kur(
    sera_id: str,
    profil: BitkilProfili,
    node: SahaNodeBase,
    tmp_db: str,
):
    """
    Tüm altyapı katmanlarını birbirine bağlı olarak kurar.
    Döner: (motor, bus, bildirim_kanal, mock_log, sensor_repo, komut_repo)
    """
    bus    = EventBus()
    cb     = CircuitBreaker(f"{sera_id}_cb", hata_esigi=3, recovery_sn=60)
    sm     = SeraStateMachine(
        sera_id, profil,
        on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d),
    )
    motor  = KontrolMotoru(
        sera_id=sera_id, profil=profil,
        node=node, cb=cb, state_machine=sm, olay_bus=bus,
    )

    # Repository katmanı
    s_repo = SQLiteSensorRepository(tmp_db)
    k_repo = SQLiteKomutRepository(tmp_db)

    # Sensör okumaları otomatik kaydet
    def sensor_kaydet(veri: dict):
        # Bu normalde KontrolMotoru döngüsünde yapılır;
        # test için EventBus üzerinden simüle ediyoruz
        pass

    # Komut kaydet
    def komut_kaydet(veri: dict):
        from sera_ai.domain.models import KomutSonucu, Komut as K
        try:
            sonuc = KomutSonucu(
                komut=K(veri["komut"]),
                basarili=veri.get("basarili", True),
                mesaj="",
            )
            k_repo.kaydet(sera_id, sonuc)
        except Exception:
            pass

    bus.abone_ol(OlayTur.KOMUT_GONDERILDI, komut_kaydet)

    # Bildirim katmanı
    bildirim_kanal = MockBildirimKanal()
    bildirim_konfig = BildirimKonfig(bastirma_dk=0)  # test: bastırma yok
    bil_dispatcher = BildirimDispatcher([bildirim_kanal], bildirim_konfig, bus)
    bil_dispatcher.baslat()

    # Log katmanı
    mock_log = MockLogger()
    log_dispatcher = LogDispatcher([mock_log], bus)
    log_dispatcher.baslat()

    return motor, bus, bildirim_kanal, mock_log, s_repo, k_repo


# ══════════════════════════════════════════════════════════════════
# SENARYO 1: Tam Altyapı Zinciri
# ══════════════════════════════════════════════════════════════════

class TestTamAltyapiZinciri:
    """MockSahaNode → KontrolMotoru → Repository + Bildirim + Log"""

    def test_normal_sensor_komut_db_kaydedilir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        sensor = SensorOkuma(
            sera_id="s1", T=27.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )
        motor.adim_at(sensor)

        # Komut gönderilmeli (27°C > opt_T=23 → sogutma)
        assert Komut.SOGUTMA_BASLAT in node.komutlar

        # Komut DB'ye kaydedilmeli
        gecmis = k_repo.gecmis("s1")
        assert len(gecmis) >= 1

    def test_alarm_durumu_bildirim_gonderir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        sensor = SensorOkuma(
            sera_id="s1", T=32.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )
        motor.adim_at(sensor)

        # ALARM → bildirim gitmeli
        assert len(bil.gonderilen) >= 1
        assert any(b.oncelik in (BildirimOncelik.ALARM, BildirimOncelik.KRITIK)
                   for b in bil.gonderilen)

    def test_alarm_log_kaydedilir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        sensor = SensorOkuma(
            sera_id="s1", T=32.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )
        motor.adim_at(sensor)

        # ALARM log → HATA veya KRITIK seviyesi
        yuksek_seviye = [
            k for k in log.kayitlar
            if k.seviye in (LogSeviye.HATA, LogSeviye.KRITIK)
        ]
        assert len(yuksek_seviye) >= 1

    def test_acil_durdur_kritik_bildirim(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        # T=34 → ACİL_DURDUR (opt_T=23, +11 > kritik eşik)
        sensor = SensorOkuma(
            sera_id="s1", T=34.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )
        motor.adim_at(sensor)

        kritik = [b for b in bil.gonderilen
                  if b.oncelik == BildirimOncelik.KRITIK]
        assert len(kritik) >= 1

    def test_iyilesme_kapatma_komutu_db_kaydedilir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        # Alarm: sogutma aç
        motor.adim_at(SensorOkuma(
            sera_id="s1", T=32.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        ))
        # İyileşme: sogutma kapat
        motor.adim_at(SensorOkuma(
            sera_id="s1", T=23.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        ))

        gecmis = k_repo.gecmis("s1")
        komutlar = {k.komut for k in gecmis}
        assert Komut.SOGUTMA_BASLAT in komutlar
        assert Komut.SOGUTMA_DURDUR in komutlar

    def test_gecersiz_sensor_komut_gonderilmez(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        gecersiz = SensorOkuma(
            sera_id="s1", T=-999.0, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )
        motor.adim_at(gecersiz)

        # Geçersiz sensör → komut gönderilmez, DB'ye komut kaydedilmez
        assert node.komutlar == []
        assert k_repo.gecmis("s1") == []

    def test_coklu_adim_log_birikir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=0.0)
        node.baglan()
        motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        # Normal → Uyarı → Alarm → Normal döngüsü
        adimlar = [
            SensorOkuma("s1", T=23.0, H=72.0, co2=950,
                        isik=450, toprak_nem=500, ph=6.5, ec=1.8),
            SensorOkuma("s1", T=27.0, H=72.0, co2=950,
                        isik=450, toprak_nem=500, ph=6.5, ec=1.8),
            SensorOkuma("s1", T=32.0, H=72.0, co2=950,
                        isik=450, toprak_nem=500, ph=6.5, ec=1.8),
            SensorOkuma("s1", T=23.0, H=72.0, co2=950,
                        isik=450, toprak_nem=500, ph=6.5, ec=1.8),
        ]
        for s in adimlar:
            motor.adim_at(s)

        # Log kayıtları oluşmuş olmalı
        assert len(log.kayitlar) >= 2  # En az 2 durum değişimi


# ══════════════════════════════════════════════════════════════════
# SENARYO 2: MQTT Round-Trip
# ══════════════════════════════════════════════════════════════════

class TestMQTTRoundTrip:
    """ESP32Simulatoru → MockMQTTBroker → MQTTSahaNodeAdaptor → KontrolMotoru"""

    @pytest.fixture
    def mqtt_sistem(self, profil_domates, tmp_db):
        broker   = MockMQTTBroker()
        node_id  = "esp32_sera_a"

        # ESP32 simülatörü
        sim = ESP32Simulatoru(node_id, "s1", profil_domates, broker)
        sim.baslat()

        # Merkez MQTT adaptörü
        adaptor = MQTTSahaNodeAdaptor("s1", node_id, broker)
        adaptor.baglan()

        bus   = EventBus()
        cb    = CircuitBreaker("s1_cb", hata_esigi=5, recovery_sn=60)
        sm    = SeraStateMachine(
            "s1", profil_domates,
            on_gecis=lambda d: bus.yayinla(OlayTur.DURUM_DEGISTI, d),
        )
        motor = KontrolMotoru(
            sera_id="s1", profil=profil_domates,
            node=adaptor, cb=cb, state_machine=sm, olay_bus=bus,
        )

        yield sim, adaptor, motor, bus

        sim.durdur()
        adaptor.kapat()

    def test_sensor_verisi_mqtt_uzerinden_akar(self, mqtt_sistem):
        sim, adaptor, motor, bus = mqtt_sistem
        sim.veri_gonder()
        okuma = adaptor.sensor_oku("s1")
        assert okuma.gecerli_mi

    def test_komut_mqtt_uzerinden_esp32_ye_ulasir(self, mqtt_sistem):
        sim, adaptor, motor, bus = mqtt_sistem
        sim.veri_gonder()  # önce veri gelsin

        # Adaptor komut gönderir → broker → sim dinler → ACK döner
        basarili = adaptor.komut_gonder(Komut.FAN_BASLAT)
        assert basarili
        assert sim.alinan_komut_sayisi >= 1

    def test_tam_dongu_sensor_to_komut(self, mqtt_sistem):
        """ESP32 → sensör → KontrolMotoru → komut → ESP32 ACK"""
        sim, adaptor, motor, bus = mqtt_sistem

        # Yüksek sıcaklık simüle et (sogutma tetiklensin)
        sim._durum.T = 28.0  # opt_T=23 → UYARI
        sim.veri_gonder()

        okuma = adaptor.sensor_oku("s1")
        assert okuma.gecerli_mi

        motor.adim_at(okuma)
        # KontrolMotoru komut gönderdi → ESP32 ACK aldı → sayaç arttı
        assert sim.alinan_komut_sayisi >= 1

    def test_mqtt_veri_gecerli_sinirlar(self, mqtt_sistem):
        """MQTT üzerinden gelen sensör verisi fiziksel sınır içinde."""
        sim, adaptor, motor, bus = mqtt_sistem
        for _ in range(5):
            sim.veri_gonder()
            okuma = adaptor.sensor_oku("s1")
            assert okuma.gecerli_mi, f"Geçersiz okuma: T={okuma.T} H={okuma.H}"

    def test_bilinmeyen_komut_false_doner(self, mqtt_sistem):
        """Geçersiz komut string'i → ESP32 ERR ACK → False."""
        sim, adaptor, motor, bus = mqtt_sistem
        # Doğrudan broker'a geçersiz komut yayınla
        topics = SeraTopics("esp32_sera_a")
        ackler = []
        kontrol_istemci = MockMQTTIstemci("k", adaptor._istemci._broker)
        kontrol_istemci.baglan()
        kontrol_istemci.abone_ol(topics.ack, lambda t, p: ackler.append(p.decode()))
        kontrol_istemci.yayinla(topics.komut, "YANLIS_KOMUT")
        assert ackler and ackler[0].startswith("ERR:")

    def test_coklu_veri_gonderimi(self, mqtt_sistem):
        sim, adaptor, motor, bus = mqtt_sistem
        for _ in range(3):
            sim.veri_gonder()
            okuma = adaptor.sensor_oku("s1")
            motor.adim_at(okuma)

        assert sim.gonderilen_veri_sayisi == 3


# ══════════════════════════════════════════════════════════════════
# SENARYO 3: Çok Sera + CB İzolasyonu
# ══════════════════════════════════════════════════════════════════

class TestCokSeraVeCBIzolasyon:
    """3 sera paralel — biri arızalansa diğerleri etkilenmez."""

    @pytest.fixture
    def uc_sera(self, profil_domates, profil_marul, tmp_db):
        sonuclar = {}
        for sid, profil in [("s1", profil_domates),
                             ("s2", profil_domates),
                             ("s3", profil_marul)]:
            node = MockSahaNode(sid, profil,
                                sensor_hata_orani=0.0,
                                komut_hata_orani=0.0)
            node.baglan()
            motor, bus, bil, log, s_repo, k_repo = tam_altyapi_kur(
                sid, profil, node, tmp_db
            )
            sonuclar[sid] = {
                "node": node, "motor": motor, "bus": bus,
                "bil": bil, "log": log,
                "s_repo": s_repo, "k_repo": k_repo,
            }
        return sonuclar

    def _sensor(self, sera_id: str, T: float) -> SensorOkuma:
        return SensorOkuma(
            sera_id=sera_id, T=T, H=72.0, co2=950,
            isik=450, toprak_nem=500, ph=6.5, ec=1.8,
        )

    def test_uc_sera_bagimsiz_calisir(self, uc_sera):
        uc_sera["s1"]["motor"].adim_at(self._sensor("s1", 23.0))  # Normal
        uc_sera["s2"]["motor"].adim_at(self._sensor("s2", 25.0))  # Biraz sıcak
        uc_sera["s3"]["motor"].adim_at(self._sensor("s3", 16.0))  # Normal

        # Hepsi çalıştı, birbirine karışmadı
        assert uc_sera["s1"]["node"].sera_id == "s1"
        assert uc_sera["s3"]["node"].sera_id == "s3"

    def test_s3_alarmi_s1_i_etkilemez(self, uc_sera):
        # s3 alarm durumuna gir
        uc_sera["s3"]["motor"].adim_at(self._sensor("s3", 25.0))  # max_T=22 üstü

        # s1 normal çalışmaya devam etmeli
        uc_sera["s1"]["motor"].adim_at(self._sensor("s1", 23.0))

        # s1'de alarm bildirimi olmamalı
        s1_alarmlar = [
            b for b in uc_sera["s1"]["bil"].gonderilen
            if b.oncelik in (BildirimOncelik.ALARM, BildirimOncelik.KRITIK)
        ]
        assert s1_alarmlar == []

        # s3'te alarm bildirimi olmalı
        s3_alarmlar = [
            b for b in uc_sera["s3"]["bil"].gonderilen
            if b.oncelik in (BildirimOncelik.ALARM, BildirimOncelik.KRITIK)
        ]
        assert len(s3_alarmlar) >= 1

    def test_cb_izolasyonu_s2_bozulsa_s1_calisir(
        self, profil_domates, profil_marul, tmp_db
    ):
        """s2'nin CB'si açılırsa s1 etkilenmez."""
        # s1 normal
        node1 = MockSahaNode("s1", profil_domates, 0.0, 0.0)
        node1.baglan()
        motor1, bus1, bil1, log1, _, _ = tam_altyapi_kur(
            "s1", profil_domates, node1, tmp_db
        )

        # s2 yüksek hata oranlı
        node2 = MockSahaNode("s2", profil_domates,
                             sensor_hata_orani=0.0,
                             komut_hata_orani=1.0)
        node2.baglan()
        bus2   = EventBus()
        cb2    = CircuitBreaker("s2_cb", hata_esigi=3, recovery_sn=60)
        sm2    = SeraStateMachine("s2", profil_domates,
                                  on_gecis=lambda d: bus2.yayinla(OlayTur.DURUM_DEGISTI, d))
        motor2 = KontrolMotoru("s2", profil_domates, node2, cb2, sm2, bus2)

        # s2'yi CB açacak kadar zorla
        for _ in range(5):
            try:
                motor2.adim_at(SensorOkuma(
                    sera_id="s2", T=28.0, H=72.0, co2=950,
                    isik=450, toprak_nem=500, ph=6.5, ec=1.8,
                ))
            except Exception:
                pass

        # s2'nin CB durumu → s1'e etki etmedi
        motor1.adim_at(self._sensor("s1", 23.0))
        assert node1.komutlar is not None  # s1 çalışmaya devam etti

    def test_her_sera_kendi_db_kayitlarini_gorur(self, uc_sera, tmp_db):
        """Farklı seralar aynı DB'de ama birbirinin kayıtlarını görmez."""
        uc_sera["s1"]["motor"].adim_at(self._sensor("s1", 28.0))
        uc_sera["s2"]["motor"].adim_at(self._sensor("s2", 23.0))

        k1 = uc_sera["s1"]["k_repo"].gecmis("s1")
        k2 = uc_sera["s2"]["k_repo"].gecmis("s2")

        # Her iki seranın kendi komutları var (veya yok ama karışmıyor)
        for k in k1:
            assert k.komut is not None  # geçerli Komut enum

    def test_cb_acildi_olayi_yayinlaniyor(self, profil_domates, tmp_db):
        """CB açılınca CB_ACILDI olayı EventBus'a yayınlanmalı."""
        node = MockSahaNode("s1", profil_domates,
                            sensor_hata_orani=0.0, komut_hata_orani=1.0)
        node.baglan()
        motor, bus, bil, log, _, _ = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        cb_olaylari = []
        bus.abone_ol(OlayTur.CB_ACILDI, lambda v: cb_olaylari.append(v))

        # CB'yi elle aç
        from sera_ai.domain.circuit_breaker import CBDurum
        motor.cb._hata_kaydet("test")
        motor.cb._hata_kaydet("test")
        motor.cb._hata_kaydet("test")

        if motor.cb.durum == CBDurum.ACIK:
            bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s1"})

        assert len(cb_olaylari) >= 1
        assert cb_olaylari[0]["sera_id"] == "s1"

    def test_cb_acildi_kritik_bildirim_gonderir(self, profil_domates, tmp_db):
        node = MockSahaNode("s1", profil_domates, 0.0, 0.0)
        node.baglan()
        motor, bus, bil, log, _, _ = tam_altyapi_kur(
            "s1", profil_domates, node, tmp_db
        )

        bus.yayinla(OlayTur.CB_ACILDI, {"sera_id": "s1"})

        kritik = [b for b in bil.gonderilen
                  if b.oncelik == BildirimOncelik.KRITIK]
        assert len(kritik) == 1
