# MicroPython
# sensors.py — Sensör okuma katmanı
# Gerçek donanım lazy import ile yüklenir; yoksa simülasyon modu devreye girer.

import utime

# ---------------------------------------------------------------------------
# Simülasyon için pseudo-random sayı üreteci (MicroPython urandom desteksiz olabilir)
# ---------------------------------------------------------------------------
_rand_tohum = utime.ticks_ms()

def _rand_float() -> float:
    """0.0–1.0 arası basit LCG tabanlı pseudo-random float."""
    global _rand_tohum
    _rand_tohum = (_rand_tohum * 1664525 + 1013904223) & 0xFFFFFFFF
    return (_rand_tohum & 0xFFFF) / 65535.0

def _rand_aralik(alt: float, ust: float) -> float:
    return alt + _rand_float() * (ust - alt)

def _gurultu(merkez: float, genlik: float) -> float:
    """Merkez değer etrafında ±genlik gürültü ekle."""
    return merkez + (_rand_float() * 2 - 1) * genlik

# ---------------------------------------------------------------------------
# Simüle edilmiş referans değerler (ilk açılışta rastgele belirlenir)
# ---------------------------------------------------------------------------
_SIM = {
    "T":     _rand_aralik(20.0, 30.0),  # °C
    "H":     _rand_aralik(50.0, 80.0),  # %RH
    "co2":   int(_rand_aralik(600, 1200)),  # ppm
    "isik":  int(_rand_aralik(5000, 50000)),  # lux
    "toprak": int(_rand_aralik(300, 700)),    # 0-1023 ölçek
    "ph":    _rand_aralik(5.5, 7.5),
    "ec":    _rand_aralik(0.8, 2.5),
}

# ---------------------------------------------------------------------------
# Donanım sürücüleri — lazy import
# ---------------------------------------------------------------------------

def _sht31_oku() -> tuple:
    """SHT31-D I2C sensöründen sıcaklık ve nem oku. (float_T, float_H)"""
    from machine import I2C, Pin
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100_000)
    # Ölçüm başlat — yüksek tekrarlanabilirlik, clock stretching kapalı
    i2c.writeto(0x44, b"\x24\x00")
    utime.sleep_ms(20)
    veri = i2c.readfrom(0x44, 6)
    # CRC-8 doğrula (0x31 polinom)
    def crc8(buf):
        crc = 0xFF
        for b in buf:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc
    if crc8(veri[:2]) != veri[2] or crc8(veri[3:5]) != veri[5]:
        raise OSError("SHT31 CRC hatası")
    ham_T = (veri[0] << 8) | veri[1]
    ham_H = (veri[3] << 8) | veri[4]
    T = -45.0 + 175.0 * ham_T / 65535.0
    H = 100.0 * ham_H / 65535.0
    return round(T, 2), round(H, 2)

def _mhz19c_oku() -> int:
    """MH-Z19C UART'tan CO₂ konsantrasyonunu oku (ppm)."""
    from machine import UART
    uart = UART(1, baudrate=9600, tx=17, rx=16)
    # CO₂ okuma komutu
    uart.write(b"\xFF\x01\x86\x00\x00\x00\x00\x00\x79")
    utime.sleep_ms(100)
    yanit = uart.read(9)
    if not yanit or len(yanit) < 9:
        raise OSError("MH-Z19C yanıt yok")
    # Checksum doğrula
    toplam = sum(yanit[1:8]) & 0xFF
    kontrol = (~toplam + 1) & 0xFF
    if yanit[8] != kontrol:
        raise OSError("MH-Z19C checksum hatası")
    return (yanit[2] << 8) | yanit[3]

def _bh1750_oku() -> int:
    """BH1750 I2C ışık sensöründen lux değerini oku."""
    from machine import I2C, Pin
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100_000)
    # Sürekli yüksek çözünürlük modu
    i2c.writeto(0x23, b"\x10")
    utime.sleep_ms(180)
    veri = i2c.readfrom(0x23, 2)
    ham = (veri[0] << 8) | veri[1]
    return int(ham / 1.2)  # lux dönüşümü

def _kapasitif_nem_oku() -> int:
    """
    Kapasitif nem sensörünü ADC Pin 34 üzerinden oku.
    Ham 0–4095 → 0–1023 ölçeğine dönüştür.
    """
    from machine import ADC, Pin
    adc = ADC(Pin(34))
    adc.atten(ADC.ATTN_11DB)  # 0–3.3V aralığı
    # Gürültüyü azaltmak için 5 örnek ortalaması
    ornekler = [adc.read() for _ in range(5)]
    ortalama = sum(ornekler) // len(ornekler)
    # 0-4095 → 0-1023
    return min(1023, int(ortalama * 1023 / 4095))

# ---------------------------------------------------------------------------
# Fiziksel sınır kontrolü
# ---------------------------------------------------------------------------

_SINIRLAR = {
    "T":      (-40.0, 85.0),
    "H":      (0.0, 100.0),
    "co2":    (0, 10000),
    "isik":   (0, 200000),
    "toprak": (0, 1023),
    "ph":     (0.0, 14.0),
    "ec":     (0.0, 10.0),
}

# ---------------------------------------------------------------------------
# Ana sensör sınıfı
# ---------------------------------------------------------------------------

