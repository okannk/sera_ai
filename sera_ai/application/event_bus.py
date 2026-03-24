"""
Event Bus — Modüller Arası İletişim

Neden event bus?
  Kontrol motoru bildirim sisteminin varlığından haberdar olmamalı.
  "Durum değişti" olayını yayınlar — dinleyen dinler.
  Modüller birbirini import etmez → test edilebilir, değiştirilebilir.

Olaylar:
  SENSOR_OKUMA   → DB kaydı, dashboard güncelleme
  DURUM_DEGISTI  → Bildirim gönderme, log
  KOMUT_GONDERILDI → Audit log
  CB_ACILDI      → Operatör uyarısı
  SISTEM_HATASI  → Kritik alarm
"""
from __future__ import annotations

from enum import Enum
from typing import Callable


class OlayTur(Enum):
    SENSOR_OKUMA     = "sensor_okuma"
    DURUM_DEGISTI    = "durum_degisti"
    KOMUT_GONDERILDI = "komut_gonderildi"
    CB_ACILDI        = "cb_acildi"
    CB_KAPANDI       = "cb_kapandi"
    SISTEM_HATASI    = "sistem_hatasi"
    HASTALIK_TESPIT  = "hastalik_tespit"   # Hastalık tespit edildi (bildirim/log)
    HASTALIK_KRITIK  = "hastalik_kritik"   # Yanıklık gibi acil müdahale gerektiren


class EventBus:
    """
    Senkron Publish/Subscribe.

    Neden senkron?
      Async/await tüm kodu etkiler — pyserial, paho-mqtt zaten
      thread tabanlı çalışıyor. Senkron bus daha az karmaşıklık.
      Performans kritik değil (2.5s döngü periyodu var).

    Hata izolasyonu:
      Bir abone exception fırlatırsa diğerleri etkilenmez.
      Hata yakalanır ve kaydedilir ama sistem devam eder.
    """

    def __init__(self):
        self._aboneler: dict[OlayTur, list[Callable[[dict], None]]] = {}

    def abone_ol(self, olay: OlayTur, fn: Callable[[dict], None]) -> None:
        """
        Bir olay türüne abone ol.
        fn(veri: dict) — olay gerçekleşince çağrılır.
        """
        self._aboneler.setdefault(olay, []).append(fn)

    def yayinla(self, olay: OlayTur, veri: dict) -> None:
        """
        Olayı tüm abonelere ilet.
        Bir abone çökerse diğerleri etkilenmez.
        """
        for fn in self._aboneler.get(olay, []):
            try:
                fn(veri)
            except Exception as e:
                # Abone hatası sistemi durdurmamalı
                print(f"[EventBus] Abone hatası ({olay.name}): {e}")

    def abone_sayisi(self, olay: OlayTur) -> int:
        return len(self._aboneler.get(olay, []))
