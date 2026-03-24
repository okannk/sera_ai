export type Durum = 'NORMAL' | 'UYARI' | 'ALARM' | 'ACIL_DURDUR' | 'BAKIM' | 'BILINMIYOR'

export interface SensorOkuma {
  T: number
  H: number
  co2: number
  isik: number
  toprak: number
  ph: number
  ec: number
  zaman: string
}

export interface SeraOzet {
  id: string
  isim: string
  bitki: string
  alan: number
  durum: Durum
  sensor: SensorOkuma | null
  esp32_ip?: string
  sensor_tipi?: string
  mqtt_topic?: string
  aciklama?: string
}

export interface BitkiProfil {
  minT?: number; maxT?: number; optT?: number
  minH?: number; maxH?: number
  min_T?: number; max_T?: number; opt_T?: number
  min_H?: number; max_H?: number; opt_CO2?: number
}

export interface SeraDetay extends SeraOzet {
  profil: BitkiProfil
  cb?: { durum: string; hata_sayisi: number }
  son_guncelleme?: string
}

export interface SaglikDurumu {
  durum: string
  uptime_sn: number
  uptime_fmt: string
  seralar: Record<string, Durum>
  alarm_sayisi: number
}

export interface Alarm {
  sera_id: string
  isim: string
  durum: Durum
  sensor: SensorOkuma | null
}

export interface ApiYanit<T> {
  success: boolean
  data: T
  error?: string | null
  hata?: string | null
  kod?: string | null
  meta: { ts: string }
}

export type KomutAdi =
  | 'SULAMA_AC' | 'SULAMA_KAPAT'
  | 'ISITICI_AC' | 'ISITICI_KAPAT'
  | 'SOGUTMA_AC' | 'SOGUTMA_KAPAT'
  | 'FAN_AC' | 'FAN_KAPAT'
  | 'ISIK_AC' | 'ISIK_KAPAT'
  | 'ACIL_DURDUR'

export interface SensorGecmis {
  zaman: string
  T: number
  H: number
  co2: number
  toprak?: number
  isik?: number
}

export type KomutKaynak = 'sistem' | 'kullanici' | 'alarm' | 'zamanlayici'

export interface KomutLog {
  id: string
  sera_id: string
  sera_isim: string
  komut: KomutAdi
  zaman: string
  basarili: boolean
  kaynak: KomutKaynak
  kullanici_id?: string
  kullanici_adi?: string
}

export interface AlarmGecmisKaydi {
  id: string
  sera_id: string
  sera_isim: string
  durum: Durum
  baslangic: string
  bitis?: string
  onaylandi: boolean
}

export interface SistemLog {
  id: string
  seviye: 'INFO' | 'WARN' | 'ERROR'
  mesaj: string
  zaman: string
  sera_id?: string
  kullanici_adi?: string
}

export interface SeraEkleInput {
  isim: string
  bitki?: string
  alan?: number
  sensor_tipi?: string
  mqtt_topic?: string
  aciklama?: string
}

export interface SeraGuncelleInput {
  isim?: string
  bitki?: string
  alan?: number
  sensor_tipi?: string
  mqtt_topic?: string
  aciklama?: string
}

export interface BitkiProfilDetay {
  isim: string
  min_T: number; max_T: number; opt_T: number
  min_H: number; max_H: number; opt_H: number
  opt_CO2: number
  min_ph: number; max_ph: number; opt_ph: number
  min_ec: number; max_ec: number
  min_isik: number; max_isik: number
  renk: string
}

export interface ProvisioningTalep {
  talep_id: string
  mac_adresi: string
  sera_id: string
  baglanti_tipi: string
  firmware_versiyon: string
  talep_zamani: string
  durum: 'BEKLEMEDE' | 'ONAYLANDI' | 'REDDEDILDI'
  cihaz_id?: string
}

export interface OnaylamaYaniti {
  talep_id: string
  cihaz_id: string
  token: string
}

export type CihazDurum = 'CEVRIMICI' | 'GECIKMELI' | 'KOPUK' | 'BILINMIYOR'

export interface Cihaz {
  cihaz_id: string
  tesis_kodu: string
  sera_id: string
  seri_no: string
  mac_adresi: string
  baglanti_tipi: 'WiFi' | 'Ethernet' | 'RS485'
  firmware_versiyon: string
  son_gorulen: string
  aktif: boolean
  durum: CihazDurum
}

export interface CihazKayitSonuc {
  cihaz: Cihaz
  sifre: string
  firmware_konfig: Record<string, unknown>
}

export interface CihazKayitInput {
  tesis_kodu: string
  sera_id: string
  mac_adresi?: string
  firmware_versiyon?: string
  baglanti_tipi?: string
}

// ── Sensör Sağlık ──────────────────────────────────────────────
export type SensorSaglikDurum =
  | 'normal'
  | 'uyari'
  | 'arizali'
  | 'pik'
  | 'donmus'
  | 'kalibre_hatasi'

export interface SensorDetay {
  tip: string
  adres: string
  baglanti: string
  son_deger: Record<string, number> | null
  saglik: SensorSaglikDurum
  aciklama: string
  son_gecerli_okuma: string
  pik_sayisi_son_1saat: number
  ardisik_hata: number
  saglik_skoru: number
}

export interface Aktuator {
  tip: string
  gpio: number
  durum: 'acik' | 'kapali'
  son_degisim: string
  toplam_acik_sure: number
}

export interface BaglantıOlayı {
  zaman: string
  olay: 'BAGLANDI' | 'KOPTU'
  detay: string
}

export interface CihazDetayFull extends Cihaz {
  sinyal_gucu: number
  uptime_saniye: number
  yeniden_baslama_sayisi: number
  bellek_bos: number
  cpu_sicakligi: number
  sensorler: SensorDetay[]
  aktuatorler: Aktuator[]
  baglanti_gecmisi: BaglantıOlayı[]
}

export interface SensorGecmisOlcum {
  zaman: string
  deger: number
  pik: boolean
}

export interface SensorGecmis {
  cihaz_id: string
  sensor_tip: string
  birim: string
  normal_aralik: { min: number; max: number }
  olcumler: SensorGecmisOlcum[]
}

export interface CihazSaglikOzet {
  toplam_cihaz: number
  arizali_sensor: number
  pik_sensor: number
  donmus_sensor: number
  uyari_sensor: number
  genel_saglik: 'IYI' | 'UYARI' | 'KRITIK'
  cihazlar: Array<{
    cihaz_id: string
    durum: CihazDurum
    alarmlar: Array<{ tip: string; saglik: SensorSaglikDurum }>
  }>
}
