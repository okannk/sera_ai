"""
Bildirim Kanalı Soyut Temel Sınıfı

Neden ABC?
  Telegram, WhatsApp, e-posta — hepsi aynı arayüzü uygular.
  Dispatcher hangi kanalın olduğunu bilmez, sadece gonder() çağırır.
  Yeni kanal eklemek = bu dosyaya dokunmadan yeni sınıf yazmak.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class BildirimOncelik(Enum):
    """Mesaj önceliği — dispatcher bastırma kararında kullanır."""
    BILGI    = "bilgi"    # Günlük rapor, durum özeti
    UYARI    = "uyari"    # UYARI durumu
    ALARM    = "alarm"    # ALARM durumu
    KRITIK   = "kritik"   # ACİL_DURDUR, CB açıldı


@dataclass
class Bildirim:
    """Kanaldan bağımsız bildirim mesajı."""
    baslik:   str
    mesaj:    str
    oncelik:  BildirimOncelik = BildirimOncelik.BILGI
    sera_id:  str = ""


class BildirimKanalBase(ABC):
    """
    Tek bildirim kanalı arayüzü.

    Sözleşme:
      - gonder() → başarıda True, hata durumunda False (istisna fırlatmaz)
      - aktif_mi → konfig ve env var kontrolü (token yoksa False)
    """

    @abstractmethod
    def gonder(self, bildirim: Bildirim) -> bool:
        """Mesajı kanala ilet. Başarıda True döner."""

    @property
    @abstractmethod
    def aktif_mi(self) -> bool:
        """Kanal kullanıma hazır mı? (token var mı, konfig aktif mi?)"""

    @property
    @abstractmethod
    def kanal_adi(self) -> str:
        """İnsan okunabilir kanal adı (log için)."""
