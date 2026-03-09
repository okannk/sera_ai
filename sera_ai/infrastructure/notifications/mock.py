"""
Mock Bildirim Kanalı — Test ve Demo İçin

Gerçek token/ağ olmadan bildirimleri test eder.
Gönderilen mesajlar bellekte tutulur → assertion'lar için.

Kullanım:
    kanal = MockBildirimKanal()
    dispatcher = BildirimDispatcher([kanal], konfig, olay_bus)
    dispatcher.baslat()
    # ... olaylar tetiklenir ...
    assert len(kanal.gonderilen) == 1
    assert kanal.gonderilen[0].oncelik == BildirimOncelik.ALARM
"""
from __future__ import annotations

from .base import Bildirim, BildirimKanalBase


class MockBildirimKanal(BildirimKanalBase):
    """
    Test kanalı — her zaman aktif, her zaman başarılı.

    hata_orani > 0 ile başarısızlık senaryoları da test edilebilir.
    """

    def __init__(self, hata_orani: float = 0.0) -> None:
        self.hata_orani = hata_orani
        self.gonderilen: list[Bildirim] = []
        self.hata_sayisi: int = 0

    @property
    def aktif_mi(self) -> bool:
        return True

    @property
    def kanal_adi(self) -> str:
        return "Mock"

    def gonder(self, bildirim: Bildirim) -> bool:
        import random
        if random.random() < self.hata_orani:
            self.hata_sayisi += 1
            return False
        self.gonderilen.append(bildirim)
        return True

    def temizle(self) -> None:
        """Test teardown için."""
        self.gonderilen.clear()
        self.hata_sayisi = 0
