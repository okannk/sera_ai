"""
Giriş Noktası — python -m sera_ai

Kullanım:
    python -m sera_ai --demo           # Mock sensörler, 15 adım, canlı çıktı
    python -m sera_ai --demo --adim 5  # 5 adım demo
    python -m sera_ai --config prod.yaml  # Üretim konfigürasyonu
    python -m sera_ai --adim 10        # 10 döngü çalış, sonra dur
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

# Windows terminali UTF-8'e zorla (box-drawing ve emoji karakterler için)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .config.settings import konfig_yukle, saha_node_olustur
from .application.event_bus import EventBus, OlayTur

# ANSI renkleri — durum görselleştirmesi için
_RENK = {
    "NORMAL":         "\033[92m",   # Yeşil
    "UYARI":          "\033[93m",   # Sarı
    "ALARM":          "\033[91m",   # Kırmızı
    "ACIL_DURDUR":    "\033[95m",   # Mor
    "MANUEL_KONTROL": "\033[96m",   # Cyan
    "RESET":          "\033[0m",
}


def _demo_aboneleri_ekle(bus: EventBus) -> None:
    """
    Demo modunda event bus'a canlı terminal çıktısı aboneleri ekle.
    Her olay tipine ayrı formatlı çıktı.
    """

    def sensor_yazdir(veri: dict):
        t = datetime.now().strftime("%H:%M:%S")
        print(
            f"  [{t}] {veri.get('sera_id','?'):3s} │ "
            f"T:{veri.get('T', 0):5.1f}°C  "
            f"H:{veri.get('H', 0):5.1f}%  "
            f"CO₂:{veri.get('co2', 0):4d}ppm  "
            f"Toprak:{veri.get('toprak_nem', 0):4d}"
        )

    def durum_yazdir(veri: dict):
        yeni  = veri.get("yeni", "?")
        renk  = _RENK.get(yeni, "")
        reset = _RENK["RESET"]
        print(
            f"\n  ⚡ [{veri.get('sera_id','?')}] "
            f"{veri.get('onceki','?')} → {renk}{yeni}{reset}"
            f"  ← {veri.get('sebep','')}\n"
        )

    def komut_yazdir(veri: dict):
        print(
            f"  ⚙  [{veri.get('sera_id','?')}] "
            f"Komut gönderildi: {veri.get('komut','?')}"
        )

    bus.abone_ol(OlayTur.SENSOR_OKUMA,     sensor_yazdir)
    bus.abone_ol(OlayTur.DURUM_DEGISTI,    durum_yazdir)
    bus.abone_ol(OlayTur.KOMUT_GONDERILDI, komut_yazdir)


def main():
    parser = argparse.ArgumentParser(
        description="Sera AI — Endüstriyel Kontrol Sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python -m sera_ai --demo              # 15 adım, canlı sensör çıktısı
  python -m sera_ai --demo --adim 5     # 5 adım demo
  python -m sera_ai --config prod.yaml  # Üretim konfigürasyonu
  python -m sera_ai --adim 30           # 30 döngü sonra dur
        """,
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Konfig dosyası (varsayılan: config.yaml)")
    parser.add_argument("--demo",   action="store_true",
                        help="Demo modu: mock sensörler, canlı çıktı")
    parser.add_argument("--adim",   type=int, default=None,
                        help="Kaç döngü (demo varsayılanı: 15, normal: sonsuz)")
    parser.add_argument("--api",    action="store_true",
                        help="REST API'yi gerçek merkeze bağlı başlat")
    args = parser.parse_args()

    konfig = konfig_yukle(args.config)

    if args.demo:
        # Demo modunda her şeyi mock'a zorla ve hızlandır
        for sera in konfig.seralar:
            sera.saha_donanim = "mock"
        konfig.merkez_donanim = "raspberry_pi"   # Tam kontrol döngüsü çalışsın
        konfig.sensor_interval_sn = 0.8
        if args.adim is None:
            args.adim = 15

    # Event bus — demo modunda canlı terminal çıktısı için abone eklenir
    bus = EventBus()
    if args.demo:
        _demo_aboneleri_ekle(bus)

    # Merkezi seç ve kur
    if konfig.merkez_donanim == "raspberry_pi":
        from .merkez.raspberry_pi import RaspberryPiMerkez
        merkez = RaspberryPiMerkez(konfig, olay_bus=bus)
    else:
        from .merkez.mock import MockMerkez
        merkez = MockMerkez()

    # Her seraya uygun node ekle
    for sera in konfig.seralar:
        node = saha_node_olustur(sera, konfig)
        merkez.node_ekle(sera.id, node)

    # ── Başlık ────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  SERA AI — ENDÜSTRİYEL KONTROL SİSTEMİ")
    if args.demo:
        print("  ► DEMO MODU — Mock sensörler, gerçek donanım yok")
    print(f"  Saha   : {konfig.seralar[0].saha_donanim if konfig.seralar else '?'}")
    print(f"  Merkez : {konfig.merkez_donanim}")
    print(f"  Seralar: {', '.join(s.isim for s in konfig.seralar)}")
    print(f"  Adım   : {args.adim or '∞'}  │  İnterval: {konfig.sensor_interval_sn}s")
    if args.demo:
        print("─" * 60)
        print("  Sütunlar: Saat │ Sera │ T(°C) │ H(%) │ CO₂(ppm) │ Toprak(ADC)")
    print("═" * 60)

    merkez.baslat()

    # REST API — hem demo hem gerçek modda başlatılabilir
    if args.api:
        import threading
        from .api.app import api_uygulamasi_olustur
        from .api.servis import MerkezApiServisi
        servis    = MerkezApiServisi(merkez, konfig)
        fastapi_app = api_uygulamasi_olustur(servis=servis)
        def _api_baslat():
            import uvicorn
            print(f"[API] Uvicorn → http://0.0.0.0:{konfig.api_port}")
            uvicorn.run(fastapi_app, host="0.0.0.0", port=konfig.api_port, log_level="warning")

        api_thread = threading.Thread(target=_api_baslat, name="FlaskAPI", daemon=True)
        api_thread.start()

    try:
        adim = 0
        while args.adim is None or adim < args.adim:
            time.sleep(konfig.sensor_interval_sn)
            adim += 1
    except KeyboardInterrupt:
        print("\n[Sistem] Kullanıcı durdurdu (Ctrl+C)")
    finally:
        merkez.durdur()
        if not args.demo:
            print("[Sistem] Kapatıldı.")

    # ── Durum Raporu ──────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  DURUM RAPORU")
    print("═" * 60)
    for sid, bilgi in merkez.tum_durum().items():
        durum  = bilgi.get("durum", "?")
        renk   = _RENK.get(durum, "")
        reset  = _RENK["RESET"]
        sensor = bilgi.get("sensor") or {}
        print(
            f"  {sid} │ {renk}{durum:18s}{reset} │ {bilgi.get('cb', '-')}"
        )
        if sensor:
            print(
                f"      Son: T={sensor.get('T','?')}°C  "
                f"H={sensor.get('H','?')}%  "
                f"CO₂={sensor.get('co2','?')}ppm"
            )
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
