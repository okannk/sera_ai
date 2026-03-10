"""
Sera AI — Çoklu Sera Uçtan Uca Demo
═══════════════════════════════════════════════════════════

3 sera paralel — s1 Domates, s2 Biber, s3 Marul

Gösterilen katmanlar:
  ■ MQTT     : MockMQTTBroker (in-process) + 3× ESP32Simulatoru
  ■ Kontrol  : 3× KontrolMotoru + 3× RLAjan (Q-learning, 2430 durum)
  ■ İzolasyon: s2 ALARM olurken s1/s3 NORMAL — CircuitBreaker bağımsız
  ■ Veri     : SQLite (sensör + komut geçmişi, tüm seralar)
  ■ Log      : JSONLLogger → demo.jsonl (yapılandırılmış JSONL)
  ■ Bildirim : MockBildirimKanal (Telegram simülasyonu)
  ■ API      : Flask REST → /api/seralar (3 sera)

Çalıştırma:
    ~/.local/bin/uv run --with flask --with flask-cors \\
        --with numpy --with joblib python demo_komplet.py
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows terminali UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sera_ai.application.control_engine import KontrolMotoru
from sera_ai.application.event_bus import EventBus, OlayTur
from sera_ai.domain.circuit_breaker import CircuitBreaker
from sera_ai.domain.models import (
    BitkilProfili, BildirimKonfig, Komut, SeraKonfig, SistemKonfig,
    VARSAYILAN_PROFILLER,
)
from sera_ai.domain.state_machine import Durum, SeraStateMachine
from sera_ai.drivers.base import SahaNodeBase
from sera_ai.infrastructure.logging import JSONLLogger, LogDispatcher, LogSeviye
from sera_ai.infrastructure.logging.base import LogKayit, LogYaziciBase
from sera_ai.infrastructure.mqtt import (
    ESP32Simulatoru, MockMQTTBroker, MockMQTTIstemci, SeraTopics,
)
from sera_ai.infrastructure.notifications import (
    BildirimDispatcher, MockBildirimKanal,
)
from sera_ai.infrastructure.repositories import (
    SQLiteKomutRepository, SQLiteSensorRepository,
)
from sera_ai.intelligence.rl_ajan import RLAjan
from sera_ai.merkez.base import MerkezKontrolBase


# ── Renk paleti ─────────────────────────────────────────────────
R = {
    "NORMAL":        "\033[92m",   # Yeşil
    "UYARI":         "\033[93m",   # Sarı
    "ALARM":         "\033[91m",   # Kırmızı
    "ACIL_DURDUR":   "\033[95m",   # Mor
    "BASLATILAMADI": "\033[90m",   # Gri
    "MQTT":          "\033[96m",   # Cyan
    "LOG":           "\033[94m",   # Mavi
    "BIL":           "\033[93m",   # Sarı
    "API":           "\033[35m",   # Magenta
    "DB":            "\033[90m",   # Gri
    "RL":            "\033[36m",   # Teal
    "RESET":         "\033[0m",
    "BOLD":          "\033[1m",
    "DIM":           "\033[2m",
    "GRI":           "\033[90m",
}

_PRINT_LOCK = threading.Lock()

def baskı(etiket: str, mesaj: str, renk_key: str = "RESET"):
    t = datetime.now().strftime("%H:%M:%S.%f")[:11]
    renk  = R.get(renk_key, "")
    reset = R["RESET"]
    dim   = R["DIM"]
    bold  = R["BOLD"]
    with _PRINT_LOCK:
        print(f"  {renk}{bold}[{etiket:10s}]{reset} {dim}{t}{reset}  {mesaj}")

def baslik(metin: str):
    with _PRINT_LOCK:
        print(f"\n{R['BOLD']}{'─'*66}{R['RESET']}")
        print(f"{R['BOLD']}  {metin}{R['RESET']}")
        print(f"{R['BOLD']}{'─'*66}{R['RESET']}")

def sera_satir(sid: str, isim: str, durum: str, T: float, not_: str):
    """Tek satırda bir seranın durumunu göster."""
    renk = R.get(durum, R["RESET"])
    bold = R["BOLD"]
    rst  = R["RESET"]
    dim  = R["DIM"]
    with _PRINT_LOCK:
        print(f"    {renk}{bold}{sid}{rst} {dim}{isim:12s}{rst}  "
              f"T={T:5.1f}°C  {renk}{bold}{durum:14s}{rst}  {dim}{not_}{rst}")


# ── MQTTSahaNodeAdaptor ─────────────────────────────────────────
# Demo/test için — production'da yerini ESP32S3Node (paho-mqtt) alır.

class MQTTSahaNodeAdaptor(SahaNodeBase):
    """MockMQTTBroker üzerinden SahaNodeBase arayüzü."""

    TIMEOUT_SN = 2.0

    def __init__(self, sera_id: str, node_id: str, broker: MockMQTTBroker):
        self.sera_id  = sera_id
        self.node_id  = node_id
        self._topics  = SeraTopics(node_id)
        self._istemci = MockMQTTIstemci(f"merkez_{node_id}", broker)
        self._sensor_q: queue.Queue[bytes] = queue.Queue(maxsize=5)
        self._ack_q:    queue.Queue[str]   = queue.Queue(maxsize=5)

    def baglan(self) -> bool:
        self._istemci.baglan()
        self._istemci.abone_ol(self._topics.sensor, self._on_sensor)
        self._istemci.abone_ol(self._topics.ack,    self._on_ack)
        return True

    def sensor_oku(self, sera_id: str):
        from sera_ai.domain.models import SensorOkuma
        try:
            payload = self._sensor_q.get(timeout=self.TIMEOUT_SN)
            veri = json.loads(payload.decode())
            return SensorOkuma(
                sera_id=sera_id,
                T=float(veri.get("T", 0)),
                H=float(veri.get("H", 0)),
                co2=int(veri.get("co2", 0)),
                isik=int(veri.get("isik", 0)),
                toprak_nem=int(veri.get("toprak", 500)),
                ph=float(veri.get("ph", 6.5)),
                ec=float(veri.get("ec", 2.0)),
            )
        except queue.Empty:
            raise IOError(f"[{self.node_id}] Sensör timeout")

    def komut_gonder(self, komut: Komut) -> bool:
        while not self._ack_q.empty():
            self._ack_q.get_nowait()
        self._istemci.yayinla(self._topics.komut, komut.value, qos=1)
        try:
            ack = self._ack_q.get(timeout=self.TIMEOUT_SN)
            return ack == "OK"
        except queue.Empty:
            raise IOError(f"[{self.node_id}] Komut ACK timeout: {komut.value}")

    def kapat(self):
        self._istemci.kes()

    def _on_sensor(self, topic: str, payload: bytes):
        if not self._sensor_q.full():
            self._sensor_q.put_nowait(payload)

    def _on_ack(self, topic: str, payload: bytes):
        if not self._ack_q.full():
            self._ack_q.put_nowait(payload.decode().strip())


# ── TerminalLogger ──────────────────────────────────────────────

class TerminalLogger(LogYaziciBase):
    """LogDispatcher'dan gelen kayıtları terminale yazar."""

    SEVIYE_RENK = {
        LogSeviye.DEBUG:  "GRI",
        LogSeviye.INFO:   "LOG",
        LogSeviye.UYARI:  "UYARI",
        LogSeviye.HATA:   "ALARM",
        LogSeviye.KRITIK: "ACIL_DURDUR",
    }

    def yaz(self, kayit: LogKayit) -> None:
        renk = self.SEVIYE_RENK.get(kayit.seviye, "RESET")
        sera = f"[{kayit.sera_id}] " if kayit.sera_id else ""
        baskı("LOG", f"{sera}{kayit.olay}", renk)


