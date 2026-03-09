"""
ESP32-S3 Saha Node — WiFi/MQTT Üzerinden Haberleşme

ESP32-S3 firmware'i şunları yapar:
  1. DHT22'den T/H okur
  2. MQ-135'ten CO2 okur
  3. Analog pinlerden toprak nem, pH, EC okur
  4. Verileri MQTT'ye yayınlar:  sera/{node_id}/sensor
  5. Komutları MQTT'den dinler:  sera/{node_id}/komut
  6. Komut onayını yayınlar:     sera/{node_id}/ack

Bu Python sınıfı merkez tarafındaki istemci —
MQTT broker'a bağlanır, ESP32'yi remote olarak kontrol eder.

Kurulum:
    pip install paho-mqtt

Bağlantı:
    node = ESP32S3Node(
        sera_id="s1",
        node_id="esp32_sera_a",
        mqtt_host="192.168.1.100",
    )
    node.baglan()
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
    """

    SENSOR_TIMEOUT_SN = 5.0   # ESP32'den veri bekleme süresi
    KOMUT_TIMEOUT_SN  = 3.0   # ACK bekleme süresi

    def __init__(self, sera_id: str, node_id: str,
                 mqtt_host: str = "localhost", mqtt_port: int = 1883,
                 kullanici: str = "", sifre: str = ""):
        self.sera_id   = sera_id
        self.node_id   = node_id
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self._kullanici = kullanici
        self._sifre     = sifre
        self._client    = None
        self._baglandı  = False

        # Thread-safe kuyruklar — MQTT callback → ana thread
        self._sensor_kuyruk: queue.Queue[dict] = queue.Queue(maxsize=10)
        self._ack_kuyruk:    queue.Queue[str]  = queue.Queue(maxsize=5)

        # Topic tanımları
        self._topic_sensor = f"sera/{node_id}/sensor"
        self._topic_komut  = f"sera/{node_id}/komut"
        self._topic_ack    = f"sera/{node_id}/ack"

    def baglan(self) -> bool:
        """
        MQTT broker'a bağlan ve ESP32 topic'lerine abone ol.
        paho-mqtt kurulu değilse ImportError → False döner (graceful).
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
            client.loop_start()   # Arka plan thread'i
            self._client  = client
            self._baglandı = True
            # Broker onayını bekle (max 3s)
            time.sleep(3)
            return self._baglandı
        except Exception as e:
            print(f"[ESP32:{self.node_id}] MQTT bağlantı hatası: {e}")
            return False

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        """
        ESP32'nin MQTT'ye yayınladığı son sensör verisini al.

        ESP32 firmware her 2.5 saniyede bir veri yayınlar.
        Bu metod kuyruğu boşaltır — timeout'ta IOError.
        """
        if not self._baglandı or not self._client:
            raise IOError(f"[{self.node_id}] MQTT bağlantısı yok")

        try:
            veri = self._sensor_kuyruk.get(timeout=self.SENSOR_TIMEOUT_SN)
            return self._dict_to_okuma(sera_id, veri)
        except queue.Empty:
            raise IOError(
                f"[{self.node_id}] Sensör timeout ({self.SENSOR_TIMEOUT_SN}s) — "
                f"ESP32 yanıt vermedi veya MQTT koptu"
            )

    def komut_gonder(self, komut: Komut) -> bool:
        """
        ESP32'ye MQTT üzerinden komut gönder, ACK bekle.

        ESP32 firmware:
          1. Komutu alır
          2. Röleyi sürer
          3. "OK" veya "ERR:{sebep}" yayınlar
        """
        if not self._baglandı or not self._client:
            raise IOError(f"[{self.node_id}] MQTT bağlantısı yok")

        # ACK kuyruğunu temizle (eski onaylar karışmasın)
        while not self._ack_kuyruk.empty():
            self._ack_kuyruk.get_nowait()

        self._client.publish(self._topic_komut, komut.value, qos=1)

        try:
            ack = self._ack_kuyruk.get(timeout=self.KOMUT_TIMEOUT_SN)
            if ack.startswith("OK"):
                return True
            else:
                # "ERR:GUVENLIK_KİLİDİ" gibi
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

    # ── MQTT Callback'leri (arka plan thread'inde çalışır) ────

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
                # Kuyruk doluysa eski veriyi at (en yeni veri önemli)
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

    # ── Dönüştürücüler ────────────────────────────────────────

    def _dict_to_okuma(self, sera_id: str, veri: dict) -> SensorOkuma:
        """
        ESP32 firmware'inin gönderdiği JSON → SensorOkuma.

        Beklenen JSON format:
          {
            "T": 23.4, "H": 68.2, "co2": 945,
            "isik": 450, "toprak": 512,
            "ph": 6.5, "ec": 1.8
          }
        """
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

    def __repr__(self) -> str:
        return (
            f"ESP32S3Node({self.node_id}, "
            f"mqtt={self.mqtt_host}:{self.mqtt_port}, "
            f"bağlı={self._baglandı})"
        )
