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

export interface KomutLog {
  id: string
  sera_id: string
  sera_isim: string
  komut: KomutAdi
  zaman: string
  basarili: boolean
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
}

export interface SeraEkleInput {
  isim: string
  bitki?: string
  alan?: number
  esp32_ip?: string
}

export interface SeraGuncelleInput {
  isim?: string
  bitki?: string
  alan?: number
  esp32_ip?: string
}
