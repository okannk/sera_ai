# MicroPython
# provisioning.py — Sıfır Dokunuşlu Temin (Zero-Touch Provisioning)
# ESP32-S3 ilk açılışta AP modunda çalışır, kullanıcı web formu ile yapılandırır.

import network
import socket
import time
import ujson
import machine

import config

# ---------------------------------------------------------------------------
# HTML şablonları
# ---------------------------------------------------------------------------

_HTML_KURULUM = """\
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sera Kurulum</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:Arial,sans-serif;background:#1a2e1a;color:#e8f5e9;min-height:100vh;
       display:flex;align-items:center;justify-content:center;padding:16px}}
  .kart{{background:#2d4a2d;border-radius:12px;padding:24px;max-width:420px;width:100%;
         box-shadow:0 4px 24px #0006}}
  h1{{color:#81c784;font-size:1.4rem;margin-bottom:4px}}
  .alt{{color:#a5d6a7;font-size:.85rem;margin-bottom:20px}}
  label{{display:block;font-size:.85rem;color:#a5d6a7;margin-bottom:4px;margin-top:12px}}
  input,select{{width:100%;padding:10px;border:1px solid #4a7c4a;border-radius:6px;
               background:#1a2e1a;color:#e8f5e9;font-size:1rem}}
  input:focus,select:focus{{outline:none;border-color:#81c784}}
  .btn{{margin-top:20px;width:100%;padding:12px;background:#388e3c;color:#fff;
        border:none;border-radius:6px;font-size:1rem;cursor:pointer;font-weight:bold}}
  .btn:active{{background:#2e7d32}}
  .bilgi{{margin-top:14px;font-size:.78rem;color:#66bb6a;text-align:center}}
  option{{background:#1a2e1a}}
</style>
</head>
<body>
<div class="kart">
  <h1>🌿 Sera Kurulum</h1>
  <p class="alt">Cihazı ağa bağlamak için bilgileri girin</p>
  <form method="POST" action="/kaydet">
    <label>WiFi Ağ Adı (SSID)</label>
    <input type="text" name="ssid" placeholder="Ev WiFi" required>
    <label>WiFi Şifresi</label>
    <input type="password" name="sifre" placeholder="••••••••">
    <label>Raspberry Pi IP Adresi</label>
    <input type="text" name="pi_ip" value="{pi_ip}" placeholder="192.168.1.100" required>
    <label>Sera Seçimi</label>
    <select name="sera_id">{sera_secenekleri}</select>
    <button type="submit" class="btn">Kaydet ve Bağlan</button>
  </form>
  <p class="bilgi">Cihaz bağlandıktan sonra bu sayfa kapanacaktır.</p>
</div>
</body>
</html>
"""

_HTML_BEKLEME = """\
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>Onay Bekleniyor</title>
<style>
  body{{font-family:Arial,sans-serif;background:#1a2e1a;color:#e8f5e9;
       display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px}}
  .kart{{background:#2d4a2d;border-radius:12px;padding:32px;max-width:380px;width:100%;text-align:center}}
  .spinner{{font-size:2.5rem;animation:spin 2s linear infinite;display:inline-block;margin-bottom:16px}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  h2{{color:#81c784;margin-bottom:8px}}
  p{{color:#a5d6a7;font-size:.9rem;line-height:1.6}}
  .talep{{font-size:.75rem;color:#66bb6a;margin-top:12px;word-break:break-all}}
</style>
</head>
<body>
<div class="kart">
  <div class="spinner">⏳</div>
  <h2>Onay Bekleniyor</h2>
  <p>Raspberry Pi'den onay bekleniyor.<br>Sayfa 10 saniyede bir otomatik yenilenir.</p>
  <p class="talep">Talep ID: {talep_id}</p>
</div>
</body>
</html>
"""

_HTML_HATA = """\
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>Hata</title>
<style>body{{font-family:Arial;background:#1a2e1a;color:#e8f5e9;
  display:flex;align-items:center;justify-content:center;min-height:100vh}}
  .k{{background:#4a1a1a;border-radius:10px;padding:24px;max-width:360px;text-align:center}}
  h2{{color:#ef9a9a}} p{{color:#ffcdd2;font-size:.9rem;margin-top:8px}}</style>
</head>
<body><div class="k"><h2>⚠ Hata</h2><p>{mesaj}</p>
<p style="margin-top:16px"><a href="/" style="color:#81c784">← Geri Dön</a></p>
</div></body></html>
"""

# ---------------------------------------------------------------------------
# Yardımcı — ham HTTP POST gövdesini ayrıştır
# ---------------------------------------------------------------------------

