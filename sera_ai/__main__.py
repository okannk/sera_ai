"""
Giriş Noktası — python -m sera_ai

Kullanım:
    python -m sera_ai                     # config.yaml'dan çalıştır
    python -m sera_ai --config myconf.yaml
    python -m sera_ai --adim 10           # 10 döngü, test için
"""
from __future__ import annotations

import argparse
import time

from .config.settings import konfig_yukle, tam_sistem_kur


def main():
    parser = argparse.ArgumentParser(
        description="Sera AI — Endüstriyel Kontrol Sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python -m sera_ai                    # Tam sistem, config.yaml'dan
  python -m sera_ai --adim 10          # 10 döngü (test)
  python -m sera_ai --config prod.yaml # Özel konfig
        """,
    )
    parser.add_argument("--config", default="config.yaml", help="Konfig dosyası")
    parser.add_argument("--adim",   type=int, default=None,
                        help="Kaç döngü çalıştırılsın (varsayılan: sonsuz)")
    args = parser.parse_args()

    konfig = konfig_yukle(args.config)
    merkez = tam_sistem_kur(konfig)

    print("\n" + "═" * 60)
    print("  SERA AI — ENDÜSTRİYEL KONTROL SİSTEMİ")
    print(f"  Saha: {konfig.seralar[0].saha_donanim if konfig.seralar else '?'}")
    print(f"  Merkez: {konfig.merkez_donanim}")
    print(f"  Seralar: {', '.join(s.isim for s in konfig.seralar)}")
    print("═" * 60 + "\n")

    merkez.baslat()
    try:
        adim = 0
        while args.adim is None or adim < args.adim:
            time.sleep(konfig.sensor_interval_sn)
            adim += 1
            if args.adim:
                print(f"[{adim}/{args.adim}] Çalışıyor...")
    except KeyboardInterrupt:
        print("\n[Sistem] Kullanıcı durdurdu (Ctrl+C)")
    finally:
        merkez.durdur()
        print("\n[Sistem] Kapatıldı.")

    print("\n" + "═" * 60)
    print("  DURUM RAPORU")
    print("═" * 60)
    for sid, bilgi in merkez.tum_durum().items():
        print(f"  {sid}: {bilgi.get('durum','?')} | {bilgi.get('cb','-')}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
