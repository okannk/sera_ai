"""
REST API — Flask Uygulaması

Endpoint'ler:
  GET  /api/seralar              → Tüm seralar + son sensör
  GET  /api/seralar/<sid>        → Tek sera detayı
  GET  /api/seralar/<sid>/sensor → Son sensör okuma
  POST /api/seralar/<sid>/komut  → Komut gönder {"komut": "FAN_AC"}
  GET  /api/sistem/saglik        → Health check (auth MUAF)
  GET  /api/sistem/metrik        → İstatistikler
  GET  /api/alarm                → Aktif alarmlar

Auth:
  X-API-Key header zorunlu (eğer SERA_API_KEY env tanımlıysa).
  /api/sistem/saglik muaf — monitoring sistemleri key olmadan erişebilir.

Kullanım:
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="gizli")
    app.run(port=5000)
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from datetime import datetime
from typing import Any, Optional

from .auth import check_api_key, MUAF_ENDPOINTLER


def api_yanit(data: Any = None, hata: str = None,
              durum: int = 200, meta: dict = None):
    """Standart JSON yanıt zarfı."""
    govde = {
        "success": hata is None,
        "data":    data,
        "error":   hata,
        "meta":    {"ts": datetime.now().isoformat(), **(meta or {})},
    }
    return (
        json.dumps(govde, ensure_ascii=False, default=str),
        durum,
        {"Content-Type": "application/json; charset=utf-8"},
    )


# ── Simülasyon Servisi ────────────────────────────────────────

class SeraApiServisi:
    """
    API iş mantığı katmanı.

    Şu an: kendi simülasyonu (mock).
    İleride: gerçek MerkezKontrolBase instance'ı enjekte edilir.
    """

    PROFILLER = {
        "Domates": {"minT": 15, "maxT": 30, "optT": 23, "minH": 60, "maxH": 85},
        "Biber":   {"minT": 18, "maxT": 32, "optT": 25, "minH": 55, "maxH": 80},
        "Marul":   {"minT": 10, "maxT": 22, "optT": 16, "minH": 65, "maxH": 85},
    }
    SERALAR = {
        "s1": {"id": "s1", "isim": "Sera A", "bitki": "Domates", "alan": 500},
        "s2": {"id": "s2", "isim": "Sera B", "bitki": "Biber",   "alan": 300},
        "s3": {"id": "s3", "isim": "Sera C", "bitki": "Marul",   "alan": 200},
    }

    def __init__(self):
        self._durum = {sid: "NORMAL" for sid in self.SERALAR}
        self._sensor: dict[str, dict] = {}
        self._komut_log: list[dict]   = []
        self._baslangic = time.time()
        threading.Thread(target=self._sim_dongu, daemon=True).start()

    def _sim_dongu(self):
        """Arka planda sensör simülasyonu."""
        s = {
            "s1": {"T": 23.0, "H": 72.0, "co2": 950},
            "s2": {"T": 25.0, "H": 65.0, "co2": 900},
            "s3": {"T": 16.0, "H": 75.0, "co2": 820},
        }
        while True:
            for sid, st in s.items():
                st["T"]   = max(8,   min(42,   st["T"]   + random.gauss(0, 0.15)))
                st["H"]   = max(20,  min(98,   st["H"]   + random.gauss(0, 0.25)))
                st["co2"] = max(300, min(1800, st["co2"] + random.gauss(0, 10)))
                p   = self.PROFILLER[self.SERALAR[sid]["bitki"]]
                opt = p["optT"]
                if   abs(st["T"] - opt) > 8: self._durum[sid] = "ACIL_DURDUR"
                elif abs(st["T"] - opt) > 5: self._durum[sid] = "ALARM"
                elif abs(st["T"] - opt) > 2: self._durum[sid] = "UYARI"
                else:                         self._durum[sid] = "NORMAL"
                self._sensor[sid] = {
                    "T":        round(st["T"], 1),
                    "H":        round(st["H"], 1),
                    "co2":      int(st["co2"]),
                    "isik":     random.randint(200, 900),
                    "toprak":   random.randint(300, 700),
                    "ph":       round(random.uniform(5.8, 7.2), 2),
                    "ec":       round(random.uniform(1.4, 2.8), 2),
                    "zaman":    datetime.now().isoformat(),
                }
            time.sleep(2)

    def tum_seralar(self) -> list:
        return [
            {**s, "durum": self._durum.get(sid, "?"),
             "sensor": self._sensor.get(sid, {})}
            for sid, s in self.SERALAR.items()
        ]

    def sera_detay(self, sid: str) -> Optional[dict]:
        if sid not in self.SERALAR:
            return None
        return {
            **self.SERALAR[sid],
            "durum":  self._durum[sid],
            "sensor": self._sensor.get(sid, {}),
            "profil": self.PROFILLER.get(self.SERALAR[sid]["bitki"], {}),
        }

    def son_sensor(self, sid: str) -> Optional[dict]:
        return self._sensor.get(sid)

    def komut_gonder(self, sid: str, komut: str, kaynak: str = "api") -> dict:
        GECERLI = {
            "SULAMA_AC", "SULAMA_KAPAT", "ISITICI_AC", "ISITICI_KAPAT",
            "SOGUTMA_AC", "SOGUTMA_KAPAT", "FAN_AC", "FAN_KAPAT",
            "ISIK_AC", "ISIK_KAPAT", "ACIL_DURDUR",
        }
        if sid not in self.SERALAR:
            return {"basarili": False, "hata": f"Sera bulunamadı: {sid}"}
        k = komut.upper()
        if k not in GECERLI:
            return {"basarili": False, "hata": f"Geçersiz komut: {komut}",
                    "gecerli": sorted(GECERLI)}
        self._komut_log.append({
            "sera_id": sid, "komut": k,
            "kaynak":  kaynak, "zaman": datetime.now().isoformat(),
        })
        return {"basarili": True, "komut": k, "sera_id": sid}

    def saglik(self) -> dict:
        up = int(time.time() - self._baslangic)
        return {
            "durum":       "CALISIYOR",
            "uptime_sn":   up,
            "uptime_fmt":  f"{up // 3600}s {(up % 3600) // 60}d",
            "seralar":     dict(self._durum),
            "alarm_sayisi": sum(
                1 for d in self._durum.values()
                if d in ("ALARM", "ACIL_DURDUR")
            ),
        }

    def metrikler(self) -> dict:
        return {
            "toplam_komut": len(self._komut_log),
            "son_10":        self._komut_log[-10:],
            "durum_dagilimi": {
                d: sum(1 for v in self._durum.values() if v == d)
                for d in set(self._durum.values())
            },
        }

    def aktif_alarmlar(self) -> list:
        return [
            {
                "sera_id": sid,
                "isim":    self.SERALAR[sid]["isim"],
                "durum":   d,
                "sensor":  self._sensor.get(sid, {}),
            }
            for sid, d in self._durum.items()
            if d in ("ALARM", "ACIL_DURDUR", "UYARI")
        ]


# ── Flask Uygulaması ──────────────────────────────────────────

def api_uygulamasi_olustur(
    servis: Optional[SeraApiServisi] = None,
    api_key: Optional[str] = None,
):
    """
    Flask uygulaması fabrika fonksiyonu.

    Args:
        servis:  Veri kaynağı (None → kendi simülasyonunu oluşturur)
        api_key: X-API-Key değeri (None → SERA_API_KEY env'den okur)

    Returns:
        Flask app instance
    """
    try:
        from flask import Flask, request
        from flask_cors import CORS
    except ImportError:
        raise ImportError(
            "Flask kurulu değil: pip install flask flask-cors"
        )

    app = Flask(__name__)
    CORS(app)

    if servis is None:
        servis = SeraApiServisi()

    # API key: parametre > env değişkeni
    _api_key = api_key if api_key is not None else os.getenv("SERA_API_KEY", "")

    if not _api_key:
        print(
            "[API] Uyarı: SERA_API_KEY tanımlı değil — "
            "kimlik doğrulama devre dışı (geliştirme modu)"
        )

    # ── Auth middleware ───────────────────────────────────────

    @app.before_request
    def auth_kontrol():
        """Her istekte X-API-Key kontrolü. Muaf endpoint'ler geçer."""
        if request.endpoint in MUAF_ENDPOINTLER:
            return None
        gelen = request.headers.get("X-API-Key", "")
        if not check_api_key(gelen, _api_key):
            return api_yanit(
                hata="Yetkisiz erişim — X-API-Key header'ı gerekli",
                durum=401,
            )

    # ── Route'lar ─────────────────────────────────────────────

    @app.route("/api/seralar")
    def tum():
        return api_yanit(servis.tum_seralar())

    @app.route("/api/seralar/<sid>")
    def detay(sid):
        d = servis.sera_detay(sid)
        return (
            api_yanit(d) if d
            else api_yanit(hata=f"Sera bulunamadı: {sid}", durum=404)
        )

    @app.route("/api/seralar/<sid>/sensor")
    def sensor(sid):
        s = servis.son_sensor(sid)
        return (
            api_yanit(s) if s
            else api_yanit(hata="Veri yok", durum=404)
        )

    @app.route("/api/seralar/<sid>/komut", methods=["POST"])
    def komut(sid):
        try:
            body = request.get_json(force=True) or {}
        except Exception:
            return api_yanit(hata="Geçersiz JSON", durum=400)
        k = body.get("komut", "").strip()
        if not k:
            return api_yanit(hata="'komut' alanı zorunlu", durum=400)
        sonuc = servis.komut_gonder(sid, k, body.get("kaynak", "api"))
        if sonuc["basarili"]:
            return api_yanit(sonuc, durum=201)
        return api_yanit(hata=sonuc["hata"], durum=400)

    @app.route("/api/sistem/saglik")
    def saglik():
        """Health check — auth MUAF (monitoring sistemleri key gerektirmez)."""
        s = servis.saglik()
        return api_yanit(s, durum=503 if s["alarm_sayisi"] > 0 else 200)

    @app.route("/api/sistem/metrik")
    def metrik():
        return api_yanit(servis.metrikler())

    @app.route("/api/alarm")
    def alarm():
        a = servis.aktif_alarmlar()
        return api_yanit(a, meta={"toplam": len(a)})

    @app.errorhandler(404)
    def e404(e):
        return api_yanit(hata=f"Bulunamadı: {request.path}", durum=404)

    @app.errorhandler(405)
    def e405(e):
        return api_yanit(hata="Yöntem desteklenmiyor", durum=405)

    return app
