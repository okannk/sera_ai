"""
Durum Makinesi — Her sera bağımsız bir durumda yaşar.

Neden state machine?
  if/elif yığını yerine açık durumlar:
  - Geçiş anı loglanır: "NORMAL → ALARM, sebep: T=34°C, tx=a3f2"
  - Geçiş koşulları tek yerde → test edilebilir
  - "Sistem neden alarm verdi?" sorusu gecmis listesiyle yanıtlanır

Durum hiyerarşisi (kötüden iyiye):
  BASLATILAMADI → NORMAL → UYARI → ALARM → ACİL_DURDUR
  MANUEL_KONTROL (operatör kararı — otomatik geçiş askıya alınır)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import BitkilProfili, SensorOkuma
    from ..application.event_bus import EventBus


class Durum(Enum):
    BASLATILAMADI  = auto()   # Henüz sensör okuma yok
    NORMAL         = auto()   # Tüm parametreler optimal bantta
    UYARI          = auto()   # Bir parametre optimal dışında, güvenli bantta
    ALARM          = auto()   # Güvenli bant aşıldı — otomatik eylem devreye girer
    ACIL_DURDUR    = auto()   # Kritik eşik — tüm aktüatörler kapatılır
    MANUEL_KONTROL = auto()   # Operatör devreye girdi — otomatik kontrol durur


@dataclass
class DurumGecisi:
    """
    Her geçiş kalıcı kayıttır.
    Neden: "Sistem neden alarm verdi?" sorusunun cevabı burada.
    """
    onceki:  Durum
    yeni:    Durum
    sebep:   str
    sensor:  Optional["SensorOkuma"]
    zaman:   datetime = field(default_factory=datetime.now)


class SeraStateMachine:
    """
    Tek sera için durum yönetimi.
    Profil değerleri → geçiş eşikleri (hardcoded değil).
    """

    # Optimal değerden sapma eşikleri (sıcaklık için °C)
    UYARI_MARJ = 3.0
    ALARM_MARJ = 6.0
    ACIL_MARJ  = 10.0

    def __init__(self, sera_id: str, profil: "BitkilProfili",
                 olay_bus: Optional["EventBus"] = None):
        self.sera_id  = sera_id
        self.profil   = profil
        self.olay_bus = olay_bus
        self._durum   = Durum.BASLATILAMADI
        self.gecmis:  list[DurumGecisi] = []

    @property
    def durum(self) -> Durum:
        return self._durum

    def guncelle(self, sensor: "SensorOkuma") -> Durum:
        """
        Sensör okuma → yeni durum hesapla → gerekirse geçiş yap.
        MANUEL_KONTROL'daysa otomatik geçiş yapma.
        """
        if self._durum == Durum.MANUEL_KONTROL:
            return self._durum

        yeni_durum, sebep = self._hesapla(sensor)
        if yeni_durum != self._durum:
            self._gecis_yap(yeni_durum, sebep, sensor)
        return self._durum

    def _hesapla(self, s: "SensorOkuma") -> tuple[Durum, str]:
        """
        Kural tabanlı durum hesaplama.
        Sıcaklık en kritik parametre — önce kontrol edilir.
        """
        p = self.profil

        # ── Sıcaklık ──────────────────────────────────────────
        T_sapma = abs(s.T - p.opt_T)
        if T_sapma > self.ACIL_MARJ or s.T > p.max_T + 5 or s.T < p.min_T - 5:
            return (Durum.ACIL_DURDUR,
                    f"Kritik sıcaklık: {s.T}°C (opt: {p.opt_T}°C, eşik: ±{self.ACIL_MARJ})")
        if T_sapma > self.ALARM_MARJ or s.T > p.max_T or s.T < p.min_T:
            return (Durum.ALARM,
                    f"Alarm sıcaklık: {s.T}°C (güvenli bant: {p.min_T}-{p.max_T}°C)")
        if T_sapma > self.UYARI_MARJ:
            return (Durum.UYARI,
                    f"Uyarı sıcaklık: {s.T}°C (opt: {p.opt_T}°C)")

        # ── Nem ───────────────────────────────────────────────
        if s.H > 95 or s.H < 30:
            return (Durum.ALARM,
                    f"Alarm nem: %{s.H} (kritik bant dışı)")
        if s.H > p.max_H or s.H < p.min_H:
            return (Durum.UYARI,
                    f"Uyarı nem: %{s.H} (bant: {p.min_H}-{p.max_H}%)")

        # ── CO₂ ───────────────────────────────────────────────
        if s.co2 > 2000 or s.co2 < 200:
            return (Durum.ALARM,
                    f"Alarm CO₂: {s.co2} ppm")

        return Durum.NORMAL, "Tüm parametreler optimal bantta"

    def _gecis_yap(self, yeni: Durum, sebep: str, sensor: Optional["SensorOkuma"]):
        gecis = DurumGecisi(self._durum, yeni, sebep, sensor)
        self.gecmis.append(gecis)
        self._durum = yeni

        # Event bus'a yayınla — bildirim sistemi dinler
        if self.olay_bus:
            from ..application.event_bus import OlayTur
            self.olay_bus.yayinla(OlayTur.DURUM_DEGISTI, {
                "sera_id": self.sera_id,
                "onceki":  gecis.onceki.name,
                "yeni":    yeni.name,
                "sebep":   sebep,
                "tx_id":   sensor.tx_id if sensor else None,
            })

    def manuel_devral(self, sebep: str = "Operatör kararı"):
        """Operatör otomatik sistemi devre dışı bırakıyor."""
        self._gecis_yap(Durum.MANUEL_KONTROL, sebep, None)

    def otomatiğe_don(self, sensor: "SensorOkuma"):
        """Operatör otomatik kontrolü iade ediyor."""
        self._durum = Durum.NORMAL  # Sıfırla, sonra sensörle güncelle
        self.guncelle(sensor)
