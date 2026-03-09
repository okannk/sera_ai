"""
Repository Soyut Temel Sınıfı

Neden ABC?
  Şu an SQLite; ileride InfluxDB, PostgreSQL veya başka bir şey.
  Kod bu arayüzü konuşur → depolama değişse uygulama kodu değişmez.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sera_ai.domain.models import SensorOkuma, KomutSonucu


class SensorRepository(ABC):
    """Sensör okumalarını kalıcı hale getirir."""

    @abstractmethod
    def kaydet(self, okuma: SensorOkuma) -> None:
        """Tek bir sensör okuması yazar."""

    @abstractmethod
    def toplu_kaydet(self, okumalar: list[SensorOkuma]) -> None:
        """Birden fazla okuması tek transaction'da yazar."""

    @abstractmethod
    def son_okuma(self, sera_id: str) -> Optional[SensorOkuma]:
        """Belirtilen sera'nın en son okumasını döner; yoksa None."""

    @abstractmethod
    def aralik_oku(
        self,
        sera_id: str,
        baslangic: datetime,
        bitis: datetime,
    ) -> list[SensorOkuma]:
        """Zaman aralığındaki okumaları kronolojik sırayla döner."""

    @abstractmethod
    def tum_seralar(self) -> list[str]:
        """Veritabanında kaydı olan tüm sera_id'lerini döner."""

    @abstractmethod
    def temizle(self, sera_id: str, oncesi: datetime) -> int:
        """Belirtilen tarihten eski kayıtları siler. Silinen satır sayısını döner."""


class KomutRepository(ABC):
    """Komut geçmişini kalıcı hale getirir."""

    @abstractmethod
    def kaydet(self, sera_id: str, sonuc: KomutSonucu) -> None:
        """Tek bir komut sonucu yazar."""

    @abstractmethod
    def gecmis(
        self,
        sera_id: str,
        limit: int = 100,
    ) -> list[KomutSonucu]:
        """Belirtilen sera'nın son N komutunu yeni→eski sırayla döner."""

    @abstractmethod
    def basarisiz_sayisi(self, sera_id: str, son_n_dk: int = 60) -> int:
        """Son N dakikadaki başarısız komut sayısını döner (dashboard için)."""
