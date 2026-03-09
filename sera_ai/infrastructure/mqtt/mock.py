"""
Mock MQTT Altyapısı — Gerçek Broker Gerektirmez

Bileşenler:
  MockMQTTBroker   — in-process mesaj yönlendirici (singleton per test)
  MockMQTTIstemci  — MQTTIstemciBase impl, broker üzerinden pub/sub
  ESP32Simulatoru  — ESP32 firmware davranışını simüle eder:
                       * sensor verisi yayınlar (sera/{node_id}/sensor)
                       * komut dinler (sera/{node_id}/komut)
                       * ACK gönderir (sera/{node_id}/ack)

Kullanım (test):
    broker = MockMQTTBroker()
    istemci = MockMQTTIstemci("test_istemci", broker)
    istemci.baglan()
    istemci.abone_ol("sera/s1/sensor", lambda t, p: ...)

    sim = ESP32Simulatoru("esp32_sera_a", "s1", profil, broker)
    sim.baslat()
    sim.veri_gonder()   # Manuel tetikle → callback çağrılır
"""
from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from sera_ai.domain.models import BitkilProfili, Komut, SensorOkuma
from .base import MesajCallback, MQTTIstemciBase
from .topics import SeraTopics


# ── Wildcard Eşleştirme ──────────────────────────────────────────

def _wildcard_eslesir(pattern: str, topic: str) -> bool:
    """
    MQTT wildcard kuralları:
      '+' → tek seviye (herhangi bir değer)
      '#' → son seviye; tüm alt seviyeler dahil

    Örnekler:
      'sera/+/sensor' eşleşir 'sera/esp32_a/sensor'
      'sera/#'        eşleşir 'sera/esp32_a/sensor/extra'
    """
    p_parcalar = pattern.split("/")
    t_parcalar = topic.split("/")

    # '#' varsa o noktadan sonrası kabul
    if "#" in p_parcalar:
        idx = p_parcalar.index("#")
        return p_parcalar[:idx] == t_parcalar[:idx]

    if len(p_parcalar) != len(t_parcalar):
        return False

    return all(p in ("+", t) for p, t in zip(p_parcalar, t_parcalar))


# ── Mock Broker ──────────────────────────────────────────────────

class MockMQTTBroker:
    """
    In-process pub/sub yönlendiricisi.

    Birden fazla MockMQTTIstemci aynı broker üzerinden haberleşir.
    publish() → senkron callback çağrısı → deterministik testler.

    Her test kendi broker instance'ını oluşturabilir:
        broker = MockMQTTBroker()
    Paylaşmak için aynı instance aktarın.
    """

    def __init__(self) -> None:
        # {pattern: [(istemci, callback), ...]}
        self._aboneler: dict[str, list[tuple[object, MesajCallback]]] = {}
        self._lock = threading.Lock()
        self._mesaj_gecmisi: list[tuple[str, bytes]] = []

    def yayinla(self, topic: str, payload: bytes, kaynak=None) -> None:
        """
        Tüm eşleşen abonelerin callback'lerini senkron olarak çağır.
        kaynak kendi mesajını almaz (gerçek MQTT davranışı).
        """
        with self._lock:
            self._mesaj_gecmisi.append((topic, payload))
            hedef_listeler = []
            for pattern, istemci_cb_list in self._aboneler.items():
                if _wildcard_eslesir(pattern, topic):
                    hedef_listeler.extend(istemci_cb_list)

        # Callback'ler lock dışında çağrılır (dead-lock önlemi)
        for istemci, cb in hedef_listeler:
            if istemci is not kaynak:
                cb(topic, payload)

    def abone_ol(self, istemci: object, pattern: str, cb: MesajCallback) -> None:
        with self._lock:
            self._aboneler.setdefault(pattern, []).append((istemci, cb))

    def abonelikten_cik(self, istemci: object, pattern: str) -> None:
        with self._lock:
            if pattern in self._aboneler:
                self._aboneler[pattern] = [
                    (i, cb) for i, cb in self._aboneler[pattern]
                    if i is not istemci
                ]

    @property
    def mesaj_sayisi(self) -> int:
        """Test assertion'ları için toplam yayınlanan mesaj sayısı."""
        return len(self._mesaj_gecmisi)

    def gecmis_temizle(self) -> None:
        with self._lock:
            self._mesaj_gecmisi.clear()


# ── Mock MQTT İstemci ─────────────────────────────────────────────

