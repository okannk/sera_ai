"""
Zero-Touch Provisioning — ESP32 Otomatik Kayıt Sistemi

Akış:
  1. ESP32 ilk açılışta AP modu açar (SERA-SETUP-XXXX)
  2. Kullanıcı bağlanır, kurulum sayfasını (192.168.4.1) doldurur
  3. ESP32 POST /api/v1/provisioning/kayit-talebi gönderir
  4. Talep BEKLEMEDE durumuna geçer, dashboard'da gösterilir
  5. Operatör dashboard'dan onayla() çağırır → JWT token üretilir
  6. ESP32 GET /api/v1/provisioning/durum/{talep_id} ile 10sn'de bir poll eder
  7. Token gelince EEPROM'a kaydeder, AP modu kapanır
  8. Bundan sonra JWT token (username=cihaz_id, password=token) ile bağlanır

JWT:
  - HS256 algoritması, stdlib hmac+hashlib — harici bağımlılık yok
  - 30 yıl geçerlilik (pratik olarak kalıcı; yenileme zorlamak için sifirla() var)
  - Payload: sub, cihaz_id, sera_id, tesis_kodu, iat, exp
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sera_ai.domain.models import CihazKimlik, CihazKayit
from ..repositories.cihaz_repository import SQLiteCihazRepository
from ..mqtt.broker_auth import yazma_konulari_olustur

# 30 yıl saniye cinsinden
_OTUZ_YIL_SN = 30 * 365 * 24 * 3600


# ──────────────────────────────────────────────────────────────
# JWT (minimal HS256 — stdlib only)
# ──────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_dec(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def jwt_uret(payload: dict, secret: str) -> str:
    """HS256 JWT üret."""
    hdr = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    bdy = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    msg = f"{hdr}.{bdy}"
    sig = _b64url(
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    )
    return f"{msg}.{sig}"


def jwt_dogrula(token: str, secret: str) -> Optional[dict]:
    """
    HS256 JWT doğrula.
    Returns: payload dict veya None (geçersiz imza / süresi dolmuş / hatalı format)
    """
    try:
        hdr, bdy, sig = token.split(".")
        msg = f"{hdr}.{bdy}"
        beklenen = _b64url(
            hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, beklenen):
            return None
        payload = json.loads(_b64url_dec(bdy))
        if payload.get("exp", float("inf")) < time.time():
            return None
        return payload
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# Provisioning Talep Modeli
# ──────────────────────────────────────────────────────────────

@dataclass
class ProvisioningTalep:
    """
    Bir ESP32'den gelen kayıt isteği.

    durum: BEKLEMEDE → onaylanmayı bekliyor
           ONAYLANDI → token üretildi, ESP32'ye gönderilecek
           REDDEDILDI → talep reddedildi
    """
    talep_id:          str
    mac_adresi:        str
    sera_id:           str
    baglanti_tipi:     str
    firmware_versiyon: str
    talep_zamani:      datetime
    durum:             str = "BEKLEMEDE"
    cihaz_id:          str = ""

    def to_dict(self) -> dict:
        return {
            "talep_id":          self.talep_id,
            "mac_adresi":        self.mac_adresi,
            "sera_id":           self.sera_id,
            "baglanti_tipi":     self.baglanti_tipi,
            "firmware_versiyon": self.firmware_versiyon,
            "talep_zamani":      self.talep_zamani.isoformat(),
            "durum":             self.durum,
            "cihaz_id":          self.cihaz_id,
        }

    def sure_gecti_mi(self, dakika: int = 30) -> bool:
        """Talep belirtilen dakika süresi içinde onaylanmadıysa True."""
        return (datetime.now() - self.talep_zamani).total_seconds() > dakika * 60


# ──────────────────────────────────────────────────────────────
# Zero-Touch Provisioning Servisi
# ──────────────────────────────────────────────────────────────

class ZeroTouchProvisioning:
    """
    ESP32 sıfır-dokunuş kayıt servisi.

    Kullanım:
        prov = ZeroTouchProvisioning(repo, jwt_secret="gizli", tesis_kodu="IST01")

        # ESP32'den talep gelir:
        talep = prov.yeni_kayit_bekle("A4:CF:12:78:5B:09", "s1", "WiFi")

        # Dashboard'dan onaylanır:
        cihaz, token = prov.onayla(talep.talep_id)

        # ESP32 poll edince token'ı alır:
        durum = prov.durum_al(talep.talep_id)
        # {"durum": "ONAYLANDI", "cihaz_id": "SERA-IST01-001", "token": "..."}

        # MQTT bağlantısında token doğrula:
        cihaz = prov.token_dogrula(token)
    """

    def __init__(
        self,
        repo: SQLiteCihazRepository,
        jwt_secret: str,
        tesis_kodu: str = "IST01",
    ) -> None:
        self._repo        = repo
        self._jwt_secret  = jwt_secret
        self._tesis_kodu  = tesis_kodu
        self._talepler:    dict[str, ProvisioningTalep] = {}
        self._token_cache: dict[str, str] = {}   # talep_id → JWT token
        self._lock = threading.Lock()

    # ── ESP32 tarafından çağrılanlar ──────────────────────────

    def yeni_kayit_bekle(
        self,
        mac_adresi:        str,
        sera_id:           str,
        baglanti_tipi:     str = "WiFi",
        firmware_versiyon: str = "1.0.0",
    ) -> ProvisioningTalep:
        """
        Yeni kayıt talebi oluştur.
        ESP32 kurulum sonrası bu metodu çağırır (API üzerinden).
        """
        talep_id = str(uuid.uuid4())
        talep = ProvisioningTalep(
            talep_id=talep_id,
            mac_adresi=mac_adresi,
            sera_id=sera_id,
            baglanti_tipi=baglanti_tipi,
            firmware_versiyon=firmware_versiyon,
            talep_zamani=datetime.now(),
        )
        with self._lock:
            self._talepler[talep_id] = talep
        return talep

    def durum_al(self, talep_id: str) -> Optional[dict]:
        """
        Talep durumunu döndür.
        ESP32 bunu 10 saniyede bir poll eder.
        ONAYLANDI ise token da dahil edilir.
        """
        with self._lock:
            t = self._talepler.get(talep_id)
        if t is None:
            return None
        result: dict = {"durum": t.durum, "talep_id": talep_id}
        if t.durum == "ONAYLANDI":
            result["cihaz_id"] = t.cihaz_id
            result["token"]    = self._token_cache.get(talep_id, "")
        return result

    # ── Dashboard tarafından çağrılanlar ──────────────────────

    def onayla(self, talep_id: str) -> Optional[tuple[CihazKimlik, str]]:
        """
        Kayıt talebini onayla.
        Cihaz ID otomatik üretilir, JWT token oluşturulur.

        Returns:
            (CihazKimlik, jwt_token) veya None (talep bulunamadı / zaten işlendi)
        """
        with self._lock:
            talep = self._talepler.get(talep_id)
            if talep is None or talep.durum != "BEKLEMEDE":
                return None

            # Cihaz ID üret
            sira     = self._repo.tesis_cihaz_sayisi(self._tesis_kodu) + 1
            cihaz_id = f"SERA-{self._tesis_kodu}-{sira:03d}"
            seri_no  = uuid.uuid4().hex[:12].upper()

            cihaz = CihazKimlik(
                cihaz_id=cihaz_id,
                tesis_kodu=self._tesis_kodu,
                sera_id=talep.sera_id,
                seri_no=seri_no,
                mac_adresi=talep.mac_adresi,
                baglanti_tipi=talep.baglanti_tipi,
                firmware_versiyon=talep.firmware_versiyon,
                son_gorulen=datetime.now(),
                aktif=True,
            )

            # JWT token üret
            token = self._token_uret(cihaz)

            # DB kaydet (sifre_hash boş → token-based auth)
            izin_verilen = yazma_konulari_olustur(
                self._tesis_kodu, talep.sera_id, cihaz_id
            )
            kayit = CihazKayit(
                cihaz_id=cihaz_id,
                sifre_hash="",         # token-based — şifre hash'i kullanılmıyor
                izin_verilen_konular=izin_verilen,
            )
            self._repo.kayit_et(cihaz, kayit)

            # Durum güncelle
            talep.durum    = "ONAYLANDI"
            talep.cihaz_id = cihaz_id
            self._token_cache[talep_id] = token

            return cihaz, token

    def reddet(self, talep_id: str) -> bool:
        """
        Kayıt talebini reddet.
        Returns: True → reddedildi, False → bulunamadı / zaten işlendi
        """
        with self._lock:
            talep = self._talepler.get(talep_id)
            if talep is None or talep.durum != "BEKLEMEDE":
                return False
            talep.durum = "REDDEDILDI"
            return True

    def bekleyen_listele(self) -> list[ProvisioningTalep]:
        """BEKLEMEDE durumundaki tüm talepleri döndür."""
        with self._lock:
            return [t for t in self._talepler.values() if t.durum == "BEKLEMEDE"]

    def tum_talepler_listele(self) -> list[ProvisioningTalep]:
        """Tüm talepleri (tüm durumlarda) döndür."""
        with self._lock:
            return list(self._talepler.values())

    def talep_bul(self, talep_id: str) -> Optional[ProvisioningTalep]:
        with self._lock:
            return self._talepler.get(talep_id)

    # ── MQTT Token Auth ────────────────────────────────────────

    def token_dogrula(self, token: str) -> Optional[CihazKimlik]:
        """
        JWT token'ı doğrula.
        Returns: CihazKimlik veya None (geçersiz/süresi dolmuş token)
        """
        payload = jwt_dogrula(token, self._jwt_secret)
        if payload is None:
            return None
        cihaz_id = payload.get("cihaz_id") or payload.get("sub")
        if not cihaz_id:
            return None
        return self._repo.bul(cihaz_id)

    def token_yenile(self, cihaz_id: str) -> Optional[str]:
        """Mevcut cihaz için yeni JWT token üret."""
        cihaz = self._repo.bul(cihaz_id)
        if cihaz is None:
            return None
        return self._token_uret(cihaz)

    # ── İç yardımcılar ────────────────────────────────────────

    def _token_uret(self, cihaz: CihazKimlik) -> str:
        now = int(time.time())
        payload = {
            "sub":        cihaz.cihaz_id,
            "cihaz_id":   cihaz.cihaz_id,
            "sera_id":    cihaz.sera_id,
            "tesis_kodu": cihaz.tesis_kodu,
            "iat":        now,
            "exp":        now + _OTUZ_YIL_SN,
        }
        return jwt_uret(payload, self._jwt_secret)
