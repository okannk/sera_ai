"""
Merkez Kontrol Soyutlama Katmanı — MERKEZ KATMANI

Tüm sera sisteminin koordinasyon beyni.
Birden fazla SahaNode'u yönetir, kontrol kararlarını çalıştırır.

config.yaml'da tek satır:
    merkez_donanim: raspberry_pi  →  RaspberryPiMerkez devreye girer
    merkez_donanim: mock          →  MockMerkez devreye girer

Şu an kullanılan: RaspberryPiMerkez
İleride eklenecek: SiemensS71200Merkez (Modbus TCP üzerinden)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..drivers.base import SahaNodeBase
    from ..domain.models import Komut, SensorOkuma


class MerkezKontrolBase(ABC):
    """
    Merkez kontrol katmanı sözleşmesi.

    Sistem geri kalanı (state machine, ML, API, bildirim) bu
    interface'e bağımlıdır. Raspberry Pi mi, Siemens PLC mi —
    bilmez, sadece bu metodları çağırır.

    Sorumluluklar:
      - SahaNode'ları kaydet ve yönet
      - Sensör okuma döngüsünü çalıştır
      - Kontrol kararlarını uygula (komut gönder)
      - Sistem durumunu raporla
    """

    @abstractmethod
    def node_ekle(self, sera_id: str, node: "SahaNodeBase") -> None:
        """
        Sisteme yeni bir sera node'u ekle.
        Args:
            sera_id: Sera kimliği ("s1", "s2" ...)
            node:    SahaNodeBase implementasyonu
        """
        ...

    @abstractmethod
    def baslat(self) -> None:
        """
        Sistemi başlat:
          - Tüm node'lara bağlan
          - Kontrol döngüsünü başlat
          - Scheduler'ı başlat (günlük rapor, DB temizliği)
        """
        ...

    @abstractmethod
    def durdur(self) -> None:
        """
        Sistemi temiz durdur:
          - Kontrol döngüsünü durdur
          - Tüm node bağlantılarını kapat
          - Açık kaynakları serbest bırak
        """
        ...

    @abstractmethod
    def sensor_oku(self, sera_id: str) -> "SensorOkuma":
        """
        Belirtilen seradan anlık sensör okuma al.
        Raises:
            KeyError:  Bilinmeyen sera_id
            IOError:   Node yanıt vermedi
        """
        ...

    @abstractmethod
    def komut_gonder(self, sera_id: str, komut: "Komut") -> bool:
        """
        Belirtilen seraya komut gönder.
        Returns:
            True  → komut başarıyla iletildi ve onaylandı
            False → iletim başarısız (CB açık veya node yanıtsız)
        """
        ...

    @abstractmethod
    def tum_durum(self) -> dict:
        """
        Tüm sistem anlık durumunu döndür.
        API ve dashboard bu metodu kullanır.
        Returns: {sera_id: {durum, sensor, cb, ...}, ...}
        """
        ...

    # ──────────────────────────────────────────────────────────
    # MODBUS TCP INTERFACE — İLERİDE EKLENECEK
    # ──────────────────────────────────────────────────────────
    #
    # Siemens S7-1200 PLC entegrasyonu için Modbus TCP kullanılacak.
    # python-snap7 veya pymodbus kütüphanesiyle implement edilecek.
    # Şimdilik yorum olarak yer tutucu — implementasyon hazır
    # olduğunda SiemensS71200Merkez bu base'den türeyecek.
    #
    # @abstractmethod
    # def modbus_holding_oku(self, unit_id: int, adres: int, adet: int) -> list[int]:
    #     """
    #     Modbus TCP FC03 — Holding Register oku.
    #     Args:
    #         unit_id: PLC slave adresi (1-247)
    #         adres:   Register başlangıç adresi (0-65535)
    #         adet:    Okunacak register sayısı
    #     Returns:
    #         16-bit integer listesi
    #     Raises:
    #         IOError: Modbus iletişim hatası
    #     """
    #     ...
    #
    # @abstractmethod
    # def modbus_register_yaz(self, unit_id: int, adres: int, deger: int) -> bool:
    #     """
    #     Modbus TCP FC06 — Tek register yaz.
    #     Analog çıkış (frekans invertör hız referansı vb.) için.
    #     """
    #     ...
    #
    # @abstractmethod
    # def modbus_coil_yaz(self, unit_id: int, adres: int, deger: bool) -> bool:
    #     """
    #     Modbus TCP FC05 — Tek coil yaz.
    #     Dijital çıkış (röle, kontaktör, solenoid valf) için.
    #     """
    #     ...
    #
    # @abstractmethod
    # def modbus_input_oku(self, unit_id: int, adres: int, adet: int) -> list[bool]:
    #     """
    #     Modbus TCP FC02 — Discrete Input oku.
    #     Dijital giriş (limit switch, acil stop butonu) için.
    #     """
    #     ...
    #
    # ──────────────────────────────────────────────────────────
    # İLERİDE: Siemens S7-1200 Buraya Eklenecek
    # ──────────────────────────────────────────────────────────
    #
    # SiemensS71200Merkez(MerkezKontrolBase):
    #   - python-snap7 ile S7 communication protocol
    #   - DB block okuma/yazma (DataBlock üzerinden sensör/aktüatör)
    #   - Hardware interrupt (OB40) → acil durum tepkisi
    #   - PROFINET üzerinden distributed I/O (ET200SP)
    #
    # Şimdilik boş — donanım temin edildiğinde implement edilecek.
    # ──────────────────────────────────────────────────────────