class MockMQTTIstemci(MQTTIstemciBase):
    """
    MQTTIstemciBase implementasyonu — gerçek ağ bağlantısı yok.

    Tüm mesajlaşma in-process MockMQTTBroker üzerinden yapılır.
    """

    def __init__(self, istemci_id: str, broker: MockMQTTBroker) -> None:
        self._id = istemci_id
        self._broker = broker
        self._bagli = False
        # Kendi abonelik haritası (abonelikten_cik için)
        self._abonelikler: set[str] = set()

    def baglan(self) -> bool:
        self._bagli = True
        return True

    def kes(self) -> None:
        for pattern in list(self._abonelikler):
            self._broker.abonelikten_cik(self, pattern)
        self._abonelikler.clear()
        self._bagli = False

    def yayinla(self, topic: str, payload: str | bytes, qos: int = 0) -> bool:
        if not self._bagli:
            return False
        if isinstance(payload, str):
            payload = payload.encode()
        self._broker.yayinla(topic, payload, kaynak=self)
        return True

    def abone_ol(self, topic: str, callback: MesajCallback) -> None:
        self._broker.abone_ol(self, topic, callback)
        self._abonelikler.add(topic)

    def abonelikten_cik(self, topic: str) -> None:
        self._broker.abonelikten_cik(self, topic)
        self._abonelikler.discard(topic)

    @property
    def bagli_mi(self) -> bool:
        return self._bagli

    def __repr__(self) -> str:
        return f"MockMQTTIstemci({self._id!r}, bagli={self._bagli})"


# ── ESP32 Simülatörü ─────────────────────────────────────────────

@dataclass
class _SimDurum:
    """Simüle edilen fiziksel sera ortamı."""
    T:            float
    H:            float
    co2:          float
    sulama_acik:  bool = False
    isitici_acik: bool = False
    sogutma_acik: bool = False
    fan_acik:     bool = False


class ESP32Simulatoru:
    """
    ESP32-S3 firmware davranışını simüle eder.

    Gerçek firmware ne yapar?
      1. Sensörleri okur (SHT31, MH-Z19C, BH1750...)
      2. JSON'a dönüştürür → sera/{node_id}/sensor yayınlar
      3. sera/{node_id}/komut dinler
      4. Komutu röleye uygular → "OK" / "ERR:sebep" yayınlar

    Bu sınıf aynı davranışı Python içinde gösterir → gerçek ESP32 olmadan
    merkez tarafının MQTT entegrasyonunu test edebiliriz.

    Kullanım:
        broker = MockMQTTBroker()
        sim = ESP32Simulatoru("esp32_sera_a", "s1", profil, broker)
        sim.baslat()
        sim.veri_gonder()       # Sensör verisi yayınla (test tetikler)
        sim.durdur()
    """

    def __init__(
        self,
        node_id: str,
        sera_id: str,
        profil: BitkilProfili,
        broker: MockMQTTBroker,
    ) -> None:
        self.node_id  = node_id
        self.sera_id  = sera_id
        self.profil   = profil
        self._topics  = SeraTopics(node_id)
        self._istemci = MockMQTTIstemci(f"esp32_{node_id}", broker)
        self._durum   = _SimDurum(
            T=profil.opt_T,
            H=(profil.min_H + profil.max_H) / 2,
            co2=float(profil.opt_CO2),
        )
        # İstatistik — test assertion için
        self.gonderilen_veri_sayisi: int = 0
        self.alinan_komut_sayisi:    int = 0

    def baslat(self) -> None:
        """Broker'a bağlan ve komut topic'ine abone ol."""
        self._istemci.baglan()
        self._istemci.abone_ol(self._topics.komut, self._komut_isle)

    def durdur(self) -> None:
        self._istemci.kes()

    def veri_gonder(self) -> None:
        """
        Sensör verisi yayınla.

        Gerçek ESP32'de bu timer interrupt'ta çağrılır (her 2.5s).
        Testlerde elle çağrılır → deterministik.
        """
        self._fizik_adimi()
        d = self._durum
        payload = json.dumps({
            "T":      round(d.T, 1),
            "H":      round(d.H, 1),
            "co2":    int(d.co2),
            "isik":   random.randint(200, 900),
            "toprak": random.randint(300, 700),
            "ph":     round(random.uniform(5.8, 7.2), 2),
            "ec":     round(random.uniform(1.4, 2.8), 2),
        })
        self._istemci.yayinla(self._topics.sensor, payload, qos=0)
        self.gonderilen_veri_sayisi += 1

    # ── Komut işleme ────────────────────────────────────────────

    def _komut_isle(self, topic: str, payload: bytes) -> None:
        """MQTT callback — komut al, röle uygula, ACK gönder."""
        komut_str = payload.decode().strip()
        self.alinan_komut_sayisi += 1
        try:
            komut = Komut(komut_str)
            self._aktüatör_güncelle(komut)
            self._istemci.yayinla(self._topics.ack, "OK", qos=1)
        except ValueError:
            self._istemci.yayinla(
                self._topics.ack, f"ERR:bilinmeyen:{komut_str}", qos=1
            )

    def _aktüatör_güncelle(self, komut: Komut) -> None:
        d = self._durum
        tablo: dict[Komut, Callable] = {
            Komut.SULAMA_BASLAT:  lambda: setattr(d, "sulama_acik",  True),
            Komut.SULAMA_DURDUR:  lambda: setattr(d, "sulama_acik",  False),
            Komut.ISITICI_BASLAT: lambda: setattr(d, "isitici_acik", True),
            Komut.ISITICI_DURDUR: lambda: setattr(d, "isitici_acik", False),
            Komut.SOGUTMA_BASLAT: lambda: setattr(d, "sogutma_acik", True),
            Komut.SOGUTMA_DURDUR: lambda: setattr(d, "sogutma_acik", False),
            Komut.FAN_BASLAT:     lambda: setattr(d, "fan_acik",     True),
            Komut.FAN_DURDUR:     lambda: setattr(d, "fan_acik",     False),
            Komut.ACIL_DURDUR:    self._acil_kapat,
            Komut.ISIK_BASLAT:    lambda: None,
            Komut.ISIK_DURDUR:    lambda: None,
        }
        if komut in tablo:
            tablo[komut]()

    def _acil_kapat(self) -> None:
        d = self._durum
        d.sulama_acik = d.isitici_acik = d.sogutma_acik = d.fan_acik = False

    # ── Fizik ───────────────────────────────────────────────────

    def _fizik_adimi(self) -> None:
        """Gaussian drift + aktüatör etkileri."""
        d = self._durum
        d.T   += random.gauss(0, 0.15)
        d.H   += random.gauss(0, 0.25)
        d.co2 += random.gauss(0, 10)
        if d.sogutma_acik: d.T   -= 0.3
        if d.isitici_acik: d.T   += 0.4
        if d.fan_acik:     d.H   -= 0.2
        if d.sulama_acik:  d.H   += 0.3
        d.T   = max(5,   min(45,   d.T))
        d.H   = max(20,  min(98,   d.H))
        d.co2 = max(300, min(2000, d.co2))

    def __repr__(self) -> str:
        return (
            f"ESP32Simulatoru({self.node_id!r}, "
            f"T={self._durum.T:.1f}°C, "
            f"basladi={self._istemci.bagli_mi})"
        )


