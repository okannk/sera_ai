"""
Sensör Sağlık Analizi

Anomali tespiti: pik, donmuş değer, fiziksel sınır ihlali,
ardışık hata sayacı, sağlık skoru.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from ...domain.models import SensorSaglik, SensorDurum


class SensorSaglikAnalizi:
    """
    Stateless sensör sağlık analiz motoru.

    Her metot bağımsız çalışır — test edilebilir, DI uyumlu.
    """

    # Fiziksel olarak mümkün değer aralıkları (sensor_tipi → (min, max))
    FIZIKSEL_SINIRLAR: dict[str, tuple[float, float]] = {
        "sicaklik":  (-40.0, 85.0),
        "nem":       (0.0,   100.0),
        "co2":       (400.0, 5000.0),
        "isik":      (0.0,   65535.0),
        "toprak":    (0.0,   100.0),
    }

    # ── Temel Testler ──────────────────────────────────────────

    def pik_tespiti(self, son_10_olcum: list[float], yeni_deger: float) -> bool:
        """
        Z-score > 3 veya önceki ortalamanın ±%30 dışına çıkarsa pik.

        Neden: tek nokta anomalisi → sensör fiziksel sarsıntısı, EMI,
        güç dibi vb. Birden fazla ardışık anormal → trend → pik değil.
        """
        if len(son_10_olcum) < 3:
            return False

        n   = len(son_10_olcum)
        ort = sum(son_10_olcum) / n
        var = sum((x - ort) ** 2 for x in son_10_olcum) / n
        std = math.sqrt(var) if var > 0 else 0.0

        # Z-score kontrolü
        if std > 0 and abs(yeni_deger - ort) / std > 3.0:
            return True

        # %30 sapma kontrolü (sıfıra yakın ortalamada atla)
        if abs(ort) > 1e-6 and abs(yeni_deger - ort) / abs(ort) > 0.30:
            return True

        return False

    def donmus_deger_tespiti(self, son_20_olcum: list[float]) -> bool:
        """
        Son 5+ ölçümün tamamı ±0.1 tolerans içindeyse sensör donmuş.

        5 dakikada bir okuma → 5 okuma ≈ 5 dakika eşiği.
        """
        if len(son_20_olcum) < 5:
            return False
        son_5  = son_20_olcum[-5:]
        aralik = max(son_5) - min(son_5)
        return aralik <= 0.1

    def fiziksel_sinir_kontrolu(self, sensor_tipi: str, deger: float) -> bool:
        """True → değer fiziksel olarak mümkün. False → kalibrasyon hatası."""
        sinir = self.FIZIKSEL_SINIRLAR.get(sensor_tipi)
        if sinir is None:
            return True  # Bilinmeyen tip → kısıtlama yok
        return sinir[0] <= deger <= sinir[1]

    def ardisik_hata_kontrolu(self, hata_sayisi: int) -> SensorSaglik:
        """3 → UYARI, 10+ → ARIZALI."""
        if hata_sayisi >= 10:
            return SensorSaglik.ARIZALI
        if hata_sayisi >= 3:
            return SensorSaglik.UYARI
        return SensorSaglik.NORMAL

    # ── Bileşik Skor ──────────────────────────────────────────

    def saglik_skoru(self, sensor_durum: SensorDurum) -> float:
        """
        0.0 (çalışmıyor) — 1.0 (mükemmel).

        Temel skor saglik enum'dan, pik/hata sayısıyla ceza eklenir.
        """
        temel: dict[SensorSaglik, float] = {
            SensorSaglik.NORMAL:         1.00,
            SensorSaglik.UYARI:          0.70,
            SensorSaglik.PIK:            0.60,
            SensorSaglik.DONMUS:         0.40,
            SensorSaglik.KALIBRE_HATASI: 0.20,
            SensorSaglik.ARIZALI:        0.00,
        }
        skor = temel.get(sensor_durum.saglik, 0.50)

        # Her pik -0.02, max -0.30
        skor -= min(0.30, sensor_durum.pik_sayisi_son_1saat * 0.02)
        # Her ardışık hata -0.03, max -0.30
        skor -= min(0.30, sensor_durum.ardisik_hata_sayisi * 0.03)

        return round(max(0.0, min(1.0, skor)), 3)

    # ── Tam Analiz ────────────────────────────────────────────

    def analiz_et(
        self,
        sensor_tipi:    str,
        deger_birimi:   str,           # "sicaklik" | "nem" | "co2" | ...
        son_olcumler:   list[float],   # kronolojik, en yenisi sonda
        ardisik_hata:   int = 0,
        pik_sayisi_1sa: int = 0,
        son_gecerli_zaman: Optional[datetime] = None,
    ) -> SensorDurum:
        """
        Ana analiz metodu: ham ölçümler → SensorDurum.

        Args:
            sensor_tipi:   "SHT31", "MH-Z19C", "BH1750", "Kapasitif"
            deger_birimi:  FIZIKSEL_SINIRLAR anahtarı
            son_olcumler:  son 20 ölçüm listesi (yoksa boş)
            ardisik_hata:  consecutive error count
            pik_sayisi_1sa: peaks in last 1 hour
            son_gecerli_zaman: last successful reading datetime
        """
        now         = datetime.now()
        son_gecerli = son_gecerli_zaman or now
        son_deger   = son_olcumler[-1] if son_olcumler else float("nan")

        # 1. Arızalı mı? (çok fazla hata)
        if ardisik_hata >= 10:
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.ARIZALI,
                aciklama             = f"{ardisik_hata} ardışık okuma hatası",
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 2. Fiziksel sınır kontrolü
        if son_olcumler and not math.isnan(son_deger) and not self.fiziksel_sinir_kontrolu(deger_birimi, son_deger):
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.KALIBRE_HATASI,
                aciklama             = (
                    f"Fiziksel sınır dışı: {son_deger} "
                    f"({deger_birimi} aralığı: "
                    f"{self.FIZIKSEL_SINIRLAR.get(deger_birimi, ('?', '?'))})"
                ),
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 3. Donmuş değer
        if self.donmus_deger_tespiti(son_olcumler):
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.DONMUS,
                aciklama             = "5+ ölçümde değer değişmedi (±0.1 tolerans)",
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 4. Pik tespiti
        if len(son_olcumler) > 1 and self.pik_tespiti(son_olcumler[:-1], son_deger):
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.PIK,
                aciklama             = f"Anormal sıçrama tespit edildi (son değer: {son_deger:.1f})",
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 5. Ardışık hata → UYARI
        if ardisik_hata >= 3:
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.UYARI,
                aciklama             = f"{ardisik_hata} ardışık hata (eşik: 10)",
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 6. Pik sayısı yüksek → UYARI
        if pik_sayisi_1sa >= 5:
            return SensorDurum(
                sensor_tipi          = sensor_tipi,
                son_deger            = son_deger,
                saglik               = SensorSaglik.UYARI,
                aciklama             = f"Son 1 saatte {pik_sayisi_1sa} pik — güvenilirlik düşük",
                son_gecerli_okuma    = son_gecerli,
                ardisik_hata_sayisi  = ardisik_hata,
                pik_sayisi_son_1saat = pik_sayisi_1sa,
            )

        # 7. Normal
        return SensorDurum(
            sensor_tipi          = sensor_tipi,
            son_deger            = son_deger,
            saglik               = SensorSaglik.NORMAL,
            aciklama             = "Normal çalışıyor",
            son_gecerli_okuma    = son_gecerli,
            ardisik_hata_sayisi  = ardisik_hata,
            pik_sayisi_son_1saat = pik_sayisi_1sa,
        )

    def rapor_uret(
        self,
        sensor_verileri: dict[str, dict],
    ) -> list[SensorDurum]:
        """
        Birden fazla sensör için toplu analiz.

        Args:
            sensor_verileri: {
                "SHT31": {
                    "tip": "sicaklik",
                    "olcumler": [23.4, 23.5, ...],
                    "ardisik_hata": 0,
                    "pik_sayisi_1sa": 0,
                },
                ...
            }
        """
        sonuclar = []
        for sensor_tipi, veri in sensor_verileri.items():
            durum = self.analiz_et(
                sensor_tipi    = sensor_tipi,
                deger_birimi   = veri.get("tip", ""),
                son_olcumler   = veri.get("olcumler", []),
                ardisik_hata   = veri.get("ardisik_hata", 0),
                pik_sayisi_1sa = veri.get("pik_sayisi_1sa", 0),
            )
            sonuclar.append(durum)
        return sonuclar

    # ── Alarm Tetikleyiciler ───────────────────────────────────

    def alarm_kontrol(self, sensor_durum: SensorDurum) -> list[dict]:
        """
        Sensör durumuna göre tetiklenmesi gereken alarmları döndür.
        Her alarm: {"tur": str, "mesaj": str, "seviye": "KRITIK"|"UYARI"}
        """
        alarmlar = []

        if sensor_durum.saglik == SensorSaglik.ARIZALI:
            alarmlar.append({
                "tur":    "SENSOR_ARIZASI",
                "mesaj":  f"{sensor_durum.sensor_tipi} sensörü arızalı ({sensor_durum.ardisik_hata_sayisi} ardışık hata)",
                "seviye": "KRITIK",
            })

        if sensor_durum.pik_sayisi_son_1saat > 5:
            alarmlar.append({
                "tur":    "SENSOR_GUVENILMEZ",
                "mesaj":  f"{sensor_durum.sensor_tipi}: son 1 saatte {sensor_durum.pik_sayisi_son_1saat} pik",
                "seviye": "UYARI",
            })

        if sensor_durum.saglik == SensorSaglik.DONMUS:
            delta = (datetime.now() - sensor_durum.son_gecerli_okuma).total_seconds()
            if delta > 600:  # 10 dakika
                alarmlar.append({
                    "tur":    "SENSOR_DONMUS",
                    "mesaj":  f"{sensor_durum.sensor_tipi}: {int(delta / 60)} dakikadır aynı değer",
                    "seviye": "UYARI",
                })

        return alarmlar
