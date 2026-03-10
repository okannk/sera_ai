"""
REST API — FastAPI Uygulaması

Endpoint'ler (/api/v1/ prefix):
  GET  /api/v1/seralar                → Tüm seralar + son sensör
  GET  /api/v1/seralar/{sid}          → Tek sera detayı
  GET  /api/v1/seralar/{sid}/sensor   → Son sensör okuma
  POST /api/v1/seralar/{sid}/komut    → Komut gönder {"komut": "FAN_AC"}
  GET  /api/v1/sistem/saglik          → Health check (auth MUAF, rate limit MUAF)
  GET  /api/v1/sistem/metrik          → İstatistikler
  GET  /api/v1/alarm                  → Aktif alarmlar
  GET  /metrics                       → Prometheus metrikleri (auth MUAF)
  GET  /docs                          → Otomatik OpenAPI dökümantasyonu

Auth:
  X-API-Key header zorunlu (SERA_API_KEY env tanımlıysa).
  /api/v1/sistem/saglik ve /metrics muaf.

Rate limiting:
  IP başına 60 istek/dakika (slowapi).
  /api/v1/sistem/saglik muaf.

Kullanım:
    from sera_ai.api.app import api_uygulamasi_olustur
    app = api_uygulamasi_olustur(api_key="gizli")
    # uvicorn ile: uvicorn.run(app, host="0.0.0.0", port=5000)
"""
from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .auth import check_api_key, get_api_key_dep
from .models import ApiYanit, HataYanit, KomutIstek, SeraEkleme, SeraGuncelleme


# ── Hata kodu sabitleri ────────────────────────────────────────

class HataKod:
    YETKISIZ        = "YETKISIZ"
    BULUNAMADI      = "BULUNAMADI"
    GECERSIZ_KOMUT  = "GECERSIZ_KOMUT"
    GECERSIZ_ISTEK  = "GECERSIZ_ISTEK"
    KOMUT_BASARISIZ = "KOMUT_BASARISIZ"
    SUNUCU_HATASI   = "SUNUCU_HATASI"
    RATE_LIMIT      = "RATE_LIMIT"


# ── Simülasyon Servisi (demo / geliştirme) ─────────────────────

