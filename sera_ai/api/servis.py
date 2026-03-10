"""
MerkezApiServisi — MerkezKontrolBase'i API arayüzüne bağlar.

Neden bu katman?
  Flask route'ları sadece dict/list döndüren metodlar bekler.
  MerkezKontrolBase ise SensorOkuma, Komut enum, tum_durum() dict döndürür.
  Bu sınıf ikisi arasında köprü kurar:
    - Komut string'ini Komut enum'a çevirir
    - SistemKonfig'den sera metadata'sını okur
    - tum_durum() çıktısını API formatına dönüştürür

Kullanım:
    merkez = RaspberryPiMerkez(konfig)
    # ... node_ekle, baslat ...
    servis = MerkezApiServisi(merkez, konfig)
    app = api_uygulamasi_olustur(servis=servis)
    app.run(port=5000)

Demo / geliştirme modunda SeraApiServisi (app.py içinde) kullanılmaya devam eder.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from ..domain.models import Komut, SistemKonfig
from ..merkez.base import MerkezKontrolBase

# Komut string → Komut enum (API'den gelen string değer → iç enum)
_KOMUT_MAP: dict[str, Komut] = {k.value: k for k in Komut}


class MerkezApiServisi:
    """
    MerkezKontrolBase + SistemKonfig → API servis arayüzü.

    api_uygulamasi_olustur(servis=MerkezApiServisi(...)) ile kullanılır.
    Mock servis ile aynı duck-typed arayüzü uygular:
      tum_seralar(), sera_detay(), son_sensor(),
      komut_gonder(), saglik(), metrikler(), aktif_alarmlar()
    """

    def __init__(self, merkez: MerkezKontrolBase, konfig: SistemKonfig) -> None:
        self.merkez    = merkez
        self.konfig    = konfig
        self._baslangic = time.time()
        # Sera id → konfig hızlı erişim
        self._sera_map = {s.id: s for s in konfig.seralar}

    # ── Yardımcı ──────────────────────────────────────────────

    def _tum_durum(self) -> dict:
        """merkez.tum_durum() önbelleğe almadan çağır."""
        return self.merkez.tum_durum()

    # ── API arayüzü ───────────────────────────────────────────

    def tum_seralar(self) -> list:
        """Tüm seraları durum ve son sensör verisiyle döndür."""
        durum = self._tum_durum()
        sonuc = []
        for sera in self.konfig.seralar:
            d = durum.get(sera.id, {})
            sonuc.append({
                "id":     sera.id,
                "isim":   sera.isim,
                "bitki":  sera.bitki,
                "alan":   sera.alan_m2,
                "durum":  d.get("durum", "BILINMIYOR"),
                "sensor": d.get("sensor"),
            })
        return sonuc

    def sera_detay(self, sid: str) -> Optional[dict]:
        """Tek sera: metadata + durum + son sensör + profil."""
        sera = self._sera_map.get(sid)
        if not sera:
            return None
        d      = self._tum_durum().get(sid, {})
        profil = self.konfig.profil_al(sera.bitki)
        return {
            "id":     sera.id,
            "isim":   sera.isim,
            "bitki":  sera.bitki,
            "alan":   sera.alan_m2,
            "durum":  d.get("durum", "BILINMIYOR"),
            "sensor": d.get("sensor"),
            "profil": {
                "min_T": profil.min_T, "max_T": profil.max_T, "opt_T": profil.opt_T,
                "min_H": profil.min_H, "max_H": profil.max_H,
                "opt_CO2": profil.opt_CO2,
            },
            "cb":             d.get("cb"),
            "son_guncelleme": d.get("son_guncelleme"),
        }

    def son_sensor(self, sid: str) -> Optional[dict]:
        """Sadece son sensör okuma dict'i."""
        d = self._tum_durum().get(sid)
        return d.get("sensor") if d else None

    def komut_gonder(self, sid: str, komut_str: str, kaynak: str = "api") -> dict:
        """
        Komut string'ini Komut enum'a çevirip merkeze ilet.

        Returns:
            {"basarili": True, "komut": ..., "sera_id": ...}
            {"basarili": False, "hata": ..., ["gecerli": ...]}
        """
        if sid not in self._sera_map:
            return {"basarili": False, "hata": f"Sera bulunamadı: {sid}"}

        k = komut_str.upper()
        if k not in _KOMUT_MAP:
            return {
                "basarili": False,
                "hata":     f"Geçersiz komut: {komut_str}",
                "gecerli":  sorted(_KOMUT_MAP.keys()),
            }

        basarili = self.merkez.komut_gonder(sid, _KOMUT_MAP[k])
        if basarili:
            return {"basarili": True, "komut": k, "sera_id": sid}
        return {
            "basarili": False,
            "hata": "Komut iletilemedi (circuit breaker açık veya node yanıtsız)",
        }

    def saglik(self) -> dict:
        """Sistem sağlık durumu — auth muaf endpoint için."""
        up    = int(time.time() - self._baslangic)
        durum = self._tum_durum()
        sera_durumlari = {
            sid: d.get("durum", "BILINMIYOR")
            for sid, d in durum.items()
        }
        return {
            "durum":       "CALISIYOR",
            "uptime_sn":   up,
            "uptime_fmt":  f"{up // 3600}s {(up % 3600) // 60}d",
            "seralar":     sera_durumlari,
            "alarm_sayisi": sum(
                1 for d in sera_durumlari.values()
                if d in ("ALARM", "ACIL_DURDUR")
            ),
        }

    def metrikler(self) -> dict:
        """İstatistik özeti."""
        durum = self._tum_durum()
        durum_degerleri = [d.get("durum", "BILINMIYOR") for d in durum.values()]
        return {
            "sera_sayisi": len(self.konfig.seralar),
            "durum_dagilimi": {
                d: durum_degerleri.count(d)
                for d in set(durum_degerleri)
            },
            "son_guncelleme": {
                sid: d.get("son_guncelleme")
                for sid, d in durum.items()
            },
        }

    def aktif_alarmlar(self) -> list:
        """UYARI, ALARM veya ACİL_DURDUR durumundaki seralar."""
        durum = self._tum_durum()
        return [
            {
                "sera_id": sid,
                "isim":    self._sera_map[sid].isim if sid in self._sera_map else sid,
                "durum":   d.get("durum"),
                "sensor":  d.get("sensor"),
            }
            for sid, d in durum.items()
            if d.get("durum") in ("UYARI", "ALARM", "ACIL_DURDUR")
        ]