def _form_ayristir(govde: str) -> dict:
    """application/x-www-form-urlencoded gövdesini dict'e çevir."""
    sonuc = {}
    for cift in govde.split("&"):
        if "=" in cift:
            k, v = cift.split("=", 1)
            # URL decode — en yaygın karakterler
            v = v.replace("+", " ")
            for kod, kar in (("%20", " "), ("%21", "!"), ("%40", "@"),
                             ("%23", "#"), ("%24", "$"), ("%2F", "/"),
                             ("%3A", ":"), ("%3F", "?"), ("%3D", "="),
                             ("%26", "&"), ("%25", "%")):
                v = v.replace(kod, kar)
            sonuc[k] = v
    return sonuc

# ---------------------------------------------------------------------------
# Pi ile HTTP iletişim (raw socket — urequests olmadan)
# ---------------------------------------------------------------------------

def _http_get(ip: str, port: int, yol: str) -> tuple:
    """Basit GET isteği; (durum_kodu, govde_str) döndür."""
    try:
        s = socket.socket()
        s.settimeout(10)
        s.connect((ip, port))
        istek = f"GET {yol} HTTP/1.0\r\nHost: {ip}\r\nConnection: close\r\n\r\n"
        s.send(istek.encode())
        yanit = b""
        while True:
            parca = s.recv(512)
            if not parca:
                break
            yanit += parca
        s.close()
        satirlar = yanit.decode("utf-8", "ignore")
        # HTTP başlığını ayır
        if "\r\n\r\n" in satirlar:
            bas, govde = satirlar.split("\r\n\r\n", 1)
            durum = int(bas.split(" ")[1])
            return durum, govde
        return 0, ""
    except Exception as e:
        print(f"[PROVISIONING] GET hatası: {e}")
        return 0, ""

def _http_post(ip: str, port: int, yol: str, veri: dict) -> tuple:
    """Basit JSON POST isteği; (durum_kodu, govde_str) döndür."""
    try:
        govde = ujson.dumps(veri)
        s = socket.socket()
        s.settimeout(10)
        s.connect((ip, port))
        istek = (
            f"POST {yol} HTTP/1.0\r\n"
            f"Host: {ip}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(govde)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{govde}"
        )
        s.send(istek.encode())
        yanit = b""
        while True:
            parca = s.recv(512)
            if not parca:
                break
            yanit += parca
        s.close()
        satirlar = yanit.decode("utf-8", "ignore")
        if "\r\n\r\n" in satirlar:
            bas, govde_y = satirlar.split("\r\n\r\n", 1)
            durum = int(bas.split(" ")[1])
            return durum, govde_y
        return 0, ""
    except Exception as e:
        print(f"[PROVISIONING] POST hatası: {e}")
        return 0, ""

# ---------------------------------------------------------------------------
# Pi'den sera listesini çek
# ---------------------------------------------------------------------------

def _sera_listesi_al(pi_ip: str, pi_port: int) -> list:
    """Pi API'sinden sera listesini al; hata durumunda varsayılan liste döndür."""
    durum, govde = _http_get(pi_ip, pi_port, "/api/v1/seralar")
    if durum == 200:
        try:
            veriler = ujson.loads(govde)
            # API {"data": [{"id": "s1", "ad": "Sera 1"}, ...]} formatını bekle
            seralar = veriler.get("data", veriler if isinstance(veriler, list) else [])
            return seralar
        except Exception:
            pass
    # Fallback — Pi'ye ulaşılamadı
    return [
        {"id": "s1", "ad": "Sera 1"},
        {"id": "s2", "ad": "Sera 2"},
        {"id": "s3", "ad": "Sera 3"},
    ]

def _sera_option_html(seralar: list) -> str:
    """Sera listesinden <option> HTML parçaları üret."""
    parcalar = []
    for s in seralar:
        sid = s.get("id", "s1")
        sad = s.get("ad", sid)
        parcalar.append(f'<option value="{sid}">{sad}</option>')
    return "".join(parcalar)

# ---------------------------------------------------------------------------
# WiFi hedef ağa bağlan
# ---------------------------------------------------------------------------

def _wifi_baglan(ssid: str, sifre: str, zaman_asimi: int = 30) -> bool:
    """Belirtilen WiFi ağına bağlan; başarı durumunu döndür."""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(ssid, sifre)
    print(f"[PROVISIONING] WiFi bağlanıyor: {ssid}")
    bitis = time.time() + zaman_asimi
    while time.time() < bitis:
        if sta.isconnected():
            print(f"[PROVISIONING] WiFi bağlandı — IP: {sta.ifconfig()[0]}")
            return True
        time.sleep(1)
    print("[PROVISIONING] WiFi bağlantısı zaman aşımına uğradı")
    return False

