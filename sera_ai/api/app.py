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
from .models import ApiYanit, HataYanit, KomutIstek, SeraEkleme, SeraGuncelleme, CihazKayitIstek, KayitTalebiIstek


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


# ── Provisioning Simülasyon Servisi (demo / geliştirme) ───────

class ProvisioningApiServisi:
    """
    Mock Zero-Touch Provisioning servisi.
    Başlangıçta 1 bekleyen talep içerir (test için).
    """

    def __init__(self) -> None:
        import uuid as _uuid
        self._talepler:    dict[str, dict] = {}
        self._token_cache: dict[str, str]  = {}
        self._sira = 3  # 3 mevcut mock cihaz var

        # 1 mock bekleyen talep
        _tid = str(_uuid.uuid4())
        self._talepler[_tid] = {
            "talep_id":          _tid,
            "mac_adresi":        "A4:CF:12:78:5B:09",
            "sera_id":           "s1",
            "baglanti_tipi":     "WiFi",
            "firmware_versiyon": "1.0.0",
            "talep_zamani":      (datetime.now() - __import__("datetime").timedelta(minutes=3)).isoformat(),
            "durum":             "BEKLEMEDE",
            "cihaz_id":          "",
        }

    def bekleyen_talepler(self) -> list:
        return [t for t in self._talepler.values() if t["durum"] == "BEKLEMEDE"]

    def tum_talepler(self) -> list:
        return list(self._talepler.values())

    def kayit_talebi(self, data: dict) -> dict:
        import uuid as _uuid
        tid = str(_uuid.uuid4())
        self._talepler[tid] = {
            "talep_id":          tid,
            "mac_adresi":        data.get("mac", ""),
            "sera_id":           data.get("sera_id", ""),
            "baglanti_tipi":     data.get("baglanti_tipi", "WiFi"),
            "firmware_versiyon": data.get("firmware_versiyon", "1.0.0"),
            "talep_zamani":      datetime.now().isoformat(),
            "durum":             "BEKLEMEDE",
            "cihaz_id":          "",
        }
        return {"talep_id": tid, "durum": "BEKLEMEDE"}

    def onayla(self, talep_id: str) -> Optional[dict]:
        t = self._talepler.get(talep_id)
        if not t or t["durum"] != "BEKLEMEDE":
            return None
        import secrets as _sec
        self._sira += 1
        cihaz_id = f"SERA-IST01-{self._sira:03d}"
        token    = _sec.token_urlsafe(32)
        t["durum"]    = "ONAYLANDI"
        t["cihaz_id"] = cihaz_id
        self._token_cache[talep_id] = token
        return {"talep_id": talep_id, "cihaz_id": cihaz_id, "token": token}

    def reddet(self, talep_id: str) -> bool:
        t = self._talepler.get(talep_id)
        if not t or t["durum"] != "BEKLEMEDE":
            return False
        t["durum"] = "REDDEDILDI"
        return True

    def durum(self, talep_id: str) -> Optional[dict]:
        t = self._talepler.get(talep_id)
        if not t:
            return None
        r = {"durum": t["durum"], "talep_id": talep_id}
        if t["durum"] == "ONAYLANDI":
            r["cihaz_id"] = t["cihaz_id"]
            r["token"]    = self._token_cache.get(talep_id, "")
        return r


# ── Cihaz Simülasyon Servisi (demo / geliştirme) ──────────────

