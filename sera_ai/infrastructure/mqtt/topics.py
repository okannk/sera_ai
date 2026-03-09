"""
MQTT Topic Yönetimi — Merkezi Topic Fabrikası

Neden burada?
  Topic string'leri ESP32 firmware, Python merkez ve dashboard arasında
  sözleşmedir. Bir string dağınık kod içinde değişirse sistem sessizce kırılır.
  Bu dosya tek kaynak: topic değişikliği = sadece bu dosya.

Topic şeması:
  sera/{node_id}/sensor     ← ESP32 → Merkez  (JSON sensör verisi, QoS 0)
  sera/{node_id}/komut      → Merkez → ESP32   (komut string, QoS 1)
  sera/{node_id}/ack        ← ESP32 → Merkez   ("OK" / "ERR:sebep", QoS 1)
  sera/{node_id}/durum      → Merkez → Dış     (state machine JSON, QoS 0)
  sera/{node_id}/dis_komut  ← Dış   → Merkez   (manuel override, QoS 1)

  sera/sistem/komut         ← Dış   → Merkez   (global sistem komutları)
"""
from __future__ import annotations

_KOK = "sera"


class SeraTopics:
    """
    Tek bir sera node'unun MQTT topic'lerini üretir.

    Kullanım:
        t = SeraTopics("esp32_sera_a")
        client.subscribe(t.sensor)
        client.publish(t.komut, "FAN_AC")
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        _kök = f"{_KOK}/{node_id}"

        # ← ESP32'nin yayınladığı (merkez okur)
        self.sensor = f"{_kök}/sensor"

        # → Merkez'in gönderdiği (ESP32 okur)
        self.komut = f"{_kök}/komut"

        # ← ESP32'nin komut onayı (merkez okur)
        self.ack = f"{_kök}/ack"

        # → Merkez'in durum yayını (dashboard okur)
        self.durum = f"{_kök}/durum"

        # ← Dashboard'un manuel komutu (merkez okur)
        self.dis_komut = f"{_kök}/dis_komut"

    @staticmethod
    def node_id_cozumle(topic: str) -> str:
        """
        'sera/esp32_sera_a/sensor' → 'esp32_sera_a'

        Wildcard subscription'dan gelen mesajlarda hangi node olduğunu anlamak için.
        """
        parcalar = topic.split("/")
        if len(parcalar) >= 2:
            return parcalar[1]
        raise ValueError(f"Geçersiz sera topic formatı: {topic!r}")

    def __repr__(self) -> str:
        return f"SeraTopics(node_id={self.node_id!r})"


# Global sistem topic'leri (node'a özgü değil)
SISTEM_KOMUT_TOPIC = f"{_KOK}/sistem/komut"

# Tüm seraların sensör verisini tek subscriptionda almak için wildcard
TUM_SENSOR_WILDCARD = f"{_KOK}/+/sensor"
TUM_ACK_WILDCARD    = f"{_KOK}/+/ack"
TUM_DIS_KOMUT_WILDCARD = f"{_KOK}/+/dis_komut"
