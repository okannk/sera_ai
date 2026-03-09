"""
Kapasitif Toprak Nem Sensörü (Analog ADC)

Donanım: Kapasitif toprak nem sensörü (çeşitli markalar)
İletişim: Analog çıkış → ADC
Güç: 3.3V – 5V

Kalibrasyon değerleri:
  KURU_ADC  : Kuru topraktaki ADC değeri (sensöre göre ~2800–3200)
  ISLAK_ADC : Suya daldırıldığındaki ADC değeri (~1000–1500)

RPi'de ADC:
  RPi'nin analog girişi yoktur — ADS1115 (I2C ADC) gerekir
  Alternatif: ESP32 ADC'den MQTT üzerinden al (mevcut ESP32S3Node akışı)

ESP32-S3'te:
  Dahili 12-bit ADC: GPIO 1–10, GPIO 11–20
  Önerilen pin: GPIO 34 (ADC1_CH6, input-only)

Bu sınıf RPi + ADS1115 kombinasyonunu destekler.
ESP32 tabanlı okuma için ESP32S3Node MQTT akışını kullanın.

Gereksinim: pip install adafruit-circuitpython-ads1x15 smbus2
"""
from __future__ import annotations

from .base import SensorBase

# Kalibrasyon: sensöre göre ayarlanmalı
_KURU_ADC  = 2800   # Havada kuru → 1023 ADC değerine map edilir
_ISLAK_ADC = 1200   # Tamamen ıslak → 0 ADC değerine map edilir


class KapasitifNemSensor(SensorBase):
    """
    Kapasitif toprak nem sensörü — ADS1115 I2C ADC üzerinden.

    Değer: 0–1023 ADC (kuru=1023, ıslak=0) — SensorOkuma.toprak_nem formatı
    """

    def __init__(
        self,
        kanal: int = 0,
        i2c_adres: int = 0x48,
        kuru_adc: int = _KURU_ADC,
        islak_adc: int = _ISLAK_ADC,
    ) -> None:
        self._kanal    = kanal
        self._adres    = i2c_adres
        self._kuru     = kuru_adc
        self._islak    = islak_adc
        self._ads      = None

    @property
    def olcum_alanlari(self) -> frozenset[str]:
        return frozenset({"toprak_nem"})

    def baglan(self) -> bool:
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn

            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c, address=self._adres)
            self._kanal_obj = AnalogIn(ads, self._kanal)
            self._ads = ads
            return True
        except ImportError:
            print("[KapasitifNem] adafruit-circuitpython-ads1x15 kurulu değil")
            return False
        except Exception as e:
            print(f"[KapasitifNem] Başlatma hatası: {e}")
            return False

    def oku(self) -> dict:
        if self._ads is None:
            raise IOError("[KapasitifNem] baglan() çağrılmadı")

        try:
            ham = self._kanal_obj.value  # 0–32767 (ADS1115 16-bit)
        except Exception as e:
            raise IOError(f"[KapasitifNem] ADC okuma hatası: {e}") from e

        # 16-bit ADS1115 → sensör ADC aralığına normalize
        adc_deger = int(ham / 32767 * 4095)   # 12-bit eşdeğeri

        # 0–1023 skalasına map et (kuru=1023, ıslak=0)
        aralik = max(self._kuru - self._islak, 1)
        normalize = 1023 - int((adc_deger - self._islak) / aralik * 1023)
        toprak_nem = max(0, min(1023, normalize))

        return {"toprak_nem": toprak_nem}

    def kapat(self) -> None:
        self._ads = None
