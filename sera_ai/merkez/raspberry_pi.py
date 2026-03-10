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
from ..config.settings import optimizer_olustur


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

        # Infrastructure bileşenleri — baslat() içinde hazırlanır
        self._sensor_repo:         object = None
        self._komut_repo:          object = None
        self._log_dispatcher:      object = None
        self._bildirim_dispatcher: object = None

        self._infrastructure_baslat()

    def _infrastructure_baslat(self) -> None:
        """Repository, Logger ve BildirimDispatcher'ı oluştur ve EventBus'a bağla."""
        # ── Repository ────────────────────────────────────────
        try:
            from ..infrastructure.repositories.sqlite_repository import (
                SQLiteSensorRepository, SQLiteKomutRepository,
            )
            self._sensor_repo = SQLiteSensorRepository(self.konfig.db_yolu)
            self._komut_repo  = SQLiteKomutRepository(self.konfig.db_yolu)
            # Komut geçmişi: KOMUT_GONDERILDI event'i → DB
            self.olay_bus.abone_ol(OlayTur.KOMUT_GONDERILDI, self._komut_kaydet)
        except Exception as e:
            print(f"[MerkezRPi] Repository başlatma hatası: {e}")

        # ── Yapılandırılmış log ────────────────────────────────
        try:
            from ..infrastructure.logging.jsonl_logger import JSONLLogger
            from ..infrastructure.logging.dispatcher import LogDispatcher
            logger = JSONLLogger(self.konfig.log_dosyasi)
            self._log_dispatcher = LogDispatcher(
                yazicilar=[logger],
                olay_bus=self.olay_bus,
            )
            self._log_dispatcher.baslat()
        except Exception as e:
            print(f"[MerkezRPi] Log başlatma hatası: {e}")

        # ── Bildirimler ────────────────────────────────────────
        try:
            from ..infrastructure.notifications.dispatcher import BildirimDispatcher
            kanallar = []
            b = self.konfig.bildirim
            if b.telegram_aktif:
                try:
                    from ..infrastructure.notifications.telegram import TelegramKanal
                    kanallar.append(TelegramKanal(
                        token_env=b.telegram_token_env,
                        chat_id_env=b.telegram_chat_id_env,
                        aktif=True,
                    ))
                except Exception as te:
                    print(f"[MerkezRPi] Telegram başlatma hatası: {te}")
            self._bildirim_dispatcher = BildirimDispatcher(
                kanallar=kanallar,
                konfig=b,
                olay_bus=self.olay_bus,
            )
            self._bildirim_dispatcher.baslat()
        except Exception as e:
            print(f"[MerkezRPi] Bildirim başlatma hatası: {e}")

    def _komut_kaydet(self, veri: dict) -> None:
        """KOMUT_GONDERILDI event'ini KomutRepository'ye yaz."""
        if self._komut_repo is None:
            return
        try:
            komut_str = veri.get("komut", "")
            komut = next((k for k in Komut if k.value == komut_str), None)
            if komut is None:
                return
            from ..domain.models import KomutSonucu
            sonuc = KomutSonucu(
                komut=komut,
                basarili=veri.get("basarili", False),
                mesaj=veri.get("hata", ""),
            )
            self._komut_repo.kaydet(veri.get("sera_id", ""), sonuc)
        except Exception as e:
            print(f"[MerkezRPi] Komut kaydetme hatası: {e}")

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
            on_gecis=lambda d, bus=self.olay_bus: bus.yayinla(OlayTur.DURUM_DEGISTI, d),
        )
        optimizer = optimizer_olustur(self.konfig, profil)
        motor = KontrolMotoru(
            sera_id=sera_id,
            profil=profil,
            node=node,
            cb=cb,
            state_machine=sm,
            olay_bus=self.olay_bus,
            optimizer=optimizer,
        )

        self._nodes[sera_id]    = node
        self._cb_ler[sera_id]   = cb
        self._sm_ler[sera_id]   = sm
        self._motorlar[sera_id] = motor

    def baslat(self) -> None:
        """Tüm node'lara bağlan, optimizer modellerini yükle ve kontrol döngüsünü başlat."""
        for sera_id, node in self._nodes.items():
            if not node.baglan():
                print(f"[MerkezRPi] Uyarı: {sera_id} node bağlantısı başarısız")

        # Optimizer kalıcılığı: kaydedilmiş modelleri yükle (ör. RLAjan Q-tablo)
        for sera_id, motor in self._motorlar.items():
            motor.optimizer.baslangic_yukle(self.konfig.model_dizin, sera_id)

        self._calisiyor = True
        self._dongu_thread = threading.Thread(
            target=self._kontrol_dongusu,
            name="KontrolDongusu",
            daemon=True,
        )
        self._dongu_thread.start()

    def durdur(self) -> None:
        """Döngüyü durdur, modelleri kaydet, node bağlantılarını kapat."""
        self._calisiyor = False
        if self._dongu_thread:
            self._dongu_thread.join(timeout=10)

        # Optimizer kalıcılığı: kapanmadan önce kaydet (ör. RLAjan Q-tablo)
        for sera_id, motor in self._motorlar.items():
            motor.optimizer.kapatma_kaydet(self.konfig.model_dizin, sera_id)

        for node in self._nodes.values():
            node.kapat()

        if self._log_dispatcher:
            self._log_dispatcher.durdur()
        if self._bildirim_dispatcher:
            self._bildirim_dispatcher.durdur()

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

            # Sensör verisini DB'ye kaydet
            if self._sensor_repo is not None:
                try:
                    self._sensor_repo.kaydet(okuma)
                except Exception as db_e:
                    print(f"[MerkezRPi:{sera_id}] DB yazma hatası: {db_e}")

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
