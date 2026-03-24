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
    T:          float
    H:          float
    co2:        float
    isik:       float   # lux — sabah/akşam döngüsü
    toprak_nem: float   # ADC 0-1023
    ph:         float   # çözelti pH
    ec:         float   # elektriksel iletkenlik mS/cm
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
        # Fiziksel simülasyon durumu — gerçekçi başlangıç değerleri
        self._durum = MockDurum(
            T=profil.opt_T,
            H=(profil.min_H + profil.max_H) / 2,
            co2=float(profil.opt_CO2),
            isik=float(profil.opt_isik // 2),
            toprak_nem=500.0,
            ph=profil.opt_pH,
            ec=profil.opt_EC,
        )
        self._adim_sayaci = 0  # ışık döngüsü için

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
            isik=int(self._durum.isik),
            toprak_nem=int(self._durum.toprak_nem),
            ph=round(self._durum.ph, 2),
            ec=round(self._durum.ec, 2),
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
        Gerçekçi sera simülasyonu: mean-reversion + küçük Gaussian gürültü.

        Tasarım kararları:
        - Mean-reversion: değerler her adımda optimal'a doğru çekilir.
          Bu, sonsuz drift'i önler ve sensörü gerçek kontrol döngüsüne benzetir.
        - Gürültü std çok küçük (0.06°C) → ölçüm gürültüsü, fiziksel olay değil.
        - Demo'da UYARI çıkabilir ama ACİL_DURDUR çıkmaz:
          T sınırları opt ± 2.5°C (KuralMotoru UYARI eşiği opt ± 2°C'dir).
        - Aktüatör etkileri gerçekçi: ısıtıcı +0.2°C/adım, fan H -0.15%/adım.
        """
        self._adim_sayaci += 1
        d = self._durum
        p = self.profil

        opt_T   = p.opt_T
        opt_H   = (p.min_H + p.max_H) / 2
        opt_co2 = float(p.opt_CO2)

        # ── Sıcaklık ──────────────────────────────────────────
        # Mean-reversion katsayısı 0.04 → ~25 adımda yarıya döner
        d.T += (opt_T - d.T) * 0.04 + random.gauss(0, 0.06)
        if d.sogutma_acik: d.T -= 0.20
        if d.isitici_acik: d.T += 0.25
        # Demo sınırı: opt ± 2.5°C → UYARI mümkün, ACİL_DURDUR imkânsız
        d.T = max(opt_T - 2.5, min(opt_T + 2.5, d.T))

        # ── Nem ───────────────────────────────────────────────
        d.H += (opt_H - d.H) * 0.03 + random.gauss(0, 0.12)
        if d.fan_acik:    d.H -= 0.15
        if d.sulama_acik: d.H += 0.20
        d.H = max(p.min_H - 2, min(p.max_H + 2, d.H))

        # ── CO₂ ───────────────────────────────────────────────
        d.co2 += (opt_co2 - d.co2) * 0.05 + random.gauss(0, 6)
        # CO₂ aralığı: opt ± 120 ppm
        d.co2 = max(opt_co2 - 120, min(opt_co2 + 120, d.co2))

        # ── Toprak Nemi (ADC) ─────────────────────────────────
        # 400-600 ADC arası, mean-reversion 500'e
        d.toprak_nem += (500 - d.toprak_nem) * 0.02 + random.gauss(0, 3)
        if d.sulama_acik: d.toprak_nem += 5
        d.toprak_nem = max(380, min(620, d.toprak_nem))

        # ── Işık (lux) — sabah/akşam sinüs döngüsü ───────────
        import math as _math
        # 120 adımda bir tam döngü (simülasyon hızına bağlı)
        faz = _math.sin(self._adim_sayaci * _math.pi / 60)
        opt_isik = p.opt_isik
        d.isik = opt_isik * (0.5 + 0.5 * max(0, faz)) + random.gauss(0, opt_isik * 0.02)
        d.isik = max(p.min_isik, min(p.max_isik, d.isik))

        # ── pH ────────────────────────────────────────────────
        d.ph += (p.opt_pH - d.ph) * 0.02 + random.gauss(0, 0.02)
        d.ph = max(p.min_pH, min(p.max_pH, d.ph))

        # ── EC ────────────────────────────────────────────────
        d.ec += (p.opt_EC - d.ec) * 0.02 + random.gauss(0, 0.03)
        d.ec = max(p.min_EC, min(p.max_EC, d.ec))

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
