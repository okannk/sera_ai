import type { ApiYanit, SeraOzet, SeraDetay, SaglikDurumu, Alarm, KomutAdi } from './types'

const API_KEY = import.meta.env.VITE_API_KEY ?? ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
  })
  const json: ApiYanit<T> = await res.json()
  if (!json.success) throw new Error(json.hata ?? json.error ?? 'API hatası')
  return json.data
}

async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
    body: JSON.stringify(body),
  })
  const json: ApiYanit<T> = await res.json()
  if (!json.success) throw new Error(json.hata ?? json.error ?? 'API hatası')
  return json.data
}

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
}
