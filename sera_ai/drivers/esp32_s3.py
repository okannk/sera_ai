"""
ESP32-S3 Saha Node — WiFi/MQTT Üzerinden Haberleşme

ESP32-S3 firmware'i şunları yapar:
  1. SHT31/MH-Z19C/BH1750/kapasitif nem sensörlerini okur
  2. JSON'a dönüştürür → sera/{node_id}/sensor yayınlar
  3. sera/{node_id}/komut dinler
  4. Komut onayını yayınlar: sera/{node_id}/ack

Bu Python sınıfı merkez tarafındaki istemci —
MQTT broker'a bağlanır, ESP32'yi remote olarak kontrol eder.

Sensör doğrulama:
  SeraKonfig.sensorler listesi hangi sensörlerin takılı olduğunu bildirir.
  Her sensör tipinin üretmesi beklenen JSON alanları kontrol edilir.
  Eksik veya fiziksel sınır dışı alan → sentinel değer (gecerli_mi=False).
  sensorler=[] verilirse doğrulama atlanır (geriye dönük uyumlu).

Kurulum:
    pip install paho-mqtt
"""
from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime
from typing import Optional

from .base import SahaNodeBase
from ..domain.models import Komut, SensorOkuma


# ── Sensör tipi → ürettiği JSON alanları ────────────────────────
# ESP32 firmware'in gönderdiği JSON key adları
_SENSOR_ALANLARI: dict[str, set[str]] = {
    "sht31":         {"T", "H"},
    "dht22":         {"T", "H"},
    "mh_z19c":       {"co2"},
    "bh1750":        {"isik"},
    "kapasitif_nem": {"toprak"},
}

# Alan → fiziksel geçerlilik aralığı (SensorOkuma.gecerli_mi ile uyumlu)
_ALAN_ARALIK: dict[str, tuple[float, float]] = {
    "T":      (-10,  60),
    "H":      (0,    100),
    "co2":    (300,  5000),
    "isik":   (0,    100000),
    "toprak": (0,    1023),
    "ph":     (3.0,  9.0),
    "ec":     (0.0,  10.0),
}

# Geçersiz alan için sentinel değerler — gecerli_mi=False yapar
_SENTINEL: dict[str, float] = {
    "T":      -999.0,
    "H":      -999.0,
    "co2":    0,
    "isik":   -1,
    "toprak": -1,
    "ph":     -1.0,
    "ec":     -1.0,
}

# JSON alanı → _dict_to_okuma'nın beklediği dict anahtar adı (aynı olan atlanır)
# Not: "toprak" JSON'da "toprak", SensorOkuma'da "toprak_nem" → özel dönüşüm