class CihazApiServisi:
    """
    Mock cihaz yönetim servisi — demo ve geliştirme modu.
    3 önceden tanımlı ESP32 cihazı ile başlar; yeni kayıt, şifre sıfırlama,
    silme işlemlerini bellekte simüle eder.
    """

    def __init__(self) -> None:
        now = datetime.now()
        self._cihazlar: dict[str, dict] = {
            "SERA-IST01-001": {
                "cihaz_id": "SERA-IST01-001", "tesis_kodu": "IST01", "sera_id": "s1",
                "seri_no": "A1B2C3D4E5F6", "mac_adresi": "A4:CF:12:78:5B:01",
                "baglanti_tipi": "WiFi", "firmware_versiyon": "1.2.0",
                "son_gorulen": now.isoformat(), "aktif": True,
            },
            "SERA-IST01-002": {
                "cihaz_id": "SERA-IST01-002", "tesis_kodu": "IST01", "sera_id": "s2",
                "seri_no": "B2C3D4E5F6A1", "mac_adresi": "A4:CF:12:78:5B:02",
                "baglanti_tipi": "Ethernet", "firmware_versiyon": "1.2.0",
                "son_gorulen": now.isoformat(), "aktif": True,
            },
            "SERA-IST01-003": {
                "cihaz_id": "SERA-IST01-003", "tesis_kodu": "IST01", "sera_id": "s3",
                "seri_no": "C3D4E5F6A1B2", "mac_adresi": "A4:CF:12:78:5B:03",
                "baglanti_tipi": "RS485", "firmware_versiyon": "1.1.0",
                "son_gorulen": (now.replace(second=max(0, now.second - 45))).isoformat(),
                "aktif": True,
            },
        }
        self._sira = 3
        # Canlı cihazlar için kalp atışı simülasyonu
        threading.Thread(target=self._kalp_sim, daemon=True).start()

    def _kalp_sim(self) -> None:
        """001 ve 002 cihazlarını canlı tut, 003'ü gecikmeli simüle et."""
        import random
        while True:
            now = datetime.now()
            for cid in ("SERA-IST01-001", "SERA-IST01-002"):
                if cid in self._cihazlar:
                    self._cihazlar[cid]["son_gorulen"] = now.isoformat()
            # 003: zaman zaman gecikme simülasyonu
            if "SERA-IST01-003" in self._cihazlar:
                delay = random.choice([10, 10, 10, 45, 120])  # çoğunlukla gecikme
                from datetime import timedelta
                self._cihazlar["SERA-IST01-003"]["son_gorulen"] = (
                    now - timedelta(seconds=delay)
                ).isoformat()
            time.sleep(20)

    def _durum_hesapla(self, son_gorulen_str: str) -> str:
        try:
            son = datetime.fromisoformat(son_gorulen_str)
        except Exception:
            return "BILINMIYOR"
        delta = (datetime.now() - son).total_seconds()
        if delta < 30:   return "CEVRIMICI"
        if delta < 90:   return "GECIKMELI"
        return "KOPUK"

    def _cihaz_dict(self, c: dict) -> dict:
        return {**c, "durum": self._durum_hesapla(c["son_gorulen"])}

    def listele(self) -> list[dict]:
        return [self._cihaz_dict(c) for c in self._cihazlar.values()]

    def detay(self, cid: str) -> Optional[dict]:
        c = self._cihazlar.get(cid)
        return self._cihaz_dict(c) if c else None

    def kayit_et(self, data: dict) -> dict:
        """Yeni cihaz ekle. Returns: {cihaz, sifre, firmware_konfig}"""
        import secrets as _sec
        self._sira += 1
        tesis = data["tesis_kodu"].strip().upper()
        cid   = f"SERA-{tesis}-{self._sira:03d}"
        sifre = _sec.token_urlsafe(16)
        cihaz = {
            "cihaz_id":          cid,
            "tesis_kodu":        tesis,
            "sera_id":           data["sera_id"],
            "seri_no":           __import__("uuid").uuid4().hex[:12].upper(),
            "mac_adresi":        data.get("mac_adresi", ""),
            "baglanti_tipi":     data.get("baglanti_tipi", "WiFi"),
            "firmware_versiyon": data.get("firmware_versiyon", "1.0.0"),
            "son_gorulen":       datetime.now().isoformat(),
            "aktif":             True,
        }
        self._cihazlar[cid] = cihaz
        sera_id = data["sera_id"]
        konfig = {
            "cihaz_id":               cid,
            "mqtt_host":              "mqtt.sera-ai.local",
            "mqtt_port":              1883,
            "mqtt_kullanici":         cid,
            "mqtt_sifre":             sifre,
            "sensor_topic":           f"sera/{tesis}/{sera_id}/sensor",
            "komut_topic":            f"sera/{tesis}/{sera_id}/komut",
            "kalp_atisi_topic":       f"cihaz/{cid}/kalp_atisi",
            "kalp_atisi_interval_sn": 30,
            "sensor_interval_sn":     5,
            "wifi_ssid":              "",
            "wifi_sifre":             "",
        }
        return {"cihaz": self._cihaz_dict(cihaz), "sifre": sifre, "firmware_konfig": konfig}

    def sifre_sifirla(self, cid: str) -> Optional[dict]:
        if cid not in self._cihazlar:
            return None
        import secrets as _sec
        sifre = _sec.token_urlsafe(16)
        return {"cihaz_id": cid, "sifre": sifre}

    def sil(self, cid: str) -> bool:
        if cid not in self._cihazlar:
            return False
        del self._cihazlar[cid]
        return True

    def detay_genisletilmis(self, cid: str) -> Optional[dict]:
        """Genişletilmiş cihaz detayı: sensör sağlığı, aktüatörler, bağlantı geçmişi."""
        import datetime as _dt
        c = self._cihazlar.get(cid)
        if c is None:
            return None

        now = datetime.now()

        if cid == "SERA-IST01-001":
            sensorler = [
                {
                    "tip": "SHT31", "adres": "0x44", "baglanti": "I2C",
                    "son_deger": {"sicaklik": 23.4, "nem": 68.0},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.98,
                },
                {
                    "tip": "MH-Z19C", "adres": "UART", "baglanti": "Serial",
                    "son_deger": {"co2": 985},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.97,
                },
                {
                    "tip": "BH1750", "adres": "0x23", "baglanti": "I2C",
                    "son_deger": {"isik": 4500},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.99,
                },
                {
                    "tip": "Kapasitif", "adres": "ADS1115", "baglanti": "I2C ADC",
                    "son_deger": {"toprak_nem": 62.0},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.96,
                },
            ]
            sinyal_gucu = -65
            uptime_saniye = 14400
            yeniden_baslama_sayisi = 2
            bellek_bos = 180000
            cpu_sicakligi = 45.2

        elif cid == "SERA-IST01-002":
            sensorler = [
                {
                    "tip": "SHT31", "adres": "0x44", "baglanti": "I2C",
                    "son_deger": {"sicaklik": 25.1, "nem": 66.0},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.97,
                },
                {
                    "tip": "MH-Z19C", "adres": "UART", "baglanti": "Serial",
                    "son_deger": None,
                    "saglik": "arizali",
                    "aciklama": "10 ardışık okuma hatası — UART bağlantısı kopuk olabilir",
                    "son_gecerli_okuma": (now - _dt.timedelta(minutes=18)).isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 10, "saglik_skoru": 0.0,
                },
                {
                    "tip": "BH1750", "adres": "0x23", "baglanti": "I2C",
                    "son_deger": {"isik": 3800},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.99,
                },
                {
                    "tip": "Kapasitif", "adres": "ADS1115", "baglanti": "I2C ADC",
                    "son_deger": {"toprak_nem": 55.0},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.95,
                },
            ]
            sinyal_gucu = -72
            uptime_saniye = 7200
            yeniden_baslama_sayisi = 5
            bellek_bos = 145000
            cpu_sicakligi = 48.7

        elif cid == "SERA-IST01-003":
            frozen_time = now - _dt.timedelta(minutes=12)
            sensorler = [
                {
                    "tip": "SHT31", "adres": "0x44", "baglanti": "I2C",
                    "son_deger": {"sicaklik": 16.2, "nem": 74.8},
                    "saglik": "pik",
                    "aciklama": "Son 1 saatte 3 pik tespit edildi (Z-score > 3)",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 3, "ardisik_hata": 0, "saglik_skoru": 0.94,
                },
                {
                    "tip": "MH-Z19C", "adres": "UART", "baglanti": "Serial",
                    "son_deger": {"co2": 820},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.97,
                },
                {
                    "tip": "BH1750", "adres": "0x23", "baglanti": "I2C",
                    "son_deger": {"isik": 2100},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.99,
                },
                {
                    "tip": "Kapasitif", "adres": "ADS1115", "baglanti": "I2C ADC",
                    "son_deger": {"toprak_nem": 45.2},
                    "saglik": "donmus",
                    "aciklama": "12 dakikadır aynı değer (±0.1 tolerans içinde)",
                    "son_gecerli_okuma": frozen_time.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.40,
                },
            ]
            sinyal_gucu = -81
            uptime_saniye = 3600
            yeniden_baslama_sayisi = 8
            bellek_bos = 120000
            cpu_sicakligi = 52.1
        else:
            sensorler = [
                {
                    "tip": "SHT31", "adres": "0x44", "baglanti": "I2C",
                    "son_deger": {"sicaklik": 22.0, "nem": 65.0},
                    "saglik": "normal", "aciklama": "Normal çalışıyor",
                    "son_gecerli_okuma": now.isoformat(),
                    "pik_sayisi_son_1saat": 0, "ardisik_hata": 0, "saglik_skoru": 0.95,
                },
            ]
            sinyal_gucu = -70
            uptime_saniye = 3600
            yeniden_baslama_sayisi = 1
            bellek_bos = 160000
            cpu_sicakligi = 44.0

        aktuatorler = [
            {
                "tip": "sulama", "gpio": 25, "durum": "kapali",
                "son_degisim": (now - _dt.timedelta(minutes=30)).isoformat(),
                "toplam_acik_sure": 7200,
            },
            {
                "tip": "isitici", "gpio": 26,
                "durum": "acik" if cid == "SERA-IST01-003" else "kapali",
                "son_degisim": (now - _dt.timedelta(minutes=5)).isoformat(),
                "toplam_acik_sure": 2700,
            },
            {
                "tip": "sogutma", "gpio": 27, "durum": "kapali",
                "son_degisim": (now - _dt.timedelta(hours=1)).isoformat(),
                "toplam_acik_sure": 1800,
            },
            {
                "tip": "fan", "gpio": 28,
                "durum": "acik" if cid == "SERA-IST01-001" else "kapali",
                "son_degisim": (now - _dt.timedelta(minutes=15)).isoformat(),
                "toplam_acik_sure": 900,
            },
        ]

        baglanti_gecmisi = [
            {
                "zaman": (now - _dt.timedelta(hours=4)).isoformat(),
                "olay": "BAGLANDI",
                "detay": f"{c.get('baglanti_tipi', 'WiFi')} — IP: 192.168.1.10{cid[-1]}",
            },
            {
                "zaman": (now - _dt.timedelta(hours=4, minutes=2)).isoformat(),
                "olay": "KOPTU",
                "detay": "WiFi sinyal kaybı",
            },
            {
                "zaman": (now - _dt.timedelta(hours=8)).isoformat(),
                "olay": "BAGLANDI",
                "detay": f"{c.get('baglanti_tipi', 'WiFi')} — güç sıfırlama sonrası",
            },
        ]

        return {
            **self._cihaz_dict(c),
            "sinyal_gucu":            sinyal_gucu,
            "uptime_saniye":          uptime_saniye,
            "yeniden_baslama_sayisi": yeniden_baslama_sayisi,
            "bellek_bos":             bellek_bos,
            "cpu_sicakligi":          cpu_sicakligi,
            "sensorler":              sensorler,
            "aktuatorler":            aktuatorler,
            "baglanti_gecmisi":       baglanti_gecmisi,
        }

    def sensor_gecmis(self, cid: str, sensor_tip: str) -> Optional[dict]:
        """Belirli sensörün son 1 saatlik ölçümleri. Pikler işaretli."""
        import random as _rnd
        import datetime as _dt
        c = self._cihazlar.get(cid)
        if c is None:
            return None

        now = datetime.now()
        _rnd.seed(hash(cid + sensor_tip) % (2 ** 31))

        config_map = {
            "SHT31_sicaklik":   {"baz": 23.0, "std": 0.3, "birim": "°C",  "min": 15, "max": 30},
            "SHT31_nem":        {"baz": 68.0, "std": 1.0, "birim": "%",   "min": 60, "max": 85},
            "MH-Z19C_co2":      {"baz": 900.0, "std": 20, "birim": "ppm", "min": 400, "max": 1500},
            "BH1750_isik":      {"baz": 4500.0, "std": 200, "birim": "lux", "min": 0, "max": 65535},
            "Kapasitif_toprak_nem": {"baz": 60.0, "std": 1.0, "birim": "%", "min": 0, "max": 100},
        }
        cfg = config_map.get(sensor_tip, {"baz": 50.0, "std": 2.0, "birim": "?", "min": 0, "max": 100})

        baz   = cfg["baz"]
        std   = cfg["std"]
        deger = baz

        pik_dakikalari: set[int] = set()
        if cid == "SERA-IST01-003" and sensor_tip == "SHT31_sicaklik":
            pik_dakikalari = {15, 35, 52}

        # Kapasitif donmuş değer: son 20 dakika sabit
        if cid == "SERA-IST01-003" and "Kapasitif" in sensor_tip:
            olcumler = []
            for i in range(60):
                t = now - _dt.timedelta(minutes=59 - i)
                d = baz if i < 40 else 45.2
                olcumler.append({"zaman": t.isoformat(), "deger": round(d, 1), "pik": False})
            return {
                "cihaz_id": cid, "sensor_tip": sensor_tip,
                "birim": cfg["birim"],
                "normal_aralik": {"min": cfg["min"], "max": cfg["max"]},
                "olcumler": olcumler,
            }

        olcumler = []
        for i in range(60):
            t   = now - _dt.timedelta(minutes=59 - i)
            pik = i in pik_dakikalari
            if pik:
                d = deger + _rnd.gauss(15, 2)
            else:
                deger = deger + _rnd.gauss(0, std * 0.3) + (baz - deger) * 0.1
                d     = deger
            olcumler.append({"zaman": t.isoformat(), "deger": round(d, 1), "pik": pik})

        return {
            "cihaz_id": cid, "sensor_tip": sensor_tip,
            "birim": cfg["birim"],
            "normal_aralik": {"min": cfg["min"], "max": cfg["max"]},
            "olcumler": olcumler,
        }

    def saglik_ozet(self) -> dict:
        """Tüm cihazların sağlık özeti."""
        arizali = pik = donmus = uyari = 0
        cihaz_durumlari = []

        for cid in self._cihazlar:
            detay = self.detay_genisletilmis(cid)
            if detay is None:
                continue
            cihaz_alarmlar = []
            for s in detay.get("sensorler", []):
                saglik = s.get("saglik", "normal")
                if saglik == "arizali":
                    arizali += 1
                    cihaz_alarmlar.append({"tip": s["tip"], "saglik": saglik})
                elif saglik == "pik":
                    pik += 1
                    cihaz_alarmlar.append({"tip": s["tip"], "saglik": saglik})
                elif saglik == "donmus":
                    donmus += 1
                    cihaz_alarmlar.append({"tip": s["tip"], "saglik": saglik})
                elif saglik == "uyari":
                    uyari += 1
            cihaz_durumlari.append({
                "cihaz_id": cid, "durum": detay["durum"], "alarmlar": cihaz_alarmlar,
            })

        return {
            "toplam_cihaz":   len(self._cihazlar),
            "arizali_sensor": arizali,
            "pik_sensor":     pik,
            "donmus_sensor":  donmus,
            "uyari_sensor":   uyari,
            "genel_saglik":   "KRITIK" if arizali > 0 else ("UYARI" if (pik + donmus + uyari) > 0 else "IYI"),
            "cihazlar":       cihaz_durumlari,
        }


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

    # ── Provisioning endpoint'leri ─────────────────────────────

    prov_servis = ProvisioningApiServisi()

    # ESP32 tarafından çağrılır — auth muaf (cihaz henüz kayıtlı değil)
    @v1.post(
        "/provisioning/kayit-talebi",
        status_code=201,
        summary="ESP32 kayıt talebi gönder",
        tags=["Provisioning"],
    )
    async def kayit_talebi(istek: KayitTalebiIstek) -> JSONResponse:
        sonuc = prov_servis.kayit_talebi(istek.model_dump())
        return JSONResponse(status_code=201, content=ApiYanit(data=sonuc).model_dump())

    # ESP32 tarafından poll edilir — auth muaf
    @v1.get(
        "/provisioning/durum/{talep_id}",
        summary="Provisioning talep durumu",
        tags=["Provisioning"],
    )
    async def provisioning_durum(talep_id: str) -> JSONResponse:
        d = prov_servis.durum(talep_id)
        if d is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Talep bulunamadı: {talep_id}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=d).model_dump())

    # Dashboard tarafından çağrılır — auth gerekli
    @v1.get(
        "/provisioning/bekleyen-talepler",
        summary="Bekleyen provisioning talepleri",
        tags=["Provisioning"],
    )
    @limit
    async def bekleyen_talepler(request: Request, _: None = Depends(auth)) -> JSONResponse:
        talepler = prov_servis.bekleyen_talepler()
        return JSONResponse(content=ApiYanit(data=talepler).model_dump())

    @v1.post(
        "/provisioning/onayla/{talep_id}",
        status_code=200,
        summary="Provisioning talebini onayla",
        tags=["Provisioning"],
    )
    @limit
    async def provisioning_onayla(
        request: Request,
        talep_id: str,
        _: None = Depends(auth),
    ) -> JSONResponse:
        sonuc = prov_servis.onayla(talep_id)
        if sonuc is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(
                    hata=f"Talep bulunamadı veya zaten işlendi: {talep_id}",
                    kod=HataKod.BULUNAMADI,
                ).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=sonuc).model_dump())

    @v1.post(
        "/provisioning/reddet/{talep_id}",
        status_code=200,
        summary="Provisioning talebini reddet",
        tags=["Provisioning"],
    )
    @limit
    async def provisioning_reddet(
        request: Request,
        talep_id: str,
        _: None = Depends(auth),
    ) -> JSONResponse:
        silindi = prov_servis.reddet(talep_id)
        if not silindi:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(
                    hata=f"Talep bulunamadı veya zaten işlendi: {talep_id}",
                    kod=HataKod.BULUNAMADI,
                ).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data={"durum": "REDDEDILDI"}).model_dump())

    # ── Cihaz endpoint'leri ────────────────────────────────────

    cihaz_servis = CihazApiServisi()

    @v1.get("/cihazlar", summary="Tüm cihazlar", tags=["Cihazlar"])
    @limit
    async def cihaz_listele(request: Request, _: None = Depends(auth)) -> JSONResponse:
        return JSONResponse(content=ApiYanit(data=cihaz_servis.listele()).model_dump())

    # !! Static route'lar {cid} dynamic route'lardan ÖNCE tanımlanmalı !!

    @v1.get("/cihazlar/saglik-ozet", summary="Cihaz sağlık özeti", tags=["Cihazlar"])
    @limit
    async def cihaz_saglik_ozet(request: Request, _: None = Depends(auth)) -> JSONResponse:
        return JSONResponse(content=ApiYanit(data=cihaz_servis.saglik_ozet()).model_dump())

    @v1.post("/cihazlar/kayit", status_code=201, summary="Yeni cihaz kaydet", tags=["Cihazlar"])
    @limit
    async def cihaz_kayit(
        request: Request,
        istek: CihazKayitIstek,
        _: None = Depends(auth),
    ) -> JSONResponse:
        sonuc = cihaz_servis.kayit_et(istek.model_dump())
        return JSONResponse(status_code=201, content=ApiYanit(data=sonuc).model_dump())

    @v1.get("/cihazlar/{cid}/detay", summary="Cihaz genişletilmiş detay", tags=["Cihazlar"])
    @limit
    async def cihaz_detay_genisletilmis(
        request: Request, cid: str, _: None = Depends(auth)
    ) -> JSONResponse:
        c = cihaz_servis.detay_genisletilmis(cid)
        if c is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=c).model_dump())

    @v1.get(
        "/cihazlar/{cid}/sensor-gecmis/{sensor_tip}",
        summary="Sensör geçmişi (son 1 saat)",
        tags=["Cihazlar"],
    )
    @limit
    async def cihaz_sensor_gecmis(
        request: Request, cid: str, sensor_tip: str, _: None = Depends(auth)
    ) -> JSONResponse:
        gecmis = cihaz_servis.sensor_gecmis(cid, sensor_tip)
        if gecmis is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=gecmis).model_dump())

    @v1.get("/cihazlar/{cid}", summary="Cihaz detayı", tags=["Cihazlar"])
    @limit
    async def cihaz_detay(request: Request, cid: str, _: None = Depends(auth)) -> JSONResponse:
        c = cihaz_servis.detay(cid)
        if c is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=c).model_dump())

    @v1.get("/cihazlar/{cid}/durum", summary="Cihaz bağlantı durumu", tags=["Cihazlar"])
    @limit
    async def cihaz_durum(request: Request, cid: str, _: None = Depends(auth)) -> JSONResponse:
        c = cihaz_servis.detay(cid)
        if c is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data={
            "cihaz_id":     c["cihaz_id"],
            "durum":        c["durum"],
            "son_gorulen":  c["son_gorulen"],
        }).model_dump())

    @v1.post(
        "/cihazlar/{cid}/sifre-sifirla",
        status_code=200,
        summary="Cihaz şifresini sıfırla",
        tags=["Cihazlar"],
    )
    @limit
    async def cihaz_sifre_sifirla(
        request: Request,
        cid: str,
        _: None = Depends(auth),
    ) -> JSONResponse:
        sonuc = cihaz_servis.sifre_sifirla(cid)
        if sonuc is None:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
            )
        return JSONResponse(content=ApiYanit(data=sonuc).model_dump())

    @v1.delete("/cihazlar/{cid}", status_code=204, summary="Cihaz sil", tags=["Cihazlar"])
    @limit
    async def cihaz_sil(
        request: Request,
        cid: str,
        _: None = Depends(auth),
    ) -> Response:
        silindi = cihaz_servis.sil(cid)
        if not silindi:
            raise HTTPException(
                status_code=404,
                detail=HataYanit(hata=f"Cihaz bulunamadı: {cid}", kod=HataKod.BULUNAMADI).model_dump(),
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
