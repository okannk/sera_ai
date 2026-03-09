"""
Mock Log Yazıcı — Test ve Demo İçin

Bellekte tutar, dosya/ağ gerektirmez.
"""
from __future__ import annotations

from .base import LogKayit, LogSeviye, LogYaziciBase


class MockLogger(LogYaziciBase):
    """
    Test logger — gelen kayıtları bellekte saklar.

    Kullanım:
        logger = MockLogger()
        dispatcher.yaz(LogKayit(...))
        assert len(logger.kayitlar) == 1
        assert logger.kayitlar[0].seviye == LogSeviye.ALARM
    """

    def __init__(self) -> None:
        self.kayitlar: list[LogKayit] = []

    def yaz(self, kayit: LogKayit) -> None:
        self.kayitlar.append(kayit)

    def temizle(self) -> None:
        self.kayitlar.clear()

    def seviyeye_gore_filtrele(self, seviye: LogSeviye) -> list[LogKayit]:
        return [k for k in self.kayitlar if k.seviye == seviye]

    def olaya_gore_filtrele(self, olay: str) -> list[LogKayit]:
        return [k for k in self.kayitlar if k.olay == olay]
