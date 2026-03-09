"""
Raspberry Pi 5 Merkez Kontrol — Şu An Kullanılan İmplementasyon

Tüm sera sisteminin beyni. Şu an Raspberry Pi 5'te çalışıyor.
Python sürecinde çalışır, asyncio yerine thread tabanlı döngü kullanır
(pyserial ve paho-mqtt zaten blocking — asyncio kazanımı minimal olur).

Sorumluluklar:
  1. SahaNode'larla bağlantı yönetimi
  2. Sensör okuma döngüsü (her sera ayrı CB korumalı)
  3. State machine → Kontrol motoru akışı
  4. Event bus üzerinden bildirim/veritabanı tetiklemesi
  5. Flask API için durum verisi sağlama
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from .base import MerkezKontrolBase
from ..drivers.base import SahaNodeBase
from ..domain.models import Komut, SensorOkuma, SistemKonfig, BitkilProfili
from ..domain.state_machine import SeraStateMachine, Durum
from ..domain.circuit_breaker import CircuitBreaker
from ..application.event_bus import EventBus, OlayTur
from ..application.control_engine import KontrolMotoru


class RaspberryPiMerkez(MerkezKontrolBase):
    """
    Raspberry Pi 5 üzerinde çalışan merkez kontrol sistemi.

    Tasarım kararları:
      - Her sera için bağımsız CircuitBreaker (Sera C arızalanınca
        Sera A ve B etkilenmez)
      - Kontrol döngüsü daemon thread — ana process ölünce o da ölür
      - Idempotent komutlar: son aktüatör durumu önbellekte,
        değişiklik yoksa komut gönderilmez (röle ömrü korunur)
    """

    def __init__(self, konfig: SistemKonfig, olay_bus: Optional[EventBus] = None):
        self.konfig    = konfig
        self.olay_bus  = olay_bus or EventBus()
        self._calisiyor = False
        self._dongu_thread: Optional[threading.Thread] = None

        # Node registry: sera_id → SahaNodeBase
        self._nodes:    dict[str, SahaNodeBase]     = {}
        # Bileşenler: sera_id → ilgili nesne
        self._cb_ler:   dict[str, CircuitBreaker]   = {}
        self._sm_ler:   dict[str, SeraStateMachine] = {}
        self._motorlar: dict[str, KontrolMotoru]    = {}
        # Anlık durum: API için thread-safe önbellek
        self._son_okumallar: dict[str, SensorOkuma] = {}
        self._son_guncelleme: dict[str, datetime]   = {}
        self._lock = threading.Lock()

    def node_ekle(self, sera_id: str, node: SahaNodeBase) -> None:
        """
        Sisteme sera ekle. baslat() öncesinde çağrılmalı.
        Her sera için CB, state machine ve kontrol motoru otomatik oluşturulur.
        """
        sera_konfig = next(
            (s for s in self.konfig.seralar if s.id == sera_id), None
        )
        if not sera_konfig:
            raise ValueError(f"config.yaml'da tanımlı değil: {sera_id}")

        profil = self.konfig.profil_al(sera_konfig.bitki)

        cb = CircuitBreaker(
            isim=f"cb_{sera_id}",
            hata_esigi=self.konfig.cb_hata_esigi,
            recovery_sn=self.konfig.cb_recovery_sn,
        )
        sm = SeraStateMachine(
            sera_id=sera_id,
            profil=profil,
            olay_bus=self.olay_bus,
        )
        motor = KontrolMotoru(
            sera_id=sera_id,
            profil=profil,
            node=node,
            cb=cb,
            state_machine=sm,
            olay_bus=self.olay_bus,
        )

        self._nodes[sera_id]    = node
        self._cb_ler[sera_id]   = cb
        self._sm_ler[sera_id]   = sm
        self._motorlar[sera_id] = motor

    def baslat(self) -> None:
        """Tüm node'lara bağlan ve kontrol döngüsünü başlat."""
        for sera_id, node in self._nodes.items():
            if not node.baglan():
                print(f"[MerkezRPi] Uyarı: {sera_id} node bağlantısı başarısız")

        self._calisiyor = True
        self._dongu_thread = threading.Thread(
            target=self._kontrol_dongusu,
            name="KontrolDongusu",
            daemon=True,
        )
        self._dongu_thread.start()

    def durdur(self) -> None:
        """Döngüyü durdur, node bağlantılarını kapat."""
        self._calisiyor = False
        if self._dongu_thread:
            self._dongu_thread.join(timeout=10)
        for node in self._nodes.values():
            node.kapat()

    def sensor_oku(self, sera_id: str) -> SensorOkuma:
        if sera_id not in self._nodes:
            raise KeyError(f"Bilinmeyen sera: {sera_id}")
        cb   = self._cb_ler[sera_id]
        node = self._nodes[sera_id]
        okuma = cb.cagir(node.sensor_oku, sera_id)
        with self._lock:
            self._son_okumallar[sera_id] = okuma
            self._son_guncelleme[sera_id] = datetime.now()
        return okuma

    def komut_gonder(self, sera_id: str, komut: Komut) -> bool:
        if sera_id not in self._nodes:
            return False
        cb   = self._cb_ler[sera_id]
        node = self._nodes[sera_id]
        try:
            cb.cagir(node.komut_gonder, komut)
            self.olay_bus.yayinla(OlayTur.KOMUT_GONDERILDI, {
                "sera_id": sera_id, "komut": komut.value,
            })
            return True
        except Exception:
            return False

    def tum_durum(self) -> dict:
        with self._lock:
            sonuc = {}
            for sera_id in self._nodes:
                okuma = self._son_okumallar.get(sera_id)
                sm    = self._sm_ler.get(sera_id)
                cb    = self._cb_ler.get(sera_id)
                sonuc[sera_id] = {
                    "durum":           sm.durum.name if sm else "BILINMIYOR",
                    "cb":              repr(cb) if cb else "-",
                    "son_guncelleme":  (
                        self._son_guncelleme[sera_id].isoformat()
                        if sera_id in self._son_guncelleme else None
                    ),
                    "sensor": okuma.to_dict() if okuma else None,
                }
            return sonuc

    # ── İç döngü ──────────────────────────────────────────────

    def _kontrol_dongusu(self):
        """
        Ana kontrol döngüsü — daemon thread içinde çalışır.
        Her iterasyonda tüm seralar için bir adım atar.
        """
        while self._calisiyor:
            for sera_id in list(self._nodes.keys()):
                self._sera_adimi(sera_id)
            time.sleep(self.konfig.sensor_interval_sn)

    def _sera_adimi(self, sera_id: str):
        """
        Tek sera için bir kontrol döngüsü adımı:
          1. Sensörü CB korumalı oku
          2. Event bus'a yayınla (DB kaydı için)
          3. Kontrol motorunu çalıştır (state machine + komut)
        """
        cb    = self._cb_ler[sera_id]
        motor = self._motorlar[sera_id]
        node  = self._nodes[sera_id]

        try:
            okuma = cb.cagir(node.sensor_oku, sera_id)
            with self._lock:
                self._son_okumallar[sera_id]  = okuma
                self._son_guncelleme[sera_id] = datetime.now()

            self.olay_bus.yayinla(OlayTur.SENSOR_OKUMA, okuma.to_dict())
            motor.adim_at(okuma)

        except RuntimeError as e:
            # Circuit breaker açık — bu sera atlanıyor
            print(f"[MerkezRPi:{sera_id}] {e}")
        except IOError as e:
            # Node yanıt vermedi — CB kendi sayacını zaten artırdı
            print(f"[MerkezRPi:{sera_id}] IO hatası: {e}")

    def calistir_blokla(self, max_adim: int = None):
        """
        Bloklayan mod — test veya CLI için.
        Üretimde systemd servis olarak çalışır (baslat() yeter).
        """
        self.baslat()
        try:
            adim = 0
            while max_adim is None or adim < max_adim:
                time.sleep(self.konfig.sensor_interval_sn)
                adim += 1
        except KeyboardInterrupt:
            pass
        finally:
            self.durdur()