# ── DemoBridgeMulti ──────────────────────────────────────────────

class DemoBridgeMulti(MerkezKontrolBase):
    """
    N serayı MerkezApiServisi için saran köprü.
    Her sera için bağımsız motor, CB, SM referansı tutar.
    """

    def __init__(self):
        self._motorlar: dict[str, KontrolMotoru] = {}
        self._son_sensor: dict[str, Any] = {}
        self._lock = threading.Lock()

    def sera_ekle(self, sera_id: str, motor: KontrolMotoru) -> None:
        self._motorlar[sera_id] = motor

    def node_ekle(self, sera_id: str, node) -> None:
        pass  # Motor zaten node'u içeriyor

    def baslat(self) -> None:
        pass

    def durdur(self) -> None:
        pass

    def sensor_oku(self, sera_id: str):
        return self._motorlar[sera_id].node.sensor_oku(sera_id)

    def komut_gonder(self, sera_id: str, komut: Komut) -> bool:
        if sera_id not in self._motorlar:
            return False
        try:
            return self._motorlar[sera_id].node.komut_gonder(komut)
        except Exception:
            return False

    def tum_durum(self) -> dict:
        with self._lock:
            return {
                sid: {
                    "durum":          motor.sm.durum.name,
                    "sensor":         self._son_sensor.get(sid),
                    "cb":             motor.cb.durum.name,
                    "son_guncelleme": datetime.now().isoformat(),
                }
                for sid, motor in self._motorlar.items()
            }

    def guncelle_son_sensor(self, sera_id: str, sensor) -> None:
        with self._lock:
            self._son_sensor[sera_id] = sensor.to_dict() if sensor else None


