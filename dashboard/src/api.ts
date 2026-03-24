import type { ApiYanit, SeraOzet, SeraDetay, SaglikDurumu, Alarm, KomutAdi, SeraEkleInput, SeraGuncelleInput, Cihaz, CihazKayitSonuc, CihazKayitInput, ProvisioningTalep, OnaylamaYaniti, CihazDetayFull, SensorGecmis, CihazSaglikOzet, BitkiProfilDetay } from './types'

function getHeaders(extraHeaders?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extraHeaders }

  // JWT Bearer token (öncelikli)
  const accessToken = localStorage.getItem('access_token')
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  // X-API-Key fallback (VITE_API_KEY tanımlıysa ve JWT yoksa)
  const apiKey = import.meta.env.VITE_API_KEY
  if (apiKey && !accessToken) {
    headers['X-API-Key'] = apiKey
  }

  return headers
}

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  const headers = getHeaders(options?.headers as Record<string, string>)
  const response = await fetch(path, { ...options, headers })

  if (response.status === 401) {
    // Token geçersiz — temizle ve AuthContext'e bildir (Login sayfasını gösterir)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.dispatchEvent(new Event('auth:token-updated'))
  }

  return response
}

async function get<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  const text = await res.text()
  if (!text) throw new Error('Sunucudan boş yanıt')
  const json: ApiYanit<T> = JSON.parse(text)
  if (!json.success) throw new Error(json.hata ?? json.error ?? 'API hatası')
  return json.data
}

async function put<T>(path: string, body: object): Promise<T> {
  const res = await apiFetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json: ApiYanit<T> = await res.json()
  if (!json.success) throw new Error(json.hata ?? json.error ?? 'API hatası')
  return json.data
}

async function del_(path: string): Promise<void> {
  await apiFetch(path, { method: 'DELETE' })
}

async function post<T>(path: string, body: object): Promise<T> {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json: ApiYanit<T> = await res.json()
  if (!json.success) throw new Error(json.hata ?? json.error ?? 'API hatası')
  return json.data
}

export { apiFetch, getHeaders }

const V1 = '/api/v1'

export const api = {
  seralar: () => get<SeraOzet[]>(`${V1}/seralar`),
  seraDetay: (sid: string) => get<SeraDetay>(`${V1}/seralar/${sid}`),
  saglik: () => get<SaglikDurumu>(`${V1}/sistem/saglik`),
  alarmlar: () => get<Alarm[]>(`${V1}/alarm`),
  komutGonder: (sid: string, komut: KomutAdi) =>
    post<{ basarili: boolean; komut: string; sera_id: string }>(
      `${V1}/seralar/${sid}/komut`,
      { komut }
    ),
  seraEkle:     (data: SeraEkleInput) => post<SeraOzet>(`${V1}/seralar`, data),
  seraGuncelle: (sid: string, data: SeraGuncelleInput) => put<SeraOzet>(`${V1}/seralar/${sid}`, data),
  seraSil:      (sid: string) => del_(`${V1}/seralar/${sid}`),
  cihazlar:     () => get<Cihaz[]>(`${V1}/cihazlar`),
  cihazDetay:   (cid: string) => get<Cihaz>(`${V1}/cihazlar/${cid}`),
  cihazKayit:   (data: CihazKayitInput) => post<CihazKayitSonuc>(`${V1}/cihazlar/kayit`, data),
  cihazSifirla: (cid: string) => post<{ cihaz_id: string; sifre: string }>(`${V1}/cihazlar/${cid}/sifre-sifirla`, {}),
  cihazSil:     (cid: string) => del_(`${V1}/cihazlar/${cid}`),
  cihazDetayFull:    (cid: string) => get<CihazDetayFull>(`${V1}/cihazlar/${cid}/detay`),
  cihazSensorGecmis: (cid: string, tip: string) => get<SensorGecmis>(`${V1}/cihazlar/${cid}/sensor-gecmis/${encodeURIComponent(tip)}`),
  cihazSaglikOzet:   () => get<CihazSaglikOzet>(`${V1}/cihazlar/saglik-ozet`),
  bitkiProfilleri: () => get<BitkiProfilDetay[]>(`${V1}/bitki-profilleri`),
  sifreDogrula: (sifre: string) => post<{ dogrulandi: boolean }>(`${V1}/auth/verify-password`, { sifre }),
  // Provisioning
  bekleyenTalepler: () => get<ProvisioningTalep[]>(`${V1}/provisioning/bekleyen-talepler`),
  provisioningDurum: (id: string) => get<{ durum: string; cihaz_id?: string; token?: string }>(`${V1}/provisioning/durum/${id}`),
  provisioningOnayla: (id: string) => post<OnaylamaYaniti>(`${V1}/provisioning/onayla/${id}`, {}),
  provisioningReddet: (id: string) => post<{ durum: string }>(`${V1}/provisioning/reddet/${id}`, {}),
}
