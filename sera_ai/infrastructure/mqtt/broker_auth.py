"""
MQTT Broker Auth — Cihaz Kimlik Doğrulama ve Konu Kontrolü

Mosquitto (veya benzeri) broker'ın auth plugin'i bu sınıfı çağırır.
Şu an in-process çalışır; ileride HTTP auth plugin ile entegre edilir.

Konu yapısı:
  sera/{tesis}/{sera_id}/sensor   → cihaz yazar, merkez okur
  sera/{tesis}/{sera_id}/komut    → merkez yazar, cihaz okur
  sera/{tesis}/{sera_id}/durum    → cihaz yazar
  cihaz/{cihaz_id}/kalp_atisi    → cihaz yazar
  cihaz/{cihaz_id}/firmware      → merkez yazar, cihaz okur

Auth yöntemleri (öncelik sırasına göre):
  1. JWT token (Zero-Touch Provisioning'den gelen — önerilen)
  2. Şifre hash (eski CihazProvisioning — geriye dönük uyumlu)
"""
from __future__ import annotations

import hashlib
from typing import Optional, TYPE_CHECKING

from ..repositories.cihaz_repository import SQLiteCihazRepository

if TYPE_CHECKING:
    from ..provisioning.zero_touch import ZeroTouchProvisioning


class MQTTBrokerAuth:
    """
    MQTT broker kimlik doğrulama ve yetkilendirme.

    İki auth yöntemi destekler:
      1. JWT token: Zero-Touch Provisioning'den (zero_touch parametresi gerekir)
      2. Şifre hash: CihazProvisioning'den (eski/fallback)

    Kullanım:
        auth = MQTTBrokerAuth(repo, zero_touch=prov)
        ok = auth.kimlik_dogrula("SERA-IST01-001", "jwt.token.burada")
        izin = auth.konu_kontrolu("SERA-IST01-001", "sera/IST01/s1/sensor", yazma=True)
    """

    def __init__(
        self,
        repo: SQLiteCihazRepository,
        zero_touch: Optional["ZeroTouchProvisioning"] = None,
    ) -> None:
        self._repo        = repo
        self._zero_touch  = zero_touch

    def kimlik_dogrula(self, cihaz_id: str, sifre_veya_token: str) -> bool:
        """
        Cihaz ID + kimlik bilgisi doğru mu?

        Önce JWT token dener (noktalı format); başarısız olursa
        şifre hash'ini dener (eski yöntem — geriye dönük uyumlu).
        """
        # 1. JWT token denemesi (Zero-Touch Provisioning)
        if self._zero_touch and sifre_veya_token.count(".") == 2:
            cihaz = self._zero_touch.token_dogrula(sifre_veya_token)
            if cihaz is not None and cihaz.cihaz_id == cihaz_id:
                return True

        # 2. Şifre hash denemesi (eski yöntem)
        kayit = self._repo.kayit_bul(cihaz_id)
        if kayit is None or not kayit.sifre_hash:
            return False
        return _dogrula_sifre(sifre_veya_token, kayit.sifre_hash)

    def konu_kontrolu(self, cihaz_id: str, konu: str, yazma: bool = True) -> bool:
        """
        Cihazın belirtilen konuya yazma (veya okuma) yetkisi var mı?

        Yazma: sadece izin_verilen_konular listesindeki konular.
        Okuma: kendi komut ve firmware konuları.
        """
        cihaz = self._repo.bul(cihaz_id)
        if cihaz is None or not cihaz.aktif:
            return False

        kayit = self._repo.kayit_bul(cihaz_id)
        if kayit is None:
            return False

        if yazma:
            return konu in kayit.izin_verilen_konular

        # Okuma: kendi komut konusu + firmware
        okuma_konulari = _okuma_konulari(cihaz.tesis_kodu, cihaz.sera_id, cihaz_id)
        return konu in okuma_konulari


# ── Yardımcılar ────────────────────────────────────────────────

def _dogrula_sifre(sifre: str, sifre_hash: str) -> bool:
    """salt:hash formatındaki hash'i doğrula."""
    try:
        salt, h = sifre_hash.split(":", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + sifre).encode()).hexdigest() == h


def _okuma_konulari(tesis_kodu: str, sera_id: str, cihaz_id: str) -> list[str]:
    return [
        f"sera/{tesis_kodu}/{sera_id}/komut",
        f"cihaz/{cihaz_id}/firmware",
    ]


def yazma_konulari_olustur(tesis_kodu: str, sera_id: str, cihaz_id: str) -> list[str]:
    """Cihazın yazabileceği MQTT konuları — provisioning'de kullanılır."""
    return [
        f"sera/{tesis_kodu}/{sera_id}/sensor",
        f"sera/{tesis_kodu}/{sera_id}/durum",
        f"cihaz/{cihaz_id}/kalp_atisi",
    ]