# ---------------------------------------------------------------------------
# Kayıt talebi gönder ve token bekle
# ---------------------------------------------------------------------------

def _kayit_yap(pi_ip: str, pi_port: int, cihaz_id: str, sera_id: str) -> tuple:
    """
    Pi'ye kayıt talebi gönder.
    (talep_id, tesis_kodu) döndür; hata durumunda ("", "").
    """
    durum, govde = _http_post(
        pi_ip, pi_port,
        "/api/v1/provisioning/kayit-talebi",
        {"cihaz_id": cihaz_id, "sera_id": sera_id}
    )
    if durum in (200, 201):
        try:
            veri = ujson.loads(govde)
            talep_id   = veri.get("talep_id", "")
            tesis_kodu = veri.get("tesis_kodu", "VARSAYILAN")
            print(f"[PROVISIONING] Kayıt talebi oluşturuldu — talep={talep_id}")
            return talep_id, tesis_kodu
        except Exception as e:
            print(f"[PROVISIONING] Kayıt yanıtı ayrıştırılamadı: {e}")
    return "", ""

def _token_bekle(pi_ip: str, pi_port: int, talep_id: str,
                 max_deneme: int = 36, aralik: int = 10) -> str:
    """
    Pi'yi periyodik olarak sorgula, token gelince döndür.
    max_deneme × aralik = 360 saniye maksimum bekleme.
    """
    yol = f"/api/v1/provisioning/durum/{talep_id}"
    for deneme in range(max_deneme):
        print(f"[PROVISIONING] Token bekleniyor ({deneme + 1}/{max_deneme})...")
        durum, govde = _http_get(pi_ip, pi_port, yol)
        if durum == 200:
            try:
                veri = ujson.loads(govde)
                token = veri.get("token", "")
                if token:
                    print("[PROVISIONING] Token alındı!")
                    return token
                # Durum henüz "bekliyor" ise devam et
                print(f"[PROVISIONING] Durum: {veri.get('durum', '?')}")
            except Exception as e:
                print(f"[PROVISIONING] Durum yanıtı ayrıştırılamadı: {e}")
        time.sleep(aralik)
    print("[PROVISIONING] Token bekleme zaman aşımı")
    return ""

# ---------------------------------------------------------------------------
# Gömülü HTTP Sunucusu
# ---------------------------------------------------------------------------

class _SunucuDurumu:
    """AP modunda çalışan küçük HTTP sunucusunun durumu."""
    def __init__(self, pi_ip: str, pi_port: int):
        self.pi_ip   = pi_ip
        self.pi_port = pi_port
        self.calisma  = True
        # MAC adresinin son 4 karakteri
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        mac = wlan.config("mac")
        self.mac_son4 = "".join(f"{b:02X}" for b in mac)[-4:]
        self.cihaz_id = f"ESP32S3-{self.mac_son4}"
        # Sera listesini önceden al (AP modundayken Pi'ye ulaşılamayabilir)
        self.seralar  = []

