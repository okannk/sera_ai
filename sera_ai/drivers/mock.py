"""
Mock Saha Node — Test ve Demo İçin

Gerçek donanım olmadan tam sistemi test etmek için.
Sensör değerleri fizyolojik drift modeli ile üretilir —
random.random() değil, gerçek sera davranışını taklit eder.

Kullanım:
    node = MockSahaNode(sera_id="s1", profil=DOMATES_PROFİL)
    node.baglan()
    okuma = node.sensor_oku("s1")
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .base import SahaNodeBase
from ..domain.models import BitkilProfili, Komut, SensorOkuma


@dataclass
class MockDurum:
    """Bir seranın simüle edilen anlık fiziksel durumu."""
    T:   float
    H:   float
    co2: float
    # Aktüatör durumları — idempotent test için
    sulama_acik:  bool = False
    isitici_acik: bool = False
    sogutma_acik: bool = False
    fan_acik:     bool = False


class MockSahaNode(SahaNodeBase):
    """
    Gerçek donanım olmadan çalışan test node'u.

    Özellikler:
      - Profil bazlı başlangıç değerleri (Domates → 23°C, Marul → 16°C)
      - Gaussian drift: değerler zaman içinde doğal sapma gösterir
      - %3 timeout simülasyonu: gerçek hata senaryolarını test eder
      - %5 komut ret simülasyonu: CB testleri için
      - Gönderilen komutlar kaydedilir → test assertion'ları için

    Test kullanımı:
        node = MockSahaNode("s1", profil, hata_orani=0)  # Hatasız mod
        node.baglan()
        okuma = node.sensor_oku("s1")
        assert okuma.gecerli_mi
        node.komut_gonder(Komut.FAN_BASLAT)
        assert node.komutlar[-1] == Komut.FAN_BASLAT
    """

    def __init__(self, sera_id: str, profil: BitkilProfili,
                 sensor_hata_orani: float = 0.03,
                 komut_hata_orani:  float = 0.05):
        self.sera_id          = sera_id
        self.profil           = profil
        self.sensor_hata_orani = sensor_hata_orani
        self.komut_hata_orani  = komut_hata_orani
        self._baglandı        = False
        # Gönderilen komutların kaydı — test assertion'ları için
        self.komutlar: list[Komut] = []
        # Fiziksel simülasyon durumu
        self._durum = MockDurum(
            T=profil.opt_T,
            H=(profil.min_H + profil.max_H) / 2,
            co2=float(profil.opt_CO2),
        )

    def baglan(self) -> bool:
        self._baglandı = True
        return True

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        if not self._baglandı:
            raise IOError(f"[{self.sera_id}] Bağlantı yok — baglan() çağrılmadı")

        # Sensör timeout simülasyonu
        if random.random() < self.sensor_hata_orani:
            raise IOError(f"[{self.sera_id}] Sensör okuma timeout (simüle)")

        self._fizik_adimi()

        return SensorOkuma(
            sera_id=sera_id,
            T=round(self._durum.T, 1),
            H=round(self._durum.H, 1),
            co2=int(self._durum.co2),
            isik=random.randint(200, 900),
            toprak_nem=random.randint(300, 700),
            ph=round(random.uniform(5.8, 7.2), 2),
            ec=round(random.uniform(1.4, 2.8), 2),
        )

    def komut_gonder(self, komut: Komut) -> bool:
        if not self._baglandı:
            raise IOError(f"[{self.sera_id}] Bağlantı yok")

        # Komut ret simülasyonu (CB testleri için)
        if random.random() < self.komut_hata_orani:
            raise IOError(f"[{self.sera_id}] Komut yanıtsız: {komut.value} (simüle)")

        # Aktüatör durumunu güncelle (simülasyon gerçekçiliği)
        self._aktüatör_güncelle(komut)
        self.komutlar.append(komut)
        return True

    def kapat(self):
        self._baglandı = False

    # ── Simülasyon iç işleri ──────────────────────────────────

    def _fizik_adimi(self):
        """
        Gaussian drift ile gerçekçi sensör davranışı.
        Aktüatörler açıksa fizik buna göre şekillenir.
        """
        d = self._durum
        p = self.profil

        # Temel drift (termal gürültü + dış etkenler)
        d.T   += random.gauss(0, 0.15)
        d.H   += random.gauss(0, 0.25)
        d.co2 += random.gauss(0, 10)

        # Aktüatör etkileri
        if d.sogutma_acik: d.T   -= 0.3
        if d.isitici_acik: d.T   += 0.4
        if d.fan_acik:     d.H   -= 0.2
        if d.sulama_acik:  d.H   += 0.3

        # Fiziksel sınırlar
        d.T   = max(5,   min(45,   d.T))
        d.H   = max(20,  min(98,   d.H))
        d.co2 = max(300, min(2000, d.co2))

    def _aktüatör_güncelle(self, komut: Komut):
        d = self._durum
        mapping = {
            Komut.SULAMA_BASLAT:  lambda: setattr(d, "sulama_acik",  True),
            Komut.SULAMA_DURDUR:  lambda: setattr(d, "sulama_acik",  False),
            Komut.ISITICI_BASLAT: lambda: setattr(d, "isitici_acik", True),
            Komut.ISITICI_DURDUR: lambda: setattr(d, "isitici_acik", False),
            Komut.SOGUTMA_BASLAT: lambda: setattr(d, "sogutma_acik", True),
            Komut.SOGUTMA_DURDUR: lambda: setattr(d, "sogutma_acik", False),
            Komut.FAN_BASLAT:     lambda: setattr(d, "fan_acik",     True),
            Komut.FAN_DURDUR:     lambda: setattr(d, "fan_acik",     False),
            Komut.ACIL_DURDUR:    self._acil_kapat,
        }
        if komut in mapping:
            mapping[komut]()

    def _acil_kapat(self):
        d = self._durum
        d.sulama_acik = d.isitici_acik = d.sogutma_acik = d.fan_acik = False

    def __repr__(self) -> str:
        return (
            f"MockSahaNode({self.sera_id}, "
            f"T={self._durum.T:.1f}°C, "
            f"bağlı={self._baglandı})"
        )
