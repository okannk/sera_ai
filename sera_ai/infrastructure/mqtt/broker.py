"""
Mosquitto / paho-mqtt Bağlantısı

Gerçek MQTT broker (Mosquitto) ile haberleşen istemci.
paho-mqtt kurulu değilse sessiz hata — lazy import.

Kurulum:
    pip install paho-mqtt
    # veya pyproject.toml [hardware] extras ile

Kullanım:
    istemci = PahoMQTTIstemci(
        istemci_id="merkez_001",
        host="localhost",
        port=1883,
    )
    if istemci.baglan():
        istemci.abone_ol("sera/+/sensor", lambda t, p: print(t, p))
        istemci.yayinla("sera/esp32_a/komut", "FAN_AC")

Thread güvenliği:
    paho loop_start() ayrı thread'de çalışır.
    Callback'ler paho thread'inde çağrılır — uygulama bunu beklemelidir.
    Abonelik haritası threading.Lock ile korunur.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from .base import MesajCallback, MQTTIstemciBase


def _wildcard_eslesir(pattern: str, topic: str) -> bool:
    """MQTT wildcard eşleştirme (+, #)."""
    p = pattern.split("/")
    t = topic.split("/")
    if "#" in p:
        idx = p.index("#")
        return p[:idx] == t[:idx]
    if len(p) != len(t):
        return False
    return all(pp in ("+", tp) for pp, tp in zip(p, t))


class PahoMQTTIstemci(MQTTIstemciBase):
    """
    MQTTIstemciBase → paho-mqtt implementasyonu.

    paho callback imzası: on_message(client, userdata, msg)
    Bizim ABC imzası:     callback(topic: str, payload: bytes)

    Bu sınıf aralarında dönüştürme yaparak ikisini birleştirir.
    """

    def __init__(
        self,
        istemci_id:  str,
        host:        str = "localhost",
        port:        int = 1883,
        kullanici:   str = "",
        sifre:       str = "",
        keepalive:   int = 60,
    ) -> None:
        self._istemci_id = istemci_id
        self._host       = host
        self._port       = port
        self._kullanici  = kullanici
        self._sifre      = sifre
        self._keepalive  = keepalive
        self._client     = None
        self._bagli      = False
        # topic_pattern → [callback, ...]
        self._abonelikler: dict[str, list[MesajCallback]] = {}
        self._lock = threading.Lock()

    def baglan(self) -> bool:
        """
        paho-mqtt ile broker'a bağlan.
        paho kurulu değilse False döner (IOError fırlatmaz).
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("[MQTT] paho-mqtt kurulu değil: pip install paho-mqtt")
            return False

        client = mqtt.Client(client_id=self._istemci_id)

        if self._kullanici:
            client.username_pw_set(self._kullanici, self._sifre)

        client.on_connect    = self._on_connect
        client.on_message    = self._on_message
        client.on_disconnect = self._on_disconnect

        try:
            client.connect(self._host, self._port, keepalive=self._keepalive)
            client.loop_start()
            self._client = client
            # Bağlantı onayını kısaca bekle (on_connect callback)
            import time; time.sleep(0.5)
            return self._bagli
        except Exception as e:
            print(f"[MQTT:{self._istemci_id}] Bağlantı hatası: {e}")
            return False

    def kes(self) -> None:
        self._bagli = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    def yayinla(self, topic: str, payload: str | bytes, qos: int = 0) -> bool:
        if not self._bagli or not self._client:
            return False
        if isinstance(payload, str):
            payload = payload.encode()
        result = self._client.publish(topic, payload, qos=qos)
        return result.rc == 0  # 0 = MQTT_ERR_SUCCESS

    def abone_ol(self, topic: str, callback: MesajCallback) -> None:
        with self._lock:
            self._abonelikler.setdefault(topic, []).append(callback)
        # Eğer bağlıysak hemen subscribe gönder
        if self._bagli and self._client:
            self._client.subscribe(topic, qos=0)

    def abonelikten_cik(self, topic: str) -> None:
        with self._lock:
            self._abonelikler.pop(topic, None)
        if self._bagli and self._client:
            self._client.unsubscribe(topic)

    @property
    def bagli_mi(self) -> bool:
        return self._bagli

    # ── paho Callback'leri ─────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._bagli = True
            # Kayıtlı abonelikleri yeniden uygula (yeniden bağlanma senaryosu)
            with self._lock:
                topics = list(self._abonelikler.keys())
            for t in topics:
                client.subscribe(t, qos=0)
        else:
            print(f"[MQTT:{self._istemci_id}] Bağlantı reddedildi: rc={rc}")
            self._bagli = False

    def _on_message(self, client, userdata, msg):
        """paho mesajını ilgili callback'lere yönlendir."""
        topic   = msg.topic
        payload = msg.payload
        with self._lock:
            hedefler = [
                cb
                for pattern, cbs in self._abonelikler.items()
                if _wildcard_eslesir(pattern, topic)
                for cb in cbs
            ]
        for cb in hedefler:
            try:
                cb(topic, payload)
            except Exception as e:
                print(f"[MQTT:{self._istemci_id}] Callback hatası ({topic}): {e}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"[MQTT:{self._istemci_id}] Beklenmedik bağlantı kesintisi (rc={rc})")
        self._bagli = False

    def __repr__(self) -> str:
        return (
            f"PahoMQTTIstemci({self._istemci_id!r}, "
            f"{self._host}:{self._port}, bagli={self._bagli})"
        )