class SensorOkuyucu:
    """
    Tüm sensörleri tek noktadan okur.
    Gerçek donanım bulunamazsa otomatik olarak simülasyon moduna geçer.
    """

    def __init__(self):
        # Her sensör için erişilebilirlik durumunu ilk okumada belirle
        self._sht31_aktif   = False
        self._mhz19c_aktif  = False
        self._bh1750_aktif  = False
        self._kapasitif_aktif = False
        self._kontrol_yapildi = False

    def _donanim_kontrol(self) -> None:
        """Sensörlerin fiziksel olarak mevcut olduğunu bir kez test et."""
        print("[SENSOR] Donanım kontrolü başlıyor...")

        try:
            _sht31_oku()
            self._sht31_aktif = True
            print("[SENSOR] SHT31 bulundu")
        except Exception as e:
            print(f"[SENSOR] SHT31 yok / hata: {e}")

        try:
            _mhz19c_oku()
            self._mhz19c_aktif = True
            print("[SENSOR] MH-Z19C bulundu")
        except Exception as e:
            print(f"[SENSOR] MH-Z19C yok / hata: {e}")

        try:
            _bh1750_oku()
            self._bh1750_aktif = True
            print("[SENSOR] BH1750 bulundu")
        except Exception as e:
            print(f"[SENSOR] BH1750 yok / hata: {e}")

        try:
            _kapasitif_nem_oku()
            self._kapasitif_aktif = True
            print("[SENSOR] Kapasitif nem sensörü bulundu")
        except Exception as e:
            print(f"[SENSOR] Kapasitif nem yok / hata: {e}")

        self._kontrol_yapildi = True
        calisanlar = sum([
            self._sht31_aktif,
            self._mhz19c_aktif,
            self._bh1750_aktif,
            self._kapasitif_aktif,
        ])
        print(f"[SENSOR] {calisanlar}/4 donanım sensörü aktif")

    def oku(self) -> dict:
        """
        Tüm sensörleri oku.
        Döndürür: {"T": float, "H": float, "co2": int,
                   "isik": int, "toprak": int, "ph": float, "ec": float}
        """
        if not self._kontrol_yapildi:
            self._donanim_kontrol()

        sonuc = {}

        # --- Sıcaklık + Nem (SHT31) ---
        if self._sht31_aktif:
            try:
                T, H = _sht31_oku()
                sonuc["T"] = T
                sonuc["H"] = H
            except Exception as e:
                print(f"[SENSOR] SHT31 okuma hatası: {e}")
                sonuc["T"] = round(_gurultu(_SIM["T"], 0.5), 2)
                sonuc["H"] = round(_gurultu(_SIM["H"], 1.0), 2)
        else:
            # Simüle edilmiş değer — zaman içinde yavaş sürüklenme
            _SIM["T"] = round(_gurultu(_SIM["T"], 0.3), 2)
            _SIM["H"] = round(_gurultu(_SIM["H"], 0.5), 2)
            sonuc["T"] = _SIM["T"]
            sonuc["H"] = _SIM["H"]

        # --- CO₂ (MH-Z19C) ---
        if self._mhz19c_aktif:
            try:
                sonuc["co2"] = _mhz19c_oku()
            except Exception as e:
                print(f"[SENSOR] MH-Z19C okuma hatası: {e}")
                sonuc["co2"] = int(_gurultu(_SIM["co2"], 20))
        else:
            _SIM["co2"] = int(_gurultu(_SIM["co2"], 15))
            sonuc["co2"] = _SIM["co2"]

        # --- Işık (BH1750) ---
        if self._bh1750_aktif:
            try:
                sonuc["isik"] = _bh1750_oku()
            except Exception as e:
                print(f"[SENSOR] BH1750 okuma hatası: {e}")
                sonuc["isik"] = int(_gurultu(_SIM["isik"], 500))
        else:
            _SIM["isik"] = int(_gurultu(_SIM["isik"], 300))
            sonuc["isik"] = max(0, _SIM["isik"])

        # --- Toprak Nemi (Kapasitif) ---
        if self._kapasitif_aktif:
            try:
                sonuc["toprak"] = _kapasitif_nem_oku()
            except Exception as e:
                print(f"[SENSOR] Kapasitif nem okuma hatası: {e}")
                sonuc["toprak"] = int(_gurultu(_SIM["toprak"], 10))
        else:
            _SIM["toprak"] = int(_gurultu(_SIM["toprak"], 8))
            sonuc["toprak"] = max(0, min(1023, _SIM["toprak"]))

        # --- pH (henüz donanım yok — simüle) ---
        _SIM["ph"] = round(_gurultu(_SIM["ph"], 0.05), 2)
        _SIM["ph"] = max(0.0, min(14.0, _SIM["ph"]))
        sonuc["ph"] = _SIM["ph"]

        # --- EC (henüz donanım yok — simüle) ---
        _SIM["ec"] = round(_gurultu(_SIM["ec"], 0.02), 2)
        _SIM["ec"] = max(0.0, min(10.0, _SIM["ec"]))
        sonuc["ec"] = _SIM["ec"]

        return sonuc

    @staticmethod
    def gecerli_mi(veri: dict) -> bool:
        """
        Fiziksel sınırları kontrol et.
        Tüm alanlar mevcut ve sınırlar içinde ise True döndür.
        """
        for alan, (alt, ust) in _SINIRLAR.items():
            deger = veri.get(alan)
            if deger is None:
                return False
            if not (alt <= deger <= ust):
                print(f"[SENSOR] Sınır dışı — {alan}={deger} [{alt},{ust}]")
                return False
        return True