class SeraApiServisi:
    """
    Mock API servisi — demo ve geliştirme modu.
    Gerçek sistem için MerkezApiServisi kullanın.
    """

    PROFILLER = {
        "Domates": {"minT": 15, "maxT": 30, "optT": 23, "minH": 60, "maxH": 85},
        "Biber":   {"minT": 18, "maxT": 32, "optT": 25, "minH": 55, "maxH": 80},
        "Marul":   {"minT": 10, "maxT": 22, "optT": 16, "minH": 65, "maxH": 85},
    }
    SERALAR = {
        "s1": {"id": "s1", "isim": "Sera A", "bitki": "Domates", "alan": 500, "esp32_ip": "192.168.1.101"},
        "s2": {"id": "s2", "isim": "Sera B", "bitki": "Biber",   "alan": 300, "esp32_ip": "192.168.1.102"},
        "s3": {"id": "s3", "isim": "Sera C", "bitki": "Marul",   "alan": 200, "esp32_ip": "192.168.1.103"},
    }
    GECERLI_KOMUTLAR = frozenset({
        "SULAMA_AC", "SULAMA_KAPAT", "ISITICI_AC", "ISITICI_KAPAT",
        "SOGUTMA_AC", "SOGUTMA_KAPAT", "FAN_AC", "FAN_KAPAT",
        "ISIK_AC", "ISIK_KAPAT", "ACIL_DURDUR",
    })

    def __init__(self) -> None:
        self._seralar: dict[str, dict] = {k: dict(v) for k, v in self.SERALAR.items()}
        self._id_sayac: int = max((int(k[1:]) for k in self.SERALAR if k[1:].isdigit()), default=0)
        self._durum: dict[str, str] = {sid: "NORMAL" for sid in self._seralar}
        self._sensor: dict[str, dict] = {}
        self._komut_log: list[dict] = []
        self._baslangic = time.time()
        threading.Thread(target=self._sim_dongu, daemon=True).start()

    def _sim_dongu(self) -> None:
        s: dict[str, dict] = {}
        while True:
            # Yeni eklenen seraları simülasyona dahil et
            for sid in list(self._seralar.keys()):
                if sid not in s:
                    p = self.PROFILLER.get(self._seralar[sid].get("bitki", "Domates"), self.PROFILLER["Domates"])
                    s[sid] = {"T": float(p["optT"]), "H": 70.0, "co2": 950}
                if sid not in self._durum:
                    self._durum[sid] = "NORMAL"
            # Silinen seraları kaldır
            for sid in list(s.keys()):
                if sid not in self._seralar:
                    del s[sid]
            for sid, st in list(s.items()):
                p    = self.PROFILLER.get(self._seralar[sid]["bitki"], self.PROFILLER["Domates"])
                opt  = p["optT"]
                # Mean-reversion: değer opt'a doğru çekiliyor, küçük gürültü ekleniyor
                st["T"]   = round(st["T"]   + random.gauss(0, 0.12) + (opt      - st["T"])   * 0.05, 2)
                st["H"]   = round(st["H"]   + random.gauss(0, 0.20) + (70.0     - st["H"])   * 0.04, 2)
                st["co2"] = round(st["co2"] + random.gauss(0, 8)    + (950.0    - st["co2"]) * 0.03, 1)
                # Gerçekçi sınırlar: T opt±4°C, H 55-85%, CO₂ 800-1200 ppm
                st["T"]   = max(opt - 4,  min(opt + 4,  st["T"]))
                st["H"]   = max(55,       min(85,        st["H"]))
                st["co2"] = max(800,      min(1200,      st["co2"]))
                if   abs(st["T"] - opt) > 8: self._durum[sid] = "ACIL_DURDUR"
                elif abs(st["T"] - opt) > 5: self._durum[sid] = "ALARM"
                elif abs(st["T"] - opt) > 2: self._durum[sid] = "UYARI"
                else:                         self._durum[sid] = "NORMAL"
                self._sensor[sid] = {
                    "T":      round(st["T"], 1),
                    "H":      round(st["H"], 1),
                    "co2":    int(st["co2"]),
                    "isik":   random.randint(200, 900),
                    "toprak": random.randint(300, 700),
                    "ph":     round(random.uniform(5.8, 7.2), 2),
                    "ec":     round(random.uniform(1.4, 2.8), 2),
                    "zaman":  datetime.now().isoformat(),
                }
            time.sleep(2)

    def tum_seralar(self) -> list:
        return [
            {**s, "durum": self._durum.get(sid, "?"),
             "sensor": self._sensor.get(sid, {})}
            for sid, s in self._seralar.items()
        ]

    def sera_detay(self, sid: str) -> Optional[dict]:
        if sid not in self._seralar:
            return None
        return {
            **self._seralar[sid],
            "durum":  self._durum.get(sid, "NORMAL"),
            "sensor": self._sensor.get(sid, {}),
            "profil": self.PROFILLER.get(self._seralar[sid].get("bitki", "Domates"), {}),
        }

    def son_sensor(self, sid: str) -> Optional[dict]:
        return self._sensor.get(sid)

    def komut_gonder(self, sid: str, komut: str, kaynak: str = "kullanici",
                     kullanici_id: str = "") -> dict:
        if sid not in self._seralar:
            return {"basarili": False, "hata": f"Sera bulunamadı: {sid}"}
        k = komut.upper()
        if k not in self.GECERLI_KOMUTLAR:
            return {
                "basarili": False,
                "hata":    f"Geçersiz komut: {komut}",
                "gecerli": sorted(self.GECERLI_KOMUTLAR),
            }
        self._komut_log.append({
            "sera_id": sid, "komut": k,
            "kaynak":  kaynak, "kullanici_id": kullanici_id,
            "zaman": datetime.now().isoformat(),
        })
        return {"basarili": True, "komut": k, "sera_id": sid,
                "kaynak": kaynak, "kullanici_id": kullanici_id}

    def sera_ekle(self, data: dict) -> dict:
        self._id_sayac += 1
        sid = f"s{self._id_sayac}"
        yeni = {
            "id":       sid,
            "isim":     data["isim"],
            "bitki":    data.get("bitki", "Domates"),
            "alan":     float(data.get("alan", 100.0)),
            "esp32_ip": data.get("esp32_ip", ""),
        }
        self._seralar[sid] = yeni
        self._durum[sid] = "NORMAL"
        return yeni

    def sera_guncelle(self, sid: str, data: dict) -> Optional[dict]:
        if sid not in self._seralar:
            return None
        for k, v in data.items():
            if v is not None:
                self._seralar[sid][k] = v
        return self._seralar[sid]

    def sera_sil(self, sid: str) -> bool:
        if sid not in self._seralar:
            return False
        del self._seralar[sid]
        self._durum.pop(sid, None)
        self._sensor.pop(sid, None)
        return True

    def saglik(self) -> dict:
        up = int(time.time() - self._baslangic)
        return {
            "durum":        "CALISIYOR",
            "uptime_sn":    up,
            "uptime_fmt":   f"{up // 3600}s {(up % 3600) // 60}d",
            "seralar":      dict(self._durum),
            "alarm_sayisi": sum(
                1 for d in self._durum.values()
                if d in ("ALARM", "ACIL_DURDUR")
            ),
        }

    def metrikler(self) -> dict:
        return {
            "toplam_komut":   len(self._komut_log),
            "son_10":         self._komut_log[-10:],
            "durum_dagilimi": {
                d: sum(1 for v in self._durum.values() if v == d)
                for d in set(self._durum.values())
            },
        }

    def aktif_alarmlar(self) -> list:
        return [
            {
                "sera_id": sid,
                "isim":    self._seralar[sid]["isim"],
                "durum":   d,
                "sensor":  self._sensor.get(sid, {}),
            }
            for sid, d in self._durum.items()
            if d in ("ALARM", "ACIL_DURDUR", "UYARI") and sid in self._seralar
        ]