# ── API istek yardımcısı ─────────────────────────────────────────

API_PORT = 5050
API_URL  = f"http://127.0.0.1:{API_PORT}"


def api_get(yol: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"{API_URL}{yol}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"hata": str(e)}


def api_post(yol: str, veri: dict, timeout: float = 2.0) -> dict | None:
    try:
        req = urllib.request.Request(
            f"{API_URL}{yol}",
            data=json.dumps(veri).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"hata": str(e)}


def api_goster(baslik_: str, yanit: dict | None):
    if yanit is None:
        baskı("API", f"{baslik_} → bağlanamadı", "ALARM")
        return
    if "hata" in yanit and not isinstance(yanit.get("success"), bool):
        baskı("API", f"{baslik_} → HATA: {yanit['hata']}", "ALARM")
        return
    if yanit.get("success") is False:
        baskı("API", f"{baslik_} → {yanit.get('error')}", "ALARM")
        return
    data = yanit.get("data", yanit)
    ozet = json.dumps(data, ensure_ascii=False)[:130]
    if len(json.dumps(data, ensure_ascii=False)) > 130:
        ozet += "…"
    baskı("API", f"{baslik_} → {ozet}", "API")


# ══════════════════════════════════════════════════════════════════
# SERA TANIMLARI
# ══════════════════════════════════════════════════════════════════

SERA_TANIMLAR = [
    # (sera_id, kısa_isim, bitki,    node_id)
    ("s1", "Sera A",  "Domates", "esp32_sera_a"),
    ("s2", "Sera B",  "Biber",   "esp32_sera_b"),
    ("s3", "Sera C",  "Marul",   "esp32_sera_c"),
]

# Senaryo: (adim_adi, T_override per sera, not)
# Domates: opt=23°C, max=30°C  → UYARI: T>26, ALARM: T>29
# Biber:   opt=25°C, max=32°C  → UYARI: T>28, ALARM: T>31
# Marul:   opt=16°C, max=22°C  → UYARI: T>19, ALARM: T>22
SENARYO = [
    ("Adım 1",
     {"s1": 23.0, "s2": 25.0, "s3": 16.0},
     "Tüm seralar optimal — sistem nominal"),
    ("Adım 2",
     {"s1": 23.5, "s2": 25.5, "s3": 16.5},
     "Hafif gün içi ısı artışı"),
    ("Adım 3",
     {"s1": 24.0, "s2": 28.5, "s3": 17.0},
     "s2 Biber ısınıyor → UYARI bölgesi"),
    ("Adım 4",
     {"s1": 23.0, "s2": 29.5, "s3": 17.5},
     "s2 Biber UYARI devam — s1/s3 hâlâ NORMAL"),
    ("Adım 5",
     {"s1": 23.5, "s2": 32.5, "s3": 17.0},
     "s2 Biber → ALARM (T>max_T=32) │ CB izolasyonu"),
    ("Adım 6",
     {"s1": 23.0, "s2": 33.0, "s3": 17.0},
     "s2 ALARM devam — s1/s3 tamamen bağımsız"),
    ("Adım 7",
     {"s1": 23.0, "s2": 29.0, "s3": 20.5},
     "s2 soğutucu devrede → UYARI │ s3 Marul ısınıyor"),
    ("Adım 8",
     {"s1": 23.0, "s2": 27.0, "s3": 23.5},
     "s3 Marul → ALARM (T>max_T=22) │ s2 toparlanıyor"),
    ("Adım 9",
     {"s1": 23.0, "s2": 25.5, "s3": 19.5},
     "s2 NORMAL │ s3 UYARI bölgesinde"),
    ("Adım 10",
     {"s1": 23.0, "s2": 25.0, "s3": 16.0},
     "Tüm seralar NORMAL — tam iyileşme"),
]


# ══════════════════════════════════════════════════════════════════
# ANA DEMO
# ══════════════════════════════════════════════════════════════════

def main():
    print()
    print(f"{R['BOLD']}{'═'*66}{R['RESET']}")
    print(f"{R['BOLD']}  SERA AI — ÇOKLU SERA UÇTAN UCA DEMO{R['RESET']}")
    print(f"{R['BOLD']}  3 Sera │ MQTT │ RL Ajan │ CB İzolasyon │ SQLite │ API{R['RESET']}")
    print(f"{R['BOLD']}{'═'*66}{R['RESET']}")

    # ── 1. Profil ve konfig ─────────────────────────────────────
    baslik("1/8  Profil & Konfig — 3 Sera")

    profiller = VARSAYILAN_PROFILLER
    sera_konfig_listesi = [
        SeraKonfig(sid, isim, alan_m2=300, bitki=bitki)
        for (sid, isim, bitki, _) in SERA_TANIMLAR
    ]
    konfig = SistemKonfig(
        seralar=sera_konfig_listesi,
        profiller=dict(profiller),
    )

    for sid, isim, bitki, _ in SERA_TANIMLAR:
        p = profiller[bitki]
        baskı("KONFIG",
              f"{sid} {isim:8s} | {bitki:8s} | "
              f"opt_T={p.opt_T}°C max_T={p.max_T}°C | "
              f"pH={p.opt_pH} EC={p.opt_EC}", "LOG")

    # ── 2. MQTT katmanı — 3 ESP32 ────────────────────────────────
    baslik("2/8  MQTT — MockBroker + 3× ESP32Simulatoru")

    broker = MockMQTTBroker()
    simler:    dict[str, ESP32Simulatoru]      = {}
    adaptorlar: dict[str, MQTTSahaNodeAdaptor] = {}

    for sid, isim, bitki, node_id in SERA_TANIMLAR:
        profil = profiller[bitki]
        sim = ESP32Simulatoru(node_id, sid, profil, broker)
        sim.baslat()
        adaptor = MQTTSahaNodeAdaptor(sid, node_id, broker)
        adaptor.baglan()
        simler[sid]    = sim
        adaptorlar[sid] = adaptor
        baskı("MQTT", f"ESP32 [{node_id}] → topic: sera/{node_id}/sensor", "MQTT")

    baskı("MQTT", "3 node bağlandı, broker başladı", "MQTT")

    # ── 3. Altyapı ──────────────────────────────────────────────
    baslik("3/8  Altyapı — SQLite + Log + Bildirim")

    db_dosya  = Path("demo_sera.db")
    log_dosya = Path("demo.jsonl")
    baskı("DB",  f"SQLite → {db_dosya.absolute()}", "DB")
    baskı("LOG", f"JSONLLogger → {log_dosya.absolute()}", "LOG")

    s_repo = SQLiteSensorRepository(str(db_dosya))
    k_repo = SQLiteKomutRepository(str(db_dosya))

    jsonl_logger    = JSONLLogger(str(log_dosya))
    terminal_logger = TerminalLogger()
    bil_kanal       = MockBildirimKanal()

    bus = EventBus()

    log_dispatcher = LogDispatcher([jsonl_logger, terminal_logger], bus)
    log_dispatcher.baslat()
    baskı("LOG", "LogDispatcher başlatıldı (JSONL + Terminal)", "LOG")

    bil_dispatcher = BildirimDispatcher(
        [bil_kanal],
        BildirimKonfig(bastirma_dk=0),  # Demo: bastırma yok
        bus,
    )
    bil_dispatcher.baslat()
    baskı("BIL", "BildirimDispatcher başlatıldı (MockTelegram)", "BIL")

    # Komut DB'ye kaydet (tüm seralar)
    def komut_kaydet(veri: dict):
        try:
            from sera_ai.domain.models import KomutSonucu
            sonuc = KomutSonucu(
                komut=Komut(veri["komut"]),
                basarili=veri.get("basarili", True),
                mesaj="",
            )
            k_repo.kaydet(veri.get("sera_id", "?"), sonuc)
            baskı("DB", f"[{veri.get('sera_id','?')}] Komut → {veri['komut']}", "DB")
        except Exception:
            pass

    bus.abone_ol(OlayTur.KOMUT_GONDERILDI, komut_kaydet)

    # Durum geçişlerini terminale yansıt (bildirim)
    def bildirim_goster(veri: dict):
        yeni  = veri.get("yeni", "?")
        renk  = "ALARM" if yeni in ("ALARM", "ACIL_DURDUR") else "UYARI"
        baskı("BIL",
              f"[Telegram SIM] {veri.get('sera_id','?')} "
              f"{veri.get('onceki','?')} → {yeni}  {veri.get('sebep','')[:50]}",
              renk)

    bus.abone_ol(OlayTur.DURUM_DEGISTI, bildirim_goster)

    # ── 4. Kontrol motorları — 3 sera ───────────────────────────
    baslik("4/8  KontrolMotoru + RLAjan — 3× bağımsız")

    bridge = DemoBridgeMulti()
    motorlar: dict[str, KontrolMotoru] = {}
    ajanlar:  dict[str, RLAjan]        = {}

    for sid, isim, bitki, _ in SERA_TANIMLAR:
        profil = profiller[bitki]
        cb  = CircuitBreaker(f"cb_{sid}", hata_esigi=5, recovery_sn=60)
        sm  = SeraStateMachine(
            sid, profil,
            on_gecis=lambda d, b=bus: b.yayinla(OlayTur.DURUM_DEGISTI, d),
        )
        ajan   = RLAjan(profil, epsilon=0.05)
        motor  = KontrolMotoru(
            sera_id=sid, profil=profil,
            node=adaptorlar[sid], cb=cb, state_machine=sm,
            olay_bus=bus, optimizer=ajan,
        )
        motorlar[sid] = motor
        ajanlar[sid]  = ajan
        bridge.sera_ekle(sid, motor)
        baskı("RL",
              f"[{sid}] RLAjan ({bitki}) | Q(2430,16) | "
              f"KuralMotoru warm-start tamamlandı", "RL")

    # ── 5. Flask API ─────────────────────────────────────────────
    baslik("5/8  Flask REST API")
    api_baslatildi = threading.Event()

    def api_calistir():
        try:
            from sera_ai.api.app import api_uygulamasi_olustur
            from sera_ai.api.servis import MerkezApiServisi
            import logging
            logging.getLogger("werkzeug").setLevel(logging.ERROR)

            servis    = MerkezApiServisi(bridge, konfig)
            flask_app = api_uygulamasi_olustur(servis=servis, api_key="")
            flask_app.config["TESTING"] = False
            api_baslatildi.set()
            flask_app.run(host="127.0.0.1", port=API_PORT, use_reloader=False, threaded=True)
        except Exception as e:
            baskı("API", f"Flask başlatılamadı: {e}", "ALARM")
            api_baslatildi.set()

    api_thread = threading.Thread(target=api_calistir, name="FlaskAPI", daemon=True)
    api_thread.start()
    api_baslatildi.wait(timeout=5)
    time.sleep(0.3)
    baskı("API", f"Flask → http://127.0.0.1:{API_PORT}", "API")
    baskı("API", "Endpoint'ler: /api/seralar  /api/seralar/{id}  /api/sistem/saglik  /api/alarm", "API")

    # ── 6. Senaryo ───────────────────────────────────────────────
    baslik("6/8  Senaryo — 10 Adım │ CB İzolasyon Kanıtı")

    RL_adimlar_oncesi = {sid: ajanlar[sid].adim_sayisi for sid in motorlar}

    for i, (ad, T_map, not_) in enumerate(SENARYO):
        print()
        baskı("─" * 4, f"{R['BOLD']}{ad}{R['RESET']}  {R['DIM']}{not_}{R['RESET']}", "GRI")

        okumallar = {}
        for sid, isim, bitki, _ in SERA_TANIMLAR:
            # Sıcaklığı senaryo değerine ayarla
            simler[sid]._durum.T = T_map[sid]
            simler[sid].veri_gonder()
            okuma = adaptorlar[sid].sensor_oku(sid)
            bridge.guncelle_son_sensor(sid, okuma)
            s_repo.kaydet(okuma)
            okumallar[sid] = okuma

            # Kontrol döngüsü adımı
            motorlar[sid].adim_at(okuma)

            durum = motorlar[sid].sm.durum.name
            sera_satir(sid, isim, durum, okuma.T, f"H={okuma.H:.0f}% CO₂={okuma.co2}ppm")

        # RL öğrenme özeti
        rl_guncelleme = 0
        for sid in motorlar:
            delta = ajanlar[sid].adim_sayisi - RL_adimlar_oncesi[sid]
            rl_guncelleme += delta
            RL_adimlar_oncesi[sid] = ajanlar[sid].adim_sayisi
        if rl_guncelleme:
            baskı("RL", f"Q-güncelleme: +{rl_guncelleme} (3 sera toplamı)", "RL")

        # API çağrıları — belirli adımlarda
        if i == 1:   # Adım 2 — tüm seralar normal
            print()
            baskı("API", "── Başlangıç Durumu Kontrolü ────────────────────────", "API")
            api_goster("GET /api/sistem/saglik", api_get("/api/sistem/saglik"))

        elif i == 4:  # Adım 5 — s2 ALARM, izolasyon
            print()
            baskı("API", "── CB İzolasyon Kanıtı (s2 ALARM, s1/s3 NORMAL) ────", "API")
            api_goster("GET /api/seralar",      api_get("/api/seralar"))
            api_goster("GET /api/alarm",         api_get("/api/alarm"))

        elif i == 7:  # Adım 8 — s3 ALARM
            print()
            baskı("API", "── s3 Marul ALARM Durumu ─────────────────────────", "API")
            api_goster("GET /api/seralar/s3",   api_get("/api/seralar/s3"))
            api_goster("POST /api/seralar/s3/komut (SOGUTMA_AC)",
                       api_post("/api/seralar/s3/komut", {"komut": "SOGUTMA_AC"}))

        time.sleep(0.3)

    # ── 7. Özet istatistikler ────────────────────────────────────
    baslik("7/8  Özet İstatistikler")

    toplam_komut = 0
    for sid, isim, bitki, _ in SERA_TANIMLAR:
        kayitlar = k_repo.gecmis(sid)
        toplam_komut += len(kayitlar)
        gecmisler = motorlar[sid].sm.gecmis
        gecmis_str = " → ".join(g.yeni.name for g in gecmisler) or "—"
        baskı("DB",
              f"[{sid}] {bitki:8s} | "
              f"komut={len(kayitlar):2d} | "
              f"RL={ajanlar[sid].adim_sayisi:3d} adım | "
              f"geçiş: {gecmis_str}", "DB")

    baskı("DB",
          f"Toplam komut kayıtları: {toplam_komut}  │  "
          f"3 sera × 10 adım = 30 sensör okuma", "DB")

    bildirimler = bil_kanal.gonderilen
    baskı("BIL",
          f"Gönderilen bildirim: {len(bildirimler)}"
          + (f"  │  " + ", ".join(b.oncelik.name for b in bildirimler)
             if bildirimler else ""), "BIL")

    try:
        log_satir = sum(1 for _ in open(log_dosya, encoding="utf-8"))
        baskı("LOG", f"demo.jsonl → {log_satir} satır yazıldı", "LOG")
    except Exception:
        pass

    # ── 8. Final API raporu ──────────────────────────────────────
    baslik("8/8  Final API Raporu — 3 Sera")
    saglik = api_get("/api/sistem/saglik")
    if saglik and saglik.get("success"):
        d = saglik["data"]
        baskı("API",
              f"Uptime: {d.get('uptime_sn')}s  │  "
              f"Durum: {d.get('durum')}  │  "
              f"Alarm: {d.get('alarm_sayisi')}", "API")
        for sid, durum in (d.get("seralar") or {}).items():
            renk_key = durum if durum in R else "RESET"
            baskı("API", f"  {sid}: {R[renk_key]}{durum}{R['RESET']}", "API")

    # Temizlik
    for sim in simler.values():
        sim.durdur()
    for adaptor in adaptorlar.values():
        adaptor.kapat()
    log_dispatcher.durdur()
    bil_dispatcher.durdur()
    jsonl_logger.kapat()

    print()
    print(f"{R['BOLD']}{'═'*66}{R['RESET']}")
    print(f"{R['BOLD']}  Demo tamamlandı — 3 sera, çoklu CB izolasyonu kanıtlandı.{R['RESET']}")
    print(f"{R['DIM']}  Veri dosyaları: {db_dosya}  │  {log_dosya}{R['RESET']}")
    print(f"{R['DIM']}  API hâlâ çalışıyor → Ctrl+C ile kapatabilirsiniz{R['RESET']}")
    print(f"{R['BOLD']}{'═'*66}{R['RESET']}")
    print()

    try:
        time.sleep(5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