class ESP32S3Node(SahaNodeBase):
    """
    ESP32-S3 node ile MQTT üzerinden iletişim.

    MQTT topic şeması:
      sera/{node_id}/sensor  ← ESP32 sensör verisi yayınlar (JSON)
      sera/{node_id}/komut   → Merkez komut gönderir (string)
      sera/{node_id}/ack     ← ESP32 komut onayı döner ("OK" / "ERR")

    Thread güvenliği:
      MQTT callback'leri ayrı thread'de çalışır.
      _sensor_kuyruk ve _ack_kuyruk thread-safe Queue kullanır.

    Sensör doğrulama:
      sensorler=[{tip: sht31}, {tip: mh_z19c}, ...]  → aktif doğrulama
      sensorler=[]                                    → doğrulama atlanır
    """

    SENSOR_TIMEOUT_SN = 5.0
    KOMUT_TIMEOUT_SN  = 3.0

    def __init__(
        self,
        sera_id:    str,
        node_id:    str,
        mqtt_host:  str  = "localhost",
        mqtt_port:  int  = 1883,
        kullanici:  str  = "",
        sifre:      str  = "",
        sensorler:  list = None,   # SeraKonfig.sensorler — doğrulama için
    ):
        self.sera_id    = sera_id
        self.node_id    = node_id
        self.mqtt_host  = mqtt_host
        self.mqtt_port  = mqtt_port
        self._kullanici = kullanici
        self._sifre     = sifre
        self._sensorler = sensorler or []
        self._client    = None
        self._baglandı  = False

        # Konfigürasyondan beklenen alan kümesini önceden hesapla
        self._beklenen_alanlar: set[str] = self._beklenen_alanlari_hesapla()

        self._sensor_kuyruk: queue.Queue[dict] = queue.Queue(maxsize=10)
        self._ack_kuyruk:    queue.Queue[str]  = queue.Queue(maxsize=5)

        self._topic_sensor = f"sera/{node_id}/sensor"
        self._topic_komut  = f"sera/{node_id}/komut"
        self._topic_ack    = f"sera/{node_id}/ack"

    def _beklenen_alanlari_hesapla(self) -> set[str]:
        """
        sensorler listesinden hangi JSON alanlarının gelmesi gerektiğini çıkar.
        ph ve ec her zaman beklenir (her kurulumda bulunur).
        """
        if not self._sensorler:
            return set()  # Doğrulama aktif değil

        alanlar = {"ph", "ec"}  # Her kurulumda ortak
        for s in self._sensorler:
            tip = s.get("tip", "").lower()
            alanlar |= _SENSOR_ALANLARI.get(tip, set())
        return alanlar

    def baglan(self) -> bool:
        """
        MQTT broker'a bağlan ve ESP32 topic'lerine abone ol.
        paho-mqtt kurulu değilse False döner (graceful).
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("[ESP32] paho-mqtt kurulu değil: pip install paho-mqtt")
            return False

        client = mqtt.Client(client_id=f"merkez_{self.node_id}")

        if self._kullanici:
            client.username_pw_set(self._kullanici, self._sifre)

        client.on_connect    = self._on_connect
        client.on_message    = self._on_message
        client.on_disconnect = self._on_disconnect

        try:
            client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            client.loop_start()
            self._client  = client
            self._baglandı = True
            time.sleep(3)
            return self._baglandı
        except Exception as e:
            print(f"[ESP32:{self.node_id}] MQTT bağlantı hatası: {e}")
            return False

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        """ESP32'nin MQTT'ye yayınladığı son sensör verisini al."""
        if not self._baglandı or not self._client:
            raise IOError(f"[{self.node_id}] MQTT bağlantısı yok")

        try:
            veri = self._sensor_kuyruk.get(timeout=self.SENSOR_TIMEOUT_SN)
            veri = self._dogrula_ve_doldur(veri)
            return self._dict_to_okuma(sera_id, veri)
        except queue.Empty:
            raise IOError(
                f"[{self.node_id}] Sensör timeout ({self.SENSOR_TIMEOUT_SN}s) — "
                "ESP32 yanıt vermedi veya MQTT koptu"
            )

    def komut_gonder(self, komut: Komut) -> bool:
        """ESP32'ye MQTT üzerinden komut gönder, ACK bekle."""
        if not self._baglandı or not self._client:
            raise IOError(f"[{self.node_id}] MQTT bağlantısı yok")

        while not self._ack_kuyruk.empty():
            self._ack_kuyruk.get_nowait()

        self._client.publish(self._topic_komut, komut.value, qos=1)

        try:
            ack = self._ack_kuyruk.get(timeout=self.KOMUT_TIMEOUT_SN)
            if ack.startswith("OK"):
                return True
            raise IOError(f"[{self.node_id}] Komut reddedildi: {ack}")
        except queue.Empty:
            raise IOError(
                f"[{self.node_id}] Komut ACK timeout ({self.KOMUT_TIMEOUT_SN}s): "
                f"{komut.value}"
            )

    def kapat(self):
        """MQTT bağlantısını temiz kapat."""
        self._baglandı = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    # ── Sensör Doğrulama ─────────────────────────────────────────

    def _dogrula_ve_doldur(self, veri: dict) -> dict:
        """
        ESP32'den gelen JSON'ı sensör konfigürasyonuna göre doğrula.

        sensorler boşsa (doğrulama kapalı) veriyi olduğu gibi döner.

        Her beklenen alan için:
          1. Alan JSON'da var mı?
          2. Değer fiziksel aralıkta mı?
          3. Yoksa veya geçersizse → sentinel (gecerli_mi=False yapacak)
        """
        if not self._beklenen_alanlar:
            return veri  # Doğrulama kapalı

        sonuc = dict(veri)
        for alan in self._beklened_kontrol_alanlari():
            ham_deger = veri.get(alan)

            if ham_deger is None:
                print(
                    f"[ESP32:{self.node_id}] Eksik alan: '{alan}' "
                    f"(sensör konfigürasyona göre bekleniyor)"
                )
                sonuc[alan] = _SENTINEL[alan]
                continue

            aralik = _ALAN_ARALIK.get(alan)
            if aralik and not (aralik[0] <= ham_deger <= aralik[1]):
                print(
                    f"[ESP32:{self.node_id}] Geçersiz değer: "
                    f"'{alan}'={ham_deger} (beklenen: {aralik[0]}–{aralik[1]})"
                )
                sonuc[alan] = _SENTINEL[alan]

        return sonuc

    def _beklened_kontrol_alanlari(self) -> set[str]:
        """Doğrulama yapılacak alan kümesi (_ALAN_ARALIK'ta olanlar)."""
        return self._beklenen_alanlar & _ALAN_ARALIK.keys()

    # ── MQTT Callback'leri ────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self._topic_sensor, qos=0)
            client.subscribe(self._topic_ack, qos=1)
        else:
            print(f"[ESP32:{self.node_id}] MQTT bağlantı ret: rc={rc}")
            self._baglandı = False

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            if topic == self._topic_sensor:
                veri = json.loads(msg.payload.decode())
                if self._sensor_kuyruk.full():
                    self._sensor_kuyruk.get_nowait()
                self._sensor_kuyruk.put_nowait(veri)
            elif topic == self._topic_ack:
                ack = msg.payload.decode().strip()
                if not self._ack_kuyruk.full():
                    self._ack_kuyruk.put_nowait(ack)
        except Exception as e:
            print(f"[ESP32:{self.node_id}] Mesaj parse hatası: {e}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"[ESP32:{self.node_id}] MQTT bağlantı kesildi (rc={rc})")
            self._baglandı = False

    # ── Dönüştürücüler ────────────────────────────────────────────

    def _dict_to_okuma(self, sera_id: str, veri: dict) -> SensorOkuma:
        """
        ESP32 JSON → SensorOkuma.

        Beklenen JSON format:
          {
            "T": 23.4, "H": 68.2, "co2": 945,
            "isik": 450, "toprak": 512,
            "ph": 6.5, "ec": 1.8
          }

        Doğrulama sonrası eksik/geçersiz alanlar sentinel değer taşır.
        SensorOkuma.gecerli_mi bunları otomatik yakalar.
        """
        return SensorOkuma(
            sera_id=sera_id,
            T=float(veri.get("T",      _SENTINEL["T"])),
            H=float(veri.get("H",      _SENTINEL["H"])),
            co2=int(veri.get("co2",    _SENTINEL["co2"])),
            isik=int(veri.get("isik",  _SENTINEL["isik"])),
            toprak_nem=int(veri.get("toprak", _SENTINEL["toprak"])),
            ph=float(veri.get("ph",    _SENTINEL["ph"])),
            ec=float(veri.get("ec",    _SENTINEL["ec"])),
        )

    def __repr__(self) -> str:
        return (
            f"ESP32S3Node({self.node_id}, "
            f"mqtt={self.mqtt_host}:{self.mqtt_port}, "
            f"bağlı={self._baglandı}, "
            f"sensörler={len(self._sensorler)})"
        )
