"""
RL Ajan — Tabular Q-Learning Optimizer

Durum uzayı (2430 durum = 5 × 3 × 2 × 3 × 3 × 3 × 3):
  T_sapma_band : [çok soğuk, soğuk, optimal, sıcak, çok sıcak]  → 0–4
  H_band       : [düşük nem, ok, yüksek nem]                     → 0–2
  toprak_band  : [kuru, yeterli]                                  → 0–1
  co2_band     : [düşük, optimal, yüksek]                        → 0–2
  isik_band    : [yetersiz, ok, fazla]                           → 0–2
  ph_band      : [asidik, ok, alkali]                            → 0–2
  ec_band      : [düşük, ok, yüksek]                            → 0–2

Durum indeksi = t×486 + h×162 + toprak×81 + co2×27 + isik×9 + ph×3 + ec

Eylem uzayı (16 eylem = 2^4):
  [sulama, isitici, sogutma, fan] → bit maske → 0–15

Q-tablo başlatma:
  KuralMotoru warm-start — sıfırdan öğrenmez, ilk adımdan güvenli çalışır.

Online öğrenme:
  hedef = ajan.hedef_hesapla(sensor, durum)    # ← karar + durum kaydet
  # aktüatörleri uygula, sonraki sensör oku ...
  odul  = ajan.odul_hesapla(sonraki_sensor)
  ajan.ogren(ajan.son_durum_idx, ajan.son_eylem_idx, odul, yeni_durum_idx)

Kalıcılık:
  ajan.kaydet("models/rl_Domates.pkl")
  ajan = RLAjan.yukle("models/rl_Domates.pkl", profil)

Güvenlik kuralları (değişmez):
  ACİL_DURDUR → HedefDeger()  (ML/RL'e danışılmaz)
  numpy yoksa → KuralMotoru fallback (sessiz degradasyon)
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

from ..domain.models import BitkilProfili, SensorOkuma
from ..domain.state_machine import Durum
from .base import HedefDeger, OptimizerBase
from .kural_motoru import KuralMotoru

try:
    import numpy as np
    _NUMPY_VAR = True
except ImportError:
    _NUMPY_VAR = False

# ── Sabitler ──────────────────────────────────────────────────

EYLEM_SAYISI       = 16    # 2^4 (sulama, isitici, sogutma, fan)
DURUM_SAYISI       = 2430  # 5 × 3 × 2 × 3 × 3 × 3 × 3 (T,H,toprak,co2,isik,ph,ec)

VARSAYILAN_ALFA    = 0.1   # Öğrenme hızı (learning rate)
VARSAYILAN_GAMA    = 0.9   # İndirim faktörü (discount)
VARSAYILAN_EPSILON = 0.05  # Keşif oranı — production'da düşük tutulur


# ── Yardımcı dönüşümler ───────────────────────────────────────

def _hedef_to_eylem(h: HedefDeger) -> int:
    """HedefDeger → eylem indeksi (bit maske)."""
    return (
        (int(h.sulama)  << 0) |
        (int(h.isitici) << 1) |
        (int(h.sogutma) << 2) |
        (int(h.fan)     << 3)
    )


def _eylem_to_hedef(eylem: int) -> HedefDeger:
    """Eylem indeksi (0–15) → HedefDeger."""
    return HedefDeger(
        sulama  = bool(eylem & (1 << 0)),
        isitici = bool(eylem & (1 << 1)),
        sogutma = bool(eylem & (1 << 2)),
        fan     = bool(eylem & (1 << 3)),
    )


# ── RLAjan ────────────────────────────────────────────────────

class RLAjan(OptimizerBase):
    """
    Tabular Q-learning RL ajan.

    Durum ayrıştırma → 2430 ayrık durum (7 sensör), KuralMotoru warm-start ile başlar.
    Online öğrenme → `ogren()` ile her adımda Q-tablo güncellenir.

    Ek metotlar:
      odul_hesapla(sensor) → float   : sensör okumasından ödül
      ogren(s, a, r, s')   → None    : Bellman güncellemesi
      kaydet(yol)          → None    : Q-tablo diske yaz
      yukle(yol, profil)   → RLAjan  : Q-tablo diskten oku
    """

    def __init__(
        self,
        profil:  BitkilProfili,
        alfa:    float = VARSAYILAN_ALFA,
        gama:    float = VARSAYILAN_GAMA,
        epsilon: float = VARSAYILAN_EPSILON,
    ) -> None:
        self.profil  = profil
        self.alfa    = alfa
        self.gama    = gama
        self.epsilon = epsilon
        self._fallback = KuralMotoru(profil)

        self._q_tablo:       object       = None   # numpy array (2430, 16)
        self._adim_sayisi:   int          = 0
        self._son_durum_idx: Optional[int] = None
        self._son_eylem_idx: Optional[int] = None

        if _NUMPY_VAR:
            self._q_tablo_baslat()
        else:
            print(
                "[RLAjan] numpy bulunamadı → KuralMotoru aktif. "
                "(pip install numpy)"
            )

    # ── Q-tablo başlatma ──────────────────────────────────────

    def _q_tablo_baslat(self) -> None:
        """
        Sıfır Q-tablosu oluştur; KuralMotoru çıktısından warm-start yap.

        Her durum için KuralMotoru'nun önerdiği eylem 1.0 başlangıç değeri alır.
        Bu sayede ajan ilk adımdan doğru kararlar verebilir.
        """
        self._q_tablo = np.zeros((DURUM_SAYISI, EYLEM_SAYISI), dtype=np.float64)

        for durum_idx in range(DURUM_SAYISI):
            sensor = self._durum_idx_to_ornek_sensor(durum_idx)
            kural_hedef = self._fallback.hedef_hesapla(sensor, Durum.NORMAL)
            kural_eylem = _hedef_to_eylem(kural_hedef)
            self._q_tablo[durum_idx, kural_eylem] = 1.0

    # ── Durum ayrıştırma ──────────────────────────────────────

    def _sensor_to_durum_idx(self, sensor: SensorOkuma) -> int:
        """
        SensorOkuma → durum indeksi (0–2429).

        Kodlama: t×486 + h×162 + toprak×81 + co2×27 + isik×9 + ph×3 + ec
        """
        p = self.profil

        # Sıcaklık bandı (opt_T'ye göre sapma)
        t_sapma = sensor.T - p.opt_T
        if   t_sapma < -4:  t_band = 0   # çok soğuk
        elif t_sapma < -2:  t_band = 1   # soğuk
        elif t_sapma <= 2:  t_band = 2   # optimal
        elif t_sapma <= 4:  t_band = 3   # sıcak
        else:               t_band = 4   # çok sıcak

        # Nem bandı (profil bandı merkezine göre)
        h_merkez  = (p.min_H + p.max_H) / 2.0
        h_yaricap = (p.max_H - p.min_H) / 2.0
        h_sapma   = sensor.H - h_merkez
        if   h_sapma < -h_yaricap * 0.5:  h_band = 0   # düşük
        elif h_sapma <=  h_yaricap * 0.5:  h_band = 1   # ok
        else:                               h_band = 2   # yüksek

        # Toprak nemi bandı
        toprak_band = 0 if sensor.toprak_nem < 350 else 1

        # CO₂ bandı (opt_CO2'ye göre ±%25)
        co2_low  = p.opt_CO2 * 0.75
        co2_high = p.opt_CO2 * 1.25
        if   sensor.co2 < co2_low:   co2_band = 0   # düşük
        elif sensor.co2 <= co2_high: co2_band = 1   # optimal
        else:                         co2_band = 2   # yüksek

        # Işık bandı (profil min/max sınırları)
        if   sensor.isik < p.min_isik:   isik_band = 0   # yetersiz
        elif sensor.isik <= p.max_isik:  isik_band = 1   # ok
        else:                             isik_band = 2   # fazla

        # pH bandı (profil opt'e göre çeyrek aralıklar)
        ph_low  = (p.min_pH + p.opt_pH) / 2.0
        ph_high = (p.opt_pH + p.max_pH) / 2.0
        if   sensor.ph < ph_low:   ph_band = 0   # asidik
        elif sensor.ph <= ph_high: ph_band = 1   # ok
        else:                       ph_band = 2   # alkali

        # EC bandı (profil opt'e göre çeyrek aralıklar)
        ec_low  = (p.min_EC + p.opt_EC) / 2.0
        ec_high = (p.opt_EC + p.max_EC) / 2.0
        if   sensor.ec < ec_low:   ec_band = 0   # düşük
        elif sensor.ec <= ec_high: ec_band = 1   # ok
        else:                       ec_band = 2   # yüksek

        return (t_band * 486 + h_band * 162 + toprak_band * 81
                + co2_band * 27 + isik_band * 9 + ph_band * 3 + ec_band)

    def _durum_idx_to_ornek_sensor(self, durum_idx: int) -> SensorOkuma:
        """
        Durum indeksinden temsili SensorOkuma oluştur (warm-start için).

        _sensor_to_durum_idx() ile tutarlı ters dönüşüm.
        """
        p = self.profil

        t_band      = durum_idx // 486
        kalan       = durum_idx % 486
        h_band      = kalan // 162
        kalan       = kalan % 162
        toprak_band = kalan // 81
        kalan       = kalan % 81
        co2_band    = kalan // 27
        kalan       = kalan % 27
        isik_band   = kalan // 9
        kalan       = kalan % 9
        ph_band     = kalan // 3
        ec_band     = kalan % 3

        t_sapma_map = {0: -6.0, 1: -3.0, 2: 0.0, 3: 3.0, 4: 6.0}
        T = p.opt_T + t_sapma_map[t_band]

        h_merkez    = (p.min_H + p.max_H) / 2.0
        h_yaricap   = (p.max_H - p.min_H) / 2.0
        h_ofset_map = {0: -h_yaricap * 0.75, 1: 0.0, 2: h_yaricap * 0.75}
        H = h_merkez + h_ofset_map[h_band]

        toprak_nem = 200 if toprak_band == 0 else 600

        co2_map = {0: int(p.opt_CO2 * 0.5), 1: p.opt_CO2, 2: int(p.opt_CO2 * 1.5)}
        co2 = co2_map[co2_band]

        isik_map = {
            0: max(0, p.min_isik - 100),
            1: p.opt_isik,
            2: min(90000, p.max_isik + 10000),
        }
        isik = isik_map[isik_band]

        ph_low  = (p.min_pH + p.opt_pH) / 2.0
        ph_high = (p.opt_pH + p.max_pH) / 2.0
        ph_map  = {0: max(3.0, ph_low - 0.5), 1: p.opt_pH, 2: min(9.0, ph_high + 0.5)}
        ph = ph_map[ph_band]

        ec_low  = (p.min_EC + p.opt_EC) / 2.0
        ec_high = (p.opt_EC + p.max_EC) / 2.0
        ec_map  = {0: max(0.0, ec_low - 0.5), 1: p.opt_EC, 2: min(10.0, ec_high + 0.5)}
        ec = ec_map[ec_band]

        return SensorOkuma(
            sera_id="rl_warm_start",
            T=T, H=H, co2=co2,
            isik=isik, toprak_nem=toprak_nem,
            ph=ph, ec=ec,
        )

    # ── Ödül hesaplama ────────────────────────────────────────

    def odul_hesapla(self, sensor: SensorOkuma) -> float:
        """
        Sensör okumasından ödül (reward) hesapla.

        Ödül yorumu:
          0.0  → mükemmel (tüm 7 değer optimal)
          -7.0 → çok kötü (tüm bileşenler maksimum ceza)

        Bileşenler (her biri 0 … -1 aralığında):
          t_skor     : -|T - opt_T| / T_aralik
          h_skor     : -|H - h_opt| / h_aralik
          toprak_skor: 0.0 (yeterli) veya -1.0 (kuru)
          co2_skor   : -|co2 - opt_CO2| / (opt_CO2 * 0.5)
          isik_skor  : -|isik - opt_isik| / (opt_isik * 0.5)
          ph_skor    : -|ph - opt_pH| / ph_aralik
          ec_skor    : -|ec - opt_EC| / ec_aralik
        """
        p = self.profil

        t_aralik   = max(p.max_T - p.opt_T, 1.0)
        t_skor     = max(-abs(sensor.T - p.opt_T) / t_aralik, -1.0)

        h_opt      = (p.min_H + p.max_H) / 2.0
        h_aralik   = max(p.max_H - h_opt, 1.0)
        h_skor     = max(-abs(sensor.H - h_opt) / h_aralik, -1.0)

        toprak_skor = 0.0 if sensor.toprak_nem >= 350 else -1.0

        co2_aralik  = max(p.opt_CO2 * 0.5, 1.0)
        co2_skor    = max(-abs(sensor.co2 - p.opt_CO2) / co2_aralik, -1.0)

        isik_aralik = max(p.opt_isik * 0.5, 1.0)
        isik_skor   = max(-abs(sensor.isik - p.opt_isik) / isik_aralik, -1.0)

        ph_aralik   = max(p.max_pH - p.opt_pH, 0.1)
        ph_skor     = max(-abs(sensor.ph - p.opt_pH) / ph_aralik, -1.0)

        ec_aralik   = max(p.max_EC - p.opt_EC, 0.1)
        ec_skor     = max(-abs(sensor.ec - p.opt_EC) / ec_aralik, -1.0)

        return t_skor + h_skor + toprak_skor + co2_skor + isik_skor + ph_skor + ec_skor

    # ── Online öğrenme (Bellman güncellemesi) ─────────────────

    def ogren(
        self,
        durum_idx:         int,
        eylem_idx:         int,
        odul:              float,
        sonraki_durum_idx: int,
    ) -> None:
        """
        Q(s, a) ← Q(s, a) + α × [r + γ × max_a' Q(s', a') − Q(s, a)]

        Args:
            durum_idx:         Önceki durum indeksi (0–2429)
            eylem_idx:         Uygulanan eylem indeksi (0–15)
            odul:              Alınan ödül (odul_hesapla() çıktısı)
            sonraki_durum_idx: Sonraki durum indeksi (0–2429)
        """
        if self._q_tablo is None:
            return

        hedef_q  = odul + self.gama * float(np.max(self._q_tablo[sonraki_durum_idx]))
        mevcut_q = float(self._q_tablo[durum_idx, eylem_idx])
        self._q_tablo[durum_idx, eylem_idx] = (
            mevcut_q + self.alfa * (hedef_q - mevcut_q)
        )
        self._adim_sayisi += 1

    # ── Kalıcılık ─────────────────────────────────────────────

    def kaydet(self, yol: str) -> None:
        """Q-tablosunu ve meta verileri diske kaydet."""
        if self._q_tablo is None:
            return
        Path(yol).parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "wb") as f:
            pickle.dump({
                "q_tablo":     self._q_tablo,
                "adim_sayisi": self._adim_sayisi,
                "profil_isim": self.profil.isim,
            }, f)

    @classmethod
    def yukle(cls, yol: str, profil: BitkilProfili, **kwargs) -> "RLAjan":
        """Kaydedilmiş Q-tablosunu yükle, yeni RLAjan döndür."""
        ajan = cls(profil, **kwargs)
        if not _NUMPY_VAR:
            return ajan
        with open(yol, "rb") as f:
            veri = pickle.load(f)
        ajan._q_tablo    = veri["q_tablo"]
        ajan._adim_sayisi = veri.get("adim_sayisi", 0)
        return ajan

    # ── Öğrenme geri bildirimi ────────────────────────────────

    def geri_bildirim(
        self,
        onceki_sensor: SensorOkuma,
        sonraki_sensor: SensorOkuma,
    ) -> None:
        """
        KontrolMotoru'ndan gelen öğrenme geri bildirimi.

        Önceki adımda verilen karar (son_durum_idx, son_eylem_idx) için
        yeni sensör okumasından ödül hesapla ve Q-tablosunu güncelle.

        Q-tablo yoksa veya önceki karar kaydedilmemişse sessizce geç.
        """
        if self._q_tablo is None:
            return
        if self._son_durum_idx is None or self._son_eylem_idx is None:
            return
        odul              = self.odul_hesapla(sonraki_sensor)
        sonraki_durum_idx = self._sensor_to_durum_idx(sonraki_sensor)
        self.ogren(self._son_durum_idx, self._son_eylem_idx, odul, sonraki_durum_idx)

    def baslangic_yukle(self, model_dizin: str, sera_id: str) -> None:
        """
        Sistem başlarken kaydedilmiş Q-tabloyu yükle.
        Dosya yoksa warm-start Q-tablosu kullanılmaya devam eder.
        """
        if not _NUMPY_VAR:
            return
        yol = Path(model_dizin) / f"rl_{sera_id}.pkl"
        if not yol.exists():
            return
        try:
            with open(yol, "rb") as f:
                veri = pickle.load(f)
            self._q_tablo    = veri["q_tablo"]
            self._adim_sayisi = veri.get("adim_sayisi", 0)
            print(f"[RLAjan:{sera_id}] Q-tablo yüklendi: {yol} ({self._adim_sayisi} adım)")
        except Exception as e:
            print(f"[RLAjan:{sera_id}] Q-tablo yüklenemedi: {e}")

    def kapatma_kaydet(self, model_dizin: str, sera_id: str) -> None:
        """Kapanırken Q-tabloyu diske kaydet."""
        if self._q_tablo is None:
            return
        yol = Path(model_dizin) / f"rl_{sera_id}.pkl"
        try:
            self.kaydet(str(yol))
            print(f"[RLAjan:{sera_id}] Q-tablo kaydedildi: {yol} ({self._adim_sayisi} adım)")
        except Exception as e:
            print(f"[RLAjan:{sera_id}] Q-tablo kaydedilemedi: {e}")

    # ── OptimizerBase arayüzü ─────────────────────────────────

    def hedef_hesapla(self, sensor: SensorOkuma, durum: Durum) -> HedefDeger:
        """
        Ana karar metodu.

        Öncelik sırası:
          1. ACİL_DURDUR → HedefDeger() (hepsi kapalı, ML/RL'e danışılmaz)
          2. numpy yok   → KuralMotoru fallback
          3. epsilon > random → keşif (KuralMotoru önerisi)
          4. Aksi halde  → Q-tablosundan argmax eylem
        """
        if durum == Durum.ACIL_DURDUR:
            return HedefDeger()

        if self._q_tablo is None:
            return self._fallback.hedef_hesapla(sensor, durum)

        durum_idx = self._sensor_to_durum_idx(sensor)
        self._son_durum_idx = durum_idx

        # Epsilon-greedy: keşif → KuralMotoru, sömürü → Q-tablo
        if self.epsilon > 0 and float(np.random.random()) < self.epsilon:
            kural_hedef = self._fallback.hedef_hesapla(sensor, durum)
            eylem_idx   = _hedef_to_eylem(kural_hedef)
        else:
            eylem_idx = int(np.argmax(self._q_tablo[durum_idx]))

        self._son_eylem_idx = eylem_idx
        return _eylem_to_hedef(eylem_idx)

    # ── Salt-okunur özellikler ────────────────────────────────

    @property
    def son_durum_idx(self) -> Optional[int]:
        """Son hedef_hesapla() çağrısındaki durum indeksi."""
        return self._son_durum_idx

    @property
    def son_eylem_idx(self) -> Optional[int]:
        """Son hedef_hesapla() çağrısındaki eylem indeksi."""
        return self._son_eylem_idx

    @property
    def adim_sayisi(self) -> int:
        """Toplam Q-güncelleme (ogren() çağrısı) sayısı."""
        return self._adim_sayisi
