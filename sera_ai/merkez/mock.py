"""
Mock Merkez — Test ve Entegrasyon Testleri İçin

Gerçek Raspberry Pi olmadan merkez katmanını test eder.
MockSahaNode'larla birlikte kullanılır.
"""
from __future__ import annotations

from typing import Optional

from .base import MerkezKontrolBase
from ..drivers.base import SahaNodeBase
from ..domain.models import Komut, SensorOkuma


class MockMerkez(MerkezKontrolBase):
    """
    Test amaçlı merkez implementasyonu.

    Özellikler:
      - Node'ları bellekte tutar
      - Komutları kaydeder (test assertion için)
      - Gerçek döngü yok — test kendi adımlarını yönetir

    Kullanım:
        merkez = MockMerkez()
        merkez.node_ekle("s1", MockSahaNode("s1", profil))
        merkez.baslat()
        okuma = merkez.sensor_oku("s1")
        merkez.komut_gonder("s1", Komut.FAN_BASLAT)
        assert ("s1", Komut.FAN_BASLAT) in merkez.komut_gecmisi
    """

    def __init__(self):
        self._nodes:        dict[str, SahaNodeBase] = {}
        self._son_okumallar: dict[str, SensorOkuma] = {}
        self._calisiyor:    bool = False
        # Gönderilen komutların kaydı — test assertion'ları için
        self.komut_gecmisi: list[tuple[str, Komut]] = []

    def node_ekle(self, sera_id: str, node: SahaNodeBase) -> None:
        self._nodes[sera_id] = node

    def baslat(self) -> None:
        for sera_id, node in self._nodes.items():
            node.baglan()
        self._calisiyor = True

    def durdur(self) -> None:
        self._calisiyor = False
        for node in self._nodes.values():
            node.kapat()

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        if sera_id not in self._nodes:
            raise KeyError(f"Bilinmeyen sera: {sera_id}")
        okuma = self._nodes[sera_id].sensor_oku(sera_id)
        self._son_okumallar[sera_id] = okuma
        return okuma

    def komut_gonder(self, sera_id: str, komut: Komut) -> bool:
        if sera_id not in self._nodes:
            return False
        try:
            sonuc = self._nodes[sera_id].komut_gonder(komut)
            self.komut_gecmisi.append((sera_id, komut))
            return sonuc
        except IOError:
            return False

    def tum_durum(self) -> dict:
        return {
            sera_id: {
                "durum":          "NORMAL",
                "sensor":         (
                    self._son_okumallar[sera_id].to_dict()
                    if sera_id in self._son_okumallar else None
                ),
                "cb":             "-",
                "son_guncelleme": None,
            }
            for sera_id, node in self._nodes.items()
        }