# ── FastAPI Uygulama Factory ───────────────────────────────────

def api_uygulamasi_olustur(
    servis: Any = None,
    api_key: Optional[str] = None,
) -> FastAPI:
    """
    FastAPI uygulaması fabrika fonksiyonu.

    Args:
        servis:  Veri kaynağı (None → mock simülasyon)
        api_key: X-API-Key değeri (None → SERA_API_KEY env'den okur)

    Returns:
        FastAPI app instance
    """
    app = FastAPI(
        title="Sera AI API",
        description="ESP32-S3 + Raspberry Pi 5 tabanlı endüstriyel sera otomasyon API'si",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Servis & key kurulumu ──────────────────────────────────

    if servis is None:
        print(
            "[API] Uyarı: servis=None → Mock simülasyon aktif. "
            "Gerçek veri için MerkezApiServisi kullanın."
        )
        servis = SeraApiServisi()

    _api_key = api_key if api_key is not None else os.getenv("SERA_API_KEY", "")

    if not _api_key:
        print("[API] Uyarı: SERA_API_KEY tanımlı değil — kimlik doğrulama devre dışı")

    auth = get_api_key_dep(_api_key)

    # ── Rate limiting ──────────────────────────────────────────

    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
        app.state.limiter = limiter
        app.add_exception_handler(
            RateLimitExceeded,
            _rate_limit_exceeded_handler,  # type: ignore[arg-type]
        )

        def limit(func):
            """Endpoint'e 60/minute rate limit uygular (request: Request gerektirir)."""
            return limiter.limit("60/minute")(func)
    except ImportError:
        print("[API] Uyarı: slowapi kurulu değil — rate limiting devre dışı")

        def limit(func):  # no-op
            return func

    # ── Global exception handler ───────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=HataYanit(
                hata=str(detail),
                kod=_durum_kodu(exc.status_code),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def genel_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=HataYanit(
                hata="Beklenmeyen sunucu hatası",
                kod=HataKod.SUNUCU_HATASI,
            ).model_dump(),
        )

    def _durum_kodu(http_status: int) -> str:
        return {
            401: HataKod.YETKISIZ,
            404: HataKod.BULUNAMADI,
            400: HataKod.GECERSIZ_ISTEK,
            422: HataKod.GECERSIZ_ISTEK,
            429: HataKod.RATE_LIMIT,
        }.get(http_status, HataKod.SUNUCU_HATASI)

    # ── 422 Validation error formatını özelleştir ──────────────

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        ilk_hata = exc.errors()[0] if exc.errors() else {}
        mesaj = ilk_hata.get("msg", "Geçersiz istek verisi")
        alan  = " → ".join(str(x) for x in ilk_hata.get("loc", []))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=HataYanit(
                hata=f"{alan}: {mesaj}" if alan else mesaj,
                kod=HataKod.GECERSIZ_ISTEK,
            ).model_dump(),
        )

    # ── Router ─────────────────────────────────────────────────

    from fastapi import APIRouter

    v1 = APIRouter(prefix="/api/v1")

    # Saglik: auth muaf, rate limit muaf
    @v1.get("/sistem/saglik", summary="Sistem sağlık durumu", tags=["Sistem"])
    async def saglik() -> JSONResponse:
        s = servis.saglik()
        http_status = 503 if s.get("alarm_sayisi", 0) > 0 else 200
        return JSONResponse(status_code=http_status, content=ApiYanit(data=s).model_dump())

    @v1.get("/seralar", summary="Tüm seralar", tags=["Seralar"])
    @limit
    async def tum_seralar(request: Request, _: None = Depends(auth)) -> JSONResponse:
        return JSONResponse(content=ApiYanit(data=servis.tum_seralar()).model_dump())

    @v1.get("/seralar/{sid}", summary="Sera detayı", tags=["Seralar"])
    @limit
    async def sera_detay(request: Request, sid: str, _: None = Depends(auth)) -> JSONResponse:
        d = servis.sera_detay(sid)
        if d is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Sera bulunamadı: {sid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=d).model_dump())

    @v1.get("/seralar/{sid}/sensor", summary="Son sensör okuma", tags=["Seralar"])
    @limit
    async def son_sensor(request: Request, sid: str, _: None = Depends(auth)) -> JSONResponse:
        s = servis.son_sensor(sid)
        if s is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(
                    hata=f"Sera bulunamadı veya henüz veri yok: {sid}",
                    kod=HataKod.BULUNAMADI,
                ).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=s).model_dump())

    @v1.post("/seralar/{sid}/komut", status_code=201, summary="Komut gönder", tags=["Seralar"])
    @limit
    async def komut_gonder(
        request: Request,
        sid: str,
        istek: KomutIstek,
        _: None = Depends(auth),
    ) -> JSONResponse:
        sonuc = servis.komut_gonder(sid, istek.komut, istek.kaynak, istek.kullanici_id or "")
        if not sonuc.get("basarili"):
            hata_mesaji = sonuc.get("hata", "Komut gönderilemedi")
            kod = HataKod.GECERSIZ_KOMUT if "gecerli" in sonuc else HataKod.BULUNAMADI
            http_st = 400 if "gecerli" in sonuc else 404
            raise HTTPException(
                status_code=http_st,
                detail=HataYanit(hata=hata_mesaji, kod=kod).model_dump(),
            )
        return JSONResponse(status_code=201, content=ApiYanit(data=sonuc).model_dump())

    @v1.get("/sistem/metrik", summary="Sistem metrikleri", tags=["Sistem"])
    @limit
    async def metrik(request: Request, _: None = Depends(auth)) -> JSONResponse:
        return JSONResponse(content=ApiYanit(data=servis.metrikler()).model_dump())

    @v1.get("/alarm", summary="Aktif alarmlar", tags=["Alarmlar"])
    @limit
    async def alarm(request: Request, _: None = Depends(auth)) -> JSONResponse:
        a = servis.aktif_alarmlar()
        return JSONResponse(
            content=ApiYanit(
                data=a,
                meta={"ts": datetime.now().isoformat(), "toplam": len(a)},  # type: ignore[arg-type]
            ).model_dump(),
        )

    # ── Kamera / Hastalık Tespiti Endpoint'leri ────────────────

    # Mock görüntü servis kayıtları: {sera_id: GorüntuServisi}
    # Demo modunda MockKamera + MockHastalıkTespit kullanılır.
    _goruntu_servisler: dict = {}
    _tespit_gecmis: dict = {}  # sera_id → list[dict]

    def _goruntu_servisi_al(sid: str):
        """Sera için GorüntuServisi döndür; yoksa mock oluştur."""
        if sid not in _goruntu_servisler:
            from ..goruntu.mock import mock_goruntu_servisi_olustur
            _goruntu_servisler[sid] = mock_goruntu_servisi_olustur()
        return _goruntu_servisler[sid]

    @v1.post(
        "/kamera/{sid}/tespit",
        status_code=200,
        summary="Kamera hastalık tespiti yap",
        tags=["Kamera"],
    )
    @limit
    async def kamera_tespit(
        request: Request,
        sid: str,
        _: None = Depends(auth),
    ) -> JSONResponse:
        # Sera var mı?
        if servis.sera_detay(sid) is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Sera bulunamadı: {sid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        try:
            gs  = _goruntu_servisi_al(sid)
            sonuc = gs.kontrol_et(sid)
        except IOError as e:
            raise HTTPException(
                status_code=503,
                detail=HataYanit(hata=f"Kamera bağlantı hatası: {e}", kod=HataKod.SUNUCU_HATASI).model_dump(),
            )
        d = sonuc.to_dict()
        _tespit_gecmis.setdefault(sid, []).append(d)
        if len(_tespit_gecmis[sid]) > 50:
            _tespit_gecmis[sid] = _tespit_gecmis[sid][-50:]
        return JSONResponse(content=ApiYanit(data=d).model_dump())

    @v1.get(
        "/kamera/{sid}/gecmis",
        summary="Son hastalık tespitleri",
        tags=["Kamera"],
    )
    @limit
    async def kamera_gecmis(
        request: Request,
        sid: str,
        son: int = 10,
        _: None = Depends(auth),
    ) -> JSONResponse:
        if servis.sera_detay(sid) is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Sera bulunamadı: {sid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        kayitlar = _tespit_gecmis.get(sid, [])[-max(1, min(son, 50)):]
        return JSONResponse(
            content=ApiYanit(
                data=kayitlar,
                meta={"sera_id": sid, "toplam": len(kayitlar)},  # type: ignore[arg-type]
            ).model_dump(),
        )

    @v1.get(
        "/kamera/ozet",
        summary="Tüm seraların son tespitleri",
        tags=["Kamera"],
    )
    @limit
    async def kamera_ozet(
        request: Request,
        _: None = Depends(auth),
    ) -> JSONResponse:
        ozet = {}
        for sid in list(_tespit_gecmis.keys()):
            gecmis = _tespit_gecmis[sid]
            if gecmis:
                ozet[sid] = gecmis[-1]
        return JSONResponse(content=ApiYanit(data=ozet).model_dump())

    @v1.post("/seralar", status_code=201, summary="Yeni sera ekle", tags=["Seralar"])
    @limit
    async def sera_ekle(
        request: Request,
        istek: SeraEkleme,
        _: None = Depends(auth),
    ) -> JSONResponse:
        yeni = servis.sera_ekle(istek.model_dump())
        return JSONResponse(status_code=201, content=ApiYanit(data=yeni).model_dump())

    @v1.put("/seralar/{sid}", summary="Sera güncelle", tags=["Seralar"])
    @limit
    async def sera_guncelle(
        request: Request,
        sid: str,
        istek: SeraGuncelleme,
        _: None = Depends(auth),
    ) -> JSONResponse:
        guncellendi = servis.sera_guncelle(sid, istek.model_dump())
        if guncellendi is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Sera bulunamadı: {sid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=guncellendi).model_dump())

    @v1.delete("/seralar/{sid}", status_code=204, summary="Sera sil", tags=["Seralar"])
    @limit
    async def sera_sil(
        request: Request,
        sid: str,
        _: None = Depends(auth),
    ) -> Response:
        silindi = servis.sera_sil(sid)
        if not silindi:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Sera bulunamadı: {sid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return Response(status_code=204)

    app.include_router(v1)

    # Prometheus metrics
    from .metrics import metrics_router_olustur
    app.include_router(metrics_router_olustur(servis))

    # 404 handler
    @app.exception_handler(404)
    async def e404(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=HataYanit(
                hata=f"Bulunamadı: {request.url.path}",
                kod=HataKod.BULUNAMADI,
            ).model_dump(),
        )

    return app
