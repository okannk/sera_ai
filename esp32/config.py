# MicroPython
# config.py — Cihaz yapılandırması ve NVS benzeri dosya tabanlı depolama
# ESP32-S3 Sera Otomasyon Düğümü

import ujson
import os

# ---------------------------------------------------------------------------
# Varsayılan değerler — provisioning sonrası /config.json'dan okunur
# ---------------------------------------------------------------------------
WIFI_SSID  = ""
WIFI_SIFRE = ""

PI_IP   = "192.168.1.100"
PI_PORT = 5000

MQTT_HOST = "192.168.1.100"
MQTT_PORT = 1883

CIHAZ_ID    = ""
TOKEN       = ""
SERA_ID     = ""
TESIS_KODU  = ""

# ---------------------------------------------------------------------------
# Dahili yardımcı — config dosyasını oku
# ---------------------------------------------------------------------------
_DOSYA = "/config.json"

def _yukle() -> dict:
    """Yapılandırma dosyasını oku; yoksa boş dict döndür."""
    try:
        with open(_DOSYA, "r") as f:
            return ujson.loads(f.read())
    except (OSError, ValueError):
        return {}

def _kaydet(veri: dict) -> None:
    """Dict'i JSON olarak yapılandırma dosyasına yaz."""
    with open(_DOSYA, "w") as f:
        f.write(ujson.dumps(veri))

# ---------------------------------------------------------------------------
# Modül yüklendiğinde mevcut değerleri bellek içine al
# ---------------------------------------------------------------------------
def _yenile():
    """Global değişkenleri dosyadaki değerlerle güncelle."""
    global WIFI_SSID, WIFI_SIFRE, PI_IP, PI_PORT
    global MQTT_HOST, MQTT_PORT, CIHAZ_ID, TOKEN, SERA_ID, TESIS_KODU

    d = _yukle()
    WIFI_SSID   = d.get("wifi_ssid",   WIFI_SSID)
    WIFI_SIFRE  = d.get("wifi_sifre",  WIFI_SIFRE)
    PI_IP       = d.get("pi_ip",       PI_IP)
    PI_PORT     = int(d.get("pi_port", PI_PORT))
    MQTT_HOST   = d.get("mqtt_host",   MQTT_HOST)
    MQTT_PORT   = int(d.get("mqtt_port", MQTT_PORT))
    CIHAZ_ID    = d.get("cihaz_id",    CIHAZ_ID)
    TOKEN       = d.get("token",       TOKEN)
    SERA_ID     = d.get("sera_id",     SERA_ID)
    TESIS_KODU  = d.get("tesis_kodu",  TESIS_KODU)

_yenile()  # modül import edildiğinde çalışır

# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------

def oku_token() -> str:
    """Kaydedilmiş JWT token'ı döndür; yoksa boş string."""
    d = _yukle()
    return d.get("token", "")

def token_kaydet(cihaz_id: str, token: str, sera_id: str, tesis_kodu: str) -> None:
    """
    Provisioning tamamlandığında çağrılır.
    Cihaz kimliği ve token'ı kalıcı olarak saklar.
    """
    global CIHAZ_ID, TOKEN, SERA_ID, TESIS_KODU
    d = _yukle()
    d["cihaz_id"]   = cihaz_id
    d["token"]      = token
    d["sera_id"]    = sera_id
    d["tesis_kodu"] = tesis_kodu
    _kaydet(d)
    # Global değişkenleri de güncelle
    CIHAZ_ID   = cihaz_id
    TOKEN      = token
    SERA_ID    = sera_id
    TESIS_KODU = tesis_kodu
    print(f"[KONFIG] Token kaydedildi — cihaz={cihaz_id}, sera={sera_id}")

def wifi_kaydet(ssid: str, sifre: str) -> None:
    """WiFi kimlik bilgilerini kaydet."""
    global WIFI_SSID, WIFI_SIFRE
    d = _yukle()
    d["wifi_ssid"]  = ssid
    d["wifi_sifre"] = sifre
    _kaydet(d)
    WIFI_SSID  = ssid
    WIFI_SIFRE = sifre
    print(f"[KONFIG] WiFi kaydedildi — SSID={ssid}")

def pi_kaydet(ip: str, port: int = 5000) -> None:
    """Raspberry Pi adresini güncelle."""
    global PI_IP, PI_PORT, MQTT_HOST
    d = _yukle()
    d["pi_ip"]    = ip
    d["pi_port"]  = port
    d["mqtt_host"] = ip   # MQTT broker Pi ile aynı makinede
    _kaydet(d)
    PI_IP     = ip
    PI_PORT   = port
    MQTT_HOST = ip
    print(f"[KONFIG] Pi adresi kaydedildi — {ip}:{port}")

def sifirla() -> None:
    """
    Fabrika sıfırlama — yapılandırma dosyasını sil.
    Sonraki yeniden başlatmada provisioning moduna girer.
    """
    try:
        os.remove(_DOSYA)
        print("[KONFIG] Fabrika sıfırlaması yapıldı — /config.json silindi")
    except OSError:
        print("[KONFIG] Sıfırlanacak yapılandırma dosyası bulunamadı")

def durum_yazdir() -> None:
    """Mevcut yapılandırmayı terminale yazdır (debug için)."""
    print("--- Yapılandırma Durumu ---")
    print(f"  WiFi SSID  : {WIFI_SSID or '(boş)'}")
    print(f"  Pi          : {PI_IP}:{PI_PORT}")
    print(f"  MQTT        : {MQTT_HOST}:{MQTT_PORT}")
    print(f"  Cihaz ID    : {CIHAZ_ID or '(boş)'}")
    print(f"  Token       : {'*' * min(len(TOKEN), 8) + '...' if TOKEN else '(boş)'}")
    print(f"  Tesis/Sera  : {TESIS_KODU}/{SERA_ID}")
    print("---------------------------")
