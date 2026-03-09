"""
Kontrol Motoru — Sensörden Komuta

Neden bu katman?
  State machine "durumu" bilir.
  Kontrol motoru "ne yapılacağını" bilir.
  Node "nasıl yapılacağını" bilir.
  Üçü birbirinden ayrı → test edilebilir.

Idempotent komut mantığı:
  "Sogutma zaten çalışıyor" → tekrar SOGUTMA_AC gönderme.
  Son aktüatör durumu önbellekte tutulur.
  Değişiklik yoksa komut gönderilmez → röle ömrü korunur, log temiz kalır.

Optimizer DI:
  optimizer=None → KuralMotoru (deterministik if/else, varsayılan)
  optimizer=<OptimizerBase> → ML modeli, RL ajanı, vb.
  KontrolMotoru hangisi olduğunu bilmez — sadece hedef_hesapla() çağırır.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .event_bus import EventBus, OlayTur
from ..domain.models import BitkilProfili, Komut, SensorOkuma
from ..domain.state_machine import Durum, SeraStateMachine
from ..domain.circuit_breaker import CircuitBreaker
from ..intelligence.base import OptimizerBase
from ..intelligence.kural_motoru import KuralMotoru

if TYPE_CHECKING:
    from ..drivers.base import SahaNodeBase


class KontrolMotoru:
    """
    Tek sera için sensör → karar → komut akışı.

    Bağımlılıklar (dependency injection):
      - SahaNodeBase   → donanım (interface, concrete değil)
      - CircuitBreaker → hata koruması
      - SeraStateMachine → durum yönetimi
      - EventBus       → olay yayınlama
      - OptimizerBase  → aktüatör hedef hesaplama (varsayılan: KuralMotoru)
    """

    def __init__(self, sera_id: str, profil: BitkilProfili,
                 node: "SahaNodeBase", cb: CircuitBreaker,
                 state_machine: SeraStateMachine, olay_bus: EventBus,
                 optimizer: Optional[OptimizerBase] = None):
        self.sera_id  = sera_id
        self.profil   = profil
        self.node     = node
        self.cb       = cb
        self.sm       = state_machine
        self.olay_bus = olay_bus
        self.optimizer = optimizer if optimizer is not None else KuralMotoru(profil)
        # Son gönderilen aktüatör durumları — idempotent için
        self._son_aktüatörler: dict[str, bool] = {}

    def adim_at(self, sensor: SensorOkuma) -> None:
        """
        Ana döngü adımı:
          1. Sensör geçerliliğini kontrol et
          2. State machine'i güncelle
          3. Optimizer'dan hedef aktüatör durumlarını al
          4. Değişen aktüatörler için komut gönder
        """
        if not sensor.gecerli_mi:
            self.olay_bus.yayinla(OlayTur.SISTEM_HATASI, {
                "sera_id": self.sera_id,
                "hata": f"Geçersiz sensör: T={sensor.T} H={sensor.H} co2={sensor.co2}",
                "tx_id": sensor.tx_id,
            })
            return

        durum = self.sm.guncelle(sensor)
        hedef = self.optimizer.hedef_hesapla(sensor, durum)

        for aktüatör, acik_mi in hedef.to_dict().items():
            if self._son_aktüatörler.get(aktüatör) != acik_mi:
                komut = self._komut_sec(aktüatör, acik_mi)
                self._komut_gonder(komut, sensor.tx_id)
                self._son_aktüatörler[aktüatör] = acik_mi

    def _komut_sec(self, aktüatör: str, ac: bool) -> Komut:
        tablo: dict[tuple[str, bool], Komut] = {
            ("sulama",  True):  Komut.SULAMA_BASLAT,
            ("sulama",  False): Komut.SULAMA_DURDUR,
            ("isitici", True):  Komut.ISITICI_BASLAT,
            ("isitici", False): Komut.ISITICI_DURDUR,
            ("sogutma", True):  Komut.SOGUTMA_BASLAT,
            ("sogutma", False): Komut.SOGUTMA_DURDUR,
            ("fan",     True):  Komut.FAN_BASLAT,
            ("fan",     False): Komut.FAN_DURDUR,
        }
        return tablo[(aktüatör, ac)]

    def _komut_gonder(self, komut: Komut, tx_id: str) -> None:
        try:
            self.cb.cagir(self.node.komut_gonder, komut)
            self.olay_bus.yayinla(OlayTur.KOMUT_GONDERILDI, {
                "sera_id": self.sera_id,
                "komut":   komut.value,
                "basarili": True,
                "tx_id":   tx_id,
            })
        except Exception as e:
            self.olay_bus.yayinla(OlayTur.SISTEM_HATASI, {
                "sera_id": self.sera_id,
                "komut":   komut.value,
                "hata":    str(e),
                "tx_id":   tx_id,
            })
