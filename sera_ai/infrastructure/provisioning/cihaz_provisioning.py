"""
Cihaz Provisioning — ESP32-S3 Saha Node Ekleme Akışı

Yeni bir cihaz sisteme eklendiğinde:
  1. Benzersiz cihaz_id ve seri_no üret
  2. Güçlü rastgele şifre üret + hash'le
  3. MQTT konu listesini oluştur
  4. ESP32 firmware'ine yüklenecek config dict döndür

cihaz_id formatı: SERA-{tesis_kodu}-{sira_no:03d}
  Örnek: SERA-IST01-001 (İstanbul tesis 1, 1. cihaz)
"""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sera_ai.domain.models import CihazKimlik, CihazKayit
from ..repositories.cihaz_repository import SQLiteCihazRepository
from ..mqtt.broker_auth import yazma_konulari_olustur


class CihazProvisioning:
    """
    ESP32 cihaz kayıt ve yapılandırma servisi.

    Kullanım:
        prov = CihazProvisioning(repo, mqtt_host="mqtt.sera-ai.local")
        cihaz, sifre, konfig = prov.yeni_cihaz_olustur("IST01", "s1")
        # sifre → tek seferlik gösterilir, konfig → ESP32'ye yüklenir
    """

    def __init__(
        self,
        repo: SQLiteCihazRepository,
        mqtt_host: str = "mqtt.sera-ai.local",
        mqtt_port: int = 1883,
    ) -> None:
        self._repo      = repo
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port

    def yeni_cihaz_olustur(
        self,
        tesis_kodu: str,
        sera_id: str,
        mac_adresi: str = "",
        baglanti_tipi: str = "WiFi",
        firmware_versiyon: str = "1.0.0",
    ) -> tuple[CihazKimlik, str, dict]:
        """
        Sisteme yeni ESP32 cihazı ekle.

        Returns:
            (CihazKimlik, plain_sifre, firmware_konfig_dict)
            plain_sifre → tek seferlik gösterilmeli, saklanmamalı!
        """
        # Sıra no: tesis'teki mevcut cihaz sayısı + 1
        sira = self._repo.tesis_cihaz_sayisi(tesis_kodu) + 1
        cihaz_id = f"SERA-{tesis_kodu}-{sira:03d}"
        seri_no  = uuid.uuid4().hex[:12].upper()

        cihaz = CihazKimlik(
            cihaz_id=cihaz_id,
            tesis_kodu=tesis_kodu,
            sera_id=sera_id,
            seri_no=seri_no,
            mac_adresi=mac_adresi,
            baglanti_tipi=baglanti_tipi,
            firmware_versiyon=firmware_versiyon,
            son_gorulen=datetime.now(),
            aktif=True,
        )

        # Şifre üret + hash'le
        plain_sifre = secrets.token_urlsafe(16)
        sifre_hash  = _hash_sifre(plain_sifre)

        yazma_konulari = yazma_konulari_olustur(tesis_kodu, sera_id, cihaz_id)
        kayit = CihazKayit(
            cihaz_id=cihaz_id,
            sifre_hash=sifre_hash,
            izin_verilen_konular=yazma_konulari,
        )

        self._repo.kayit_et(cihaz, kayit)

        konfig = self.firmware_config_uret(cihaz, plain_sifre)
        return cihaz, plain_sifre, konfig

    def sifre_sifirla(self, cihaz_id: str) -> Optional[tuple[str, str]]:
        """
        Cihaz şifresini sıfırla.

        Returns:
            (yeni_hash, plain_sifre) veya None (cihaz bulunamadı)
        """
        cihaz = self._repo.bul(cihaz_id)
        if cihaz is None:
            return None
        plain_sifre = secrets.token_urlsafe(16)
        yeni_hash   = _hash_sifre(plain_sifre)
        self._repo.sifre_guncelle(cihaz_id, yeni_hash)
        return yeni_hash, plain_sifre

    def firmware_config_uret(self, cihaz: CihazKimlik, sifre: str) -> dict:
        """
        ESP32 firmware'ine yüklenecek yapılandırma dict'i.
        JSON olarak flash'a yazılır veya OTA ile güncellenir.
        """
        return {
            "cihaz_id":              cihaz.cihaz_id,
            "seri_no":               cihaz.seri_no,
            "mqtt_host":             self._mqtt_host,
            "mqtt_port":             self._mqtt_port,
            "mqtt_kullanici":        cihaz.cihaz_id,
            "mqtt_sifre":            sifre,
            "sensor_topic":          f"sera/{cihaz.tesis_kodu}/{cihaz.sera_id}/sensor",
            "komut_topic":           f"sera/{cihaz.tesis_kodu}/{cihaz.sera_id}/komut",
            "durum_topic":           f"sera/{cihaz.tesis_kodu}/{cihaz.sera_id}/durum",
            "kalp_atisi_topic":      f"cihaz/{cihaz.cihaz_id}/kalp_atisi",
            "firmware_topic":        f"cihaz/{cihaz.cihaz_id}/firmware",
            "kalp_atisi_interval_sn": 30,
            "sensor_interval_sn":    5,
            "wifi_ssid":             "",   # kullanıcı dolduracak
            "wifi_sifre":            "",   # kullanıcı dolduracak
        }


# ── Yardımcılar ────────────────────────────────────────────────

def _hash_sifre(sifre: str) -> str:
    """Şifreyi tuzlayarak SHA-256 ile hash'le. Format: 'salt:hash'"""
    salt = secrets.token_hex(16)
    h    = hashlib.sha256((salt + sifre).encode()).hexdigest()
    return f"{salt}:{h}"
