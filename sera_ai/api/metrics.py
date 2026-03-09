"""
Prometheus Metrik Endpoint

Grafana Prometheus datasource olarak kullanılır.
Harici kütüphane gerekmez — Prometheus text formatı stdlib ile üretilir.

Prometheus text format:
  # HELP <name> <description>
  # TYPE <name> <gauge|counter|histogram>
  <name>{label="value"} <value> [timestamp_ms]

Endpoint: GET /metrics  (auth MUAF — Prometheus scraper key gerektirmez)

Mevcut metrikler:
  sera_sicaklik_celsius{sera_id}     gauge — hava sıcaklığı
  sera_nem_yuzde{sera_id}            gauge — bağıl nem
  sera_co2_ppm{sera_id}              gauge — CO₂
  sera_durum{sera_id, durum}         gauge — 1=aktif durum, 0=diğer
  sera_alarm_aktif{sera_id}          gauge — 1=alarm/acil, 0=normal
  sistem_uptime_saniye               gauge — sistem çalışma süresi
  sistem_toplam_komut                counter — toplam gönderilen komut
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


# Durum → numerik değer (Grafana'da renk kodlaması için)
_DURUM_DEGER: dict[str, int] = {
    "NORMAL":      0,
    "BEKLEME":     1,
    "BAKIM":       2,
    "UYARI":       3,
    "ALARM":       4,
    "ACIL_DURDUR": 5,
}


def prometheus_metrik_uret(servis) -> str:
    """
    SeraApiServisi'nden Prometheus text formatında metrik üretir.

    Args:
        servis: SeraApiServisi instance (veya aynı arayüzü uygulayan mock)

    Returns:
        Prometheus text format string
    """
    satirlar: list[str] = []

    def yorum(isim: str, aciklama: str, tip: str = "gauge") -> None:
        satirlar.append(f"# HELP {isim} {aciklama}")
        satirlar.append(f"# TYPE {isim} {tip}")

    def metrik(isim: str, etiketler: dict[str, str], deger: Any) -> None:
        etiket_str = ",".join(f'{k}="{v}"' for k, v in etiketler.items())
        satirlar.append(f"{isim}{{{etiket_str}}} {deger}")

    # ── Sistem metrikleri ──────────────────────────────────────
    saglik = servis.saglik()

    yorum("sistem_uptime_saniye", "Sistem çalışma süresi (saniye)")
    metrik("sistem_uptime_saniye", {}, saglik.get("uptime_sn", 0))

    yorum("sistem_alarm_sayisi", "Aktif alarm ve acil durdur sayısı")
    metrik("sistem_alarm_sayisi", {}, saglik.get("alarm_sayisi", 0))

    yorum("sistem_toplam_komut", "Toplam gönderilen komut sayısı", "counter")
    metrik("sistem_toplam_komut", {}, servis.metrikler().get("toplam_komut", 0))

    # ── Sera metrikleri ───────────────────────────────────────
    yorum("sera_sicaklik_celsius", "Sera hava sıcaklığı (°C)")
    yorum("sera_nem_yuzde", "Sera bağıl nemi (%)")
    yorum("sera_co2_ppm", "Sera CO₂ konsantrasyonu (ppm)")
    yorum("sera_isik_lux", "Sera aydınlık seviyesi (lux)")
    yorum("sera_toprak_nemi", "Toprak nemi (ham ADC değeri 0-1023)")
    yorum("sera_ph", "Çözelti pH değeri")
    yorum("sera_ec_ms_cm", "Elektriksel iletkenlik (mS/cm)")
    yorum("sera_durum_kodu",
          "Sera durumu (0=NORMAL 1=BEKLEME 2=BAKIM 3=UYARI 4=ALARM 5=ACIL)")
    yorum("sera_alarm_aktif", "Sera alarm durumunda mı (1=evet)")

    for sera in servis.tum_seralar():
        sid   = sera["id"]
        sensor = sera.get("sensor", {})
        durum  = sera.get("durum", "NORMAL")
        etiket = {"sera_id": sid, "isim": sera.get("isim", sid)}

        if sensor:
            metrik("sera_sicaklik_celsius", etiket, sensor.get("T", 0))
            metrik("sera_nem_yuzde",        etiket, sensor.get("H", 0))
            metrik("sera_co2_ppm",          etiket, sensor.get("co2", 0))
            metrik("sera_isik_lux",         etiket, sensor.get("isik", 0))
            metrik("sera_toprak_nemi",      etiket, sensor.get("toprak", 0))
            metrik("sera_ph",               etiket, sensor.get("ph", 0))
            metrik("sera_ec_ms_cm",         etiket, sensor.get("ec", 0))

        metrik("sera_durum_kodu",  etiket, _DURUM_DEGER.get(durum, -1))
        metrik("sera_alarm_aktif", etiket,
               1 if durum in ("ALARM", "ACIL_DURDUR") else 0)

    return "\n".join(satirlar) + "\n"


def metrics_route_ekle(app, servis) -> None:
    """
    Flask uygulamasına /metrics endpoint ekler.

    app.before_request auth kontrolünü bypass etmek için
    MUAF_ENDPOINTLER'e 'metrics' eklenmesi gerekir.
    Çağıran (api_uygulamasi_olustur) bunu halleder.

    Kullanım:
        metrics_route_ekle(app, servis)
    """
    @app.route("/metrics")
    def metrics():
        from flask import Response
        try:
            icerik = prometheus_metrik_uret(servis)
            return Response(
                icerik,
                mimetype="text/plain; version=0.0.4; charset=utf-8",
            )
        except Exception as e:
            return Response(
                f"# ERROR {e}\n",
                status=500,
                mimetype="text/plain",
            )