# ── MQTT → EventBus Köprüsü ──────────────────────────────────────

class MQTTKomutKoprusu:
    """
    Dış MQTT komutlarını (dashboard, operatör) sisteme yönlendirir.

    Abone olduğu topic: sera/{node_id}/dis_komut
    Aldığında: callback(sera_id, Komut) çağrılır

    Kullanım:
        kopru = MQTTKomutKoprusu(istemci, node_sera_haritasi, on_komut)
        kopru.baslat()
        # Artık MQTT'den gelen manuel komutlar on_komut ile iletilir

    on_komut imzası: (sera_id: str, komut: Komut) -> None
    """

    def __init__(
        self,
        istemci: MQTTIstemciBase,
        node_sera_haritasi: dict[str, str],   # node_id → sera_id
        on_komut: Callable[[str, Komut], None],
    ) -> None:
        self._istemci     = istemci
        self._harita      = node_sera_haritasi
        self._on_komut    = on_komut
        self._aktif       = False

    def baslat(self) -> None:
        """Her node'un dis_komut topic'ine abone ol."""
        for node_id in self._harita:
            t = SeraTopics(node_id)
            self._istemci.abone_ol(t.dis_komut, self._mesaj_isle)
        self._aktif = True

    def durdur(self) -> None:
        for node_id in self._harita:
            t = SeraTopics(node_id)
            self._istemci.abonelikten_cik(t.dis_komut)
        self._aktif = False

    def _mesaj_isle(self, topic: str, payload: bytes) -> None:
        try:
            node_id = SeraTopics.node_id_cozumle(topic)
            sera_id = self._harita.get(node_id)
            if sera_id is None:
                return
            komut = Komut(payload.decode().strip())
            self._on_komut(sera_id, komut)
        except (ValueError, KeyError):
            pass  # Bilinmeyen komut → sessizce yoksay
