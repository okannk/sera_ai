"""
Telegram Bildirim Kanalı

Bot API üzerinden mesaj gönderir.
Token ve chat_id .env'den okunur — config.yaml'da sadece env var adları saklanır.

Kurulum:
    pip install httpx
    # veya pyproject.toml [notifications] extras ile

.env örneği:
    TELEGRAM_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=-100123456789

Kullanım:
    kanal = TelegramKanal(
        token_env="TELEGRAM_TOKEN",
        chat_id_env="TELEGRAM_CHAT_ID",
        aktif=True,
    )
    kanal.gonder(Bildirim("Alarm!", "Sera A çok sıcak", BildirimOncelik.ALARM))

httpx seçildi çünkü:
  - requests'ten daha modern, async-ready (gelecekte gerekirse)
  - paho, smbus2 gibi diğer optional dep'lerle tutarlı lazy import
"""
from __future__ import annotations

import os
from typing import Optional

from .base import Bildirim, BildirimKanalBase, BildirimOncelik

# Önceliğe göre Telegram emoji/prefix
_ONCELIK_SEMBOL: dict[BildirimOncelik, str] = {
    BildirimOncelik.BILGI:  "ℹ️",
    BildirimOncelik.UYARI:  "⚠️",
    BildirimOncelik.ALARM:  "🚨",
    BildirimOncelik.KRITIK: "🆘",
}

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramKanal(BildirimKanalBase):
    """
    Telegram Bot API ile mesaj gönderir.

    Thread-safe: httpx.post() blocking — senkron EventBus ile uyumlu.
    Timeout 5s — ağ gecikmesi kontrol döngüsünü bloke etmemeli.
    """

    TIMEOUT_SN = 5.0

    def __init__(
        self,
        token_env:   str  = "TELEGRAM_TOKEN",
        chat_id_env: str  = "TELEGRAM_CHAT_ID",
        aktif:       bool = False,
    ) -> None:
        self._token_env   = token_env
        self._chat_id_env = chat_id_env
        self._aktif_konfig = aktif

    @property
    def aktif_mi(self) -> bool:
        if not self._aktif_konfig:
            return False
        return bool(os.getenv(self._token_env)) and bool(os.getenv(self._chat_id_env))

    @property
    def kanal_adi(self) -> str:
        return "Telegram"

    def gonder(self, bildirim: Bildirim) -> bool:
        if not self.aktif_mi:
            return False

        token   = os.getenv(self._token_env, "")
        chat_id = os.getenv(self._chat_id_env, "")
        metin   = self._formatla(bildirim)

        try:
            import httpx
        except ImportError:
            print("[Telegram] httpx kurulu değil: pip install httpx")
            return False

        try:
            yanit = httpx.post(
                _TELEGRAM_API.format(token=token),
                json={"chat_id": chat_id, "text": metin, "parse_mode": "HTML"},
                timeout=self.TIMEOUT_SN,
            )
            if yanit.status_code == 200:
                return True
            print(f"[Telegram] API hatası: {yanit.status_code} — {yanit.text[:200]}")
            return False
        except Exception as e:
            print(f"[Telegram] Gönderim hatası: {e}")
            return False

    @staticmethod
    def _formatla(b: Bildirim) -> str:
        sembol = _ONCELIK_SEMBOL.get(b.oncelik, "📢")
        satirlar = [f"{sembol} <b>{b.baslik}</b>"]
        if b.sera_id:
            satirlar.append(f"🌿 Sera: <code>{b.sera_id}</code>")
        satirlar.append(b.mesaj)
        return "\n".join(satirlar)