def _istegi_isle(baglanti, adres, durum: _SunucuDurumu) -> bool:
    """
    Gelen HTTP isteğini işle.
    Provisioning tamamlandıysa True döndür.
    """
    try:
        istek = baglanti.recv(2048).decode("utf-8", "ignore")
        if not istek:
            return False

        satirlar = istek.split("\r\n")
        ilk_satir = satirlar[0] if satirlar else ""
        parcalar  = ilk_satir.split(" ")
        if len(parcalar) < 2:
            return False

        metod = parcalar[0]
        yol   = parcalar[1]

        # ----------------------------------------------------------------
        # GET / — kurulum sayfası
        # ----------------------------------------------------------------
        if metod == "GET" and yol in ("/", "/index.html"):
            sera_html = _sera_option_html(durum.seralar)
            html = _HTML_KURULUM.format(
                pi_ip=durum.pi_ip,
                sera_secenekleri=sera_html
            )
            yanit = (
                "HTTP/1.0 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                f"Content-Length: {len(html)}\r\n\r\n"
                f"{html}"
            )
            baglanti.send(yanit.encode())

        # ----------------------------------------------------------------
        # POST /kaydet — form verisini işle
        # ----------------------------------------------------------------
        elif metod == "POST" and yol == "/kaydet":
            # Gövdeyi ayır
            if "\r\n\r\n" in istek:
                _, govde = istek.split("\r\n\r\n", 1)
            else:
                govde = ""
            form = _form_ayristir(govde)

            ssid   = form.get("ssid", "").strip()
            sifre  = form.get("sifre", "")
            pi_ip  = form.get("pi_ip", durum.pi_ip).strip()
            sera_id = form.get("sera_id", "s1").strip()

            if not ssid:
                html = _HTML_HATA.format(mesaj="WiFi SSID boş olamaz.")
                yanit = (
                    "HTTP/1.0 400 Bad Request\r\n"
                    "Content-Type: text/html; charset=UTF-8\r\n"
                    f"Content-Length: {len(html)}\r\n\r\n{html}"
                )
                baglanti.send(yanit.encode())
                return False

            # Bekleme sayfasını hemen göster
            talep_id_on = "bekliyor..."
            html_bkl = _HTML_BEKLEME.format(talep_id=talep_id_on)
            yanit_bkl = (
                "HTTP/1.0 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                f"Content-Length: {len(html_bkl)}\r\n\r\n{html_bkl}"
            )
            baglanti.send(yanit_bkl.encode())
            baglanti.close()

            # --- WiFi ve Pi bilgilerini kaydet ---
            config.wifi_kaydet(ssid, sifre)
            config.pi_kaydet(pi_ip)

            # --- Hedef WiFi'ye bağlan ---
            print(f"[PROVISIONING] AP kapatılıyor, {ssid} ağına bağlanılıyor...")
            ap = network.WLAN(network.AP_IF)
            ap.active(False)

            if not _wifi_baglan(ssid, sifre):
                # WiFi bağlantısı başarısız — sıfırla ve yeniden başlat
                print("[PROVISIONING] WiFi başarısız, fabrika sıfırlaması yapılıyor")
                config.sifirla()
                time.sleep(2)
                machine.reset()
                return True

            # --- Pi'ye kayıt talebi gönder ---
            talep_id, tesis_kodu = _kayit_yap(pi_ip, int(durum.pi_port), durum.cihaz_id, sera_id)
            if not talep_id:
                print("[PROVISIONING] Kayıt talebi başarısız, sıfırlanıyor")
                config.sifirla()
                time.sleep(2)
                machine.reset()
                return True

            # --- Token bekle ---
            token = _token_bekle(pi_ip, int(durum.pi_port), talep_id)
            if token:
                config.token_kaydet(durum.cihaz_id, token, sera_id, tesis_kodu)
                print("[PROVISIONING] Provisioning tamamlandı, yeniden başlatılıyor...")
                time.sleep(2)
                machine.reset()
            else:
                print("[PROVISIONING] Token alınamadı, sıfırlanıyor")
                config.sifirla()
                time.sleep(2)
                machine.reset()

            return True

        # ----------------------------------------------------------------
        # Bilinmeyen istek — 404
        # ----------------------------------------------------------------
        else:
            yanit = "HTTP/1.0 404 Not Found\r\n\r\n404\r\n"
            baglanti.send(yanit.encode())

    except Exception as e:
        print(f"[PROVISIONING] İstek işleme hatası: {e}")
    finally:
        try:
            baglanti.close()
        except Exception:
            pass

    return False

# ---------------------------------------------------------------------------
# Ana provisioning akışı
# ---------------------------------------------------------------------------

def baslat(pi_ip: str = "192.168.1.100", pi_port: int = 5000) -> None:
    """
    Provisioning modunu başlat:
    1. AP aç
    2. HTTP sunucu dinle
    3. Form gelince WiFi bağlan + Pi kayıt + token al
    4. token_kaydet() + machine.reset()
    """
    durum = _SunucuDurumu(pi_ip, pi_port)

    # --- Access Point aç ---
    ap_ssid = f"SERA-SETUP-{durum.mac_son4}"
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=ap_ssid, authmode=network.AUTH_OPEN)
    print(f"[PROVISIONING] AP başlatıldı: {ap_ssid}")
    print(f"[PROVISIONING] Kurulum sayfası: http://192.168.4.1")

    # Sera listesini AP üzerinden değil, sonraki WiFi bağlantısında alacağız;
    # şimdilik varsayılan listeyi kullan
    durum.seralar = _sera_listesi_al(pi_ip, pi_port)

    # --- HTTP sunucu ---
    sunucu = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sunucu.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sunucu.bind(("0.0.0.0", 80))
    sunucu.listen(3)
    sunucu.settimeout(1)  # 1 saniye timeout → watchdog için döngü sürdürülebilir
    print("[PROVISIONING] HTTP sunucu dinleniyor :80")

    try:
        while durum.calisma:
            try:
                baglanti, adres = sunucu.accept()
                print(f"[PROVISIONING] Bağlantı: {adres[0]}")
                bitti = _istegi_isle(baglanti, adres, durum)
                if bitti:
                    # machine.reset() zaten çağrıldı, buraya genellikle gelinmez
                    break
            except OSError:
                pass  # Zaman aşımı — normal, döngüye devam
    finally:
        sunucu.close()
        print("[PROVISIONING] HTTP sunucu kapatıldı")
