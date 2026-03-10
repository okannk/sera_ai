import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type {
  SeraOzet, SaglikDurumu, Alarm, SensorGecmis,
  KomutAdi, KomutLog, KomutKaynak, AlarmGecmisKaydi, SistemLog,
} from '../types'

const MAX_GECMIS = 300

interface DataCtx {
  seralar: SeraOzet[]
  saglik: SaglikDurumu | null
  alarmlar: Alarm[]
  sensorGecmis: Record<string, SensorGecmis[]>
  alarmGecmis: AlarmGecmisKaydi[]
  komutLog: KomutLog[]
  sistemLog: SistemLog[]
  yukleniyor: boolean
  hata: string | null
  sonGuncelleme: Date | null
  komutGonder: (sid: string, komut: KomutAdi, seraIsim?: string, kaynak?: KomutKaynak) => Promise<{ ok: boolean; mesaj: string }>
  alarmOnayla: (id: string) => void
}

const DataContext = createContext<DataCtx | null>(null)

let _logId = 0
function logId() { return `log-${++_logId}` }

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [seralar, setSeralar]         = useState<SeraOzet[]>([])
  const [saglik, setSaglik]           = useState<SaglikDurumu | null>(null)
  const [alarmlar, setAlarmlar]       = useState<Alarm[]>([])
  const [sensorGecmis, setSensorGecmis] = useState<Record<string, SensorGecmis[]>>({})
  const [alarmGecmis, setAlarmGecmis] = useState<AlarmGecmisKaydi[]>([])
  const [komutLog, setKomutLog]       = useState<KomutLog[]>([])
  const [sistemLog, setSistemLog]     = useState<SistemLog[]>(() => [
    { id: logId(), seviye: 'INFO',  mesaj: 'Sera AI sistemi başlatıldı',              zaman: new Date().toISOString() },
    { id: logId(), seviye: 'INFO',  mesaj: 'FastAPI sunucu bağlantısı kuruldu',        zaman: new Date().toISOString() },
    { id: logId(), seviye: 'INFO',  mesaj: 'RLAjan Q-tablosu yüklendi (2430 durum)', zaman: new Date().toISOString() },
  ])
  const [yukleniyor, setYukleniyor]   = useState(true)
  const [hata, setHata]               = useState<string | null>(null)
  const [sonGuncelleme, setSonGuncelleme] = useState<Date | null>(null)

  const oncekiAlarmIdler = useRef<Set<string>>(new Set())
  const pollSayac = useRef(0)

  const addSistemLog = useCallback((seviye: SistemLog['seviye'], mesaj: string, sera_id?: string) => {
    setSistemLog(prev => [
      { id: logId(), seviye, mesaj, zaman: new Date().toISOString(), sera_id },
      ...prev,
    ].slice(0, 200))
  }, [])

  const yukle = useCallback(async () => {
    try {
      const [s, sag, al] = await Promise.all([api.seralar(), api.saglik(), api.alarmlar()])

      setSeralar(s)
      setSaglik(sag)
      setAlarmlar(al)
      setSonGuncelleme(new Date())
      setHata(null)
      setYukleniyor(false)

      // Sensör geçmişi biriktir
      setSensorGecmis(prev => {
        const yeni = { ...prev }
        for (const sera of s) {
          if (!sera.sensor) continue
          const nokta: SensorGecmis = {
            zaman:  sera.sensor.zaman,
            T:      sera.sensor.T,
            H:      sera.sensor.H,
            co2:    sera.sensor.co2,
            toprak: sera.sensor.toprak,
            isik:   sera.sensor.isik,
          }
          const mevcut = yeni[sera.id] ?? []
          const son = mevcut[mevcut.length - 1]
          if (!son || son.zaman !== nokta.zaman) {
            yeni[sera.id] = [...mevcut.slice(-(MAX_GECMIS - 1)), nokta]
          }
        }
        return yeni
      })

      // Alarm geçmişini güncelle
      const yeniIdler = new Set(al.map(a => a.sera_id))
      const eskiIdler = oncekiAlarmIdler.current

      const yeniAlarmlar = al.filter(a => !eskiIdler.has(a.sera_id))
      if (yeniAlarmlar.length > 0) {
        setAlarmGecmis(prev => [
          ...yeniAlarmlar.map(a => ({
            id: `${a.sera_id}-${Date.now()}`,
            sera_id: a.sera_id, sera_isim: a.isim,
            durum: a.durum, baslangic: new Date().toISOString(),
            onaylandi: false,
          })),
          ...prev,
        ].slice(0, 100))
        yeniAlarmlar.forEach(a => addSistemLog('WARN', `${a.isim} → ${a.durum} durumuna geçti`, a.sera_id))
      }

      const cozulenIdler = [...eskiIdler].filter(id => !yeniIdler.has(id))
      if (cozulenIdler.length > 0) {
        setAlarmGecmis(prev => prev.map(a =>
          cozulenIdler.includes(a.sera_id) && !a.bitis
            ? { ...a, bitis: new Date().toISOString() } : a
        ))
        cozulenIdler.forEach(id => {
          const sera = s.find(x => x.id === id)
          addSistemLog('INFO', `${sera?.isim ?? id} normale döndü`, id)
        })
      }

      oncekiAlarmIdler.current = yeniIdler

      // Her 15 polling (30sn) bir INFO log
      pollSayac.current++
      if (pollSayac.current % 15 === 0) {
        const aktif = s.filter(x => x.durum === 'NORMAL').length
        addSistemLog('INFO', `Durum kontrolü: ${aktif}/${s.length} sera normal`)
      }

    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Bağlantı hatası'
      setHata(msg)
      setYukleniyor(false)
      addSistemLog('ERROR', `API hatası: ${msg}`)
    }
  }, [addSistemLog])

  useEffect(() => {
    yukle()
    const id = setInterval(yukle, 2000)
    return () => clearInterval(id)
  }, [yukle])

  const komutGonder = useCallback(async (
    sid: string, komut: KomutAdi, seraIsim = sid, kaynak: KomutKaynak = 'kullanici'
  ) => {
    try {
      await api.komutGonder(sid, komut)
      const log: KomutLog = {
        id: `${sid}-${komut}-${Date.now()}`, sera_id: sid,
        sera_isim: seraIsim, komut, zaman: new Date().toISOString(),
        basarili: true, kaynak,
      }
      setKomutLog(prev => [log, ...prev].slice(0, 100))
      addSistemLog('INFO', `Komut: ${seraIsim} → ${komut}`, sid)
      return { ok: true, mesaj: `${komut} gönderildi` }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Hata'
      const log: KomutLog = {
        id: `${sid}-${komut}-${Date.now()}`, sera_id: sid,
        sera_isim: seraIsim, komut, zaman: new Date().toISOString(),
        basarili: false, kaynak,
      }
      setKomutLog(prev => [log, ...prev].slice(0, 100))
      addSistemLog('ERROR', `Komut başarısız: ${seraIsim} → ${komut} (${msg})`, sid)
      return { ok: false, mesaj: msg }
    }
  }, [addSistemLog])

  const alarmOnayla = useCallback((id: string) => {
    setAlarmGecmis(prev => prev.map(a => a.id === id ? { ...a, onaylandi: true } : a))
    addSistemLog('INFO', `Alarm onaylandı: ${id}`)
  }, [addSistemLog])

  return (
    <DataContext.Provider value={{
      seralar, saglik, alarmlar, sensorGecmis, alarmGecmis,
      komutLog, sistemLog, yukleniyor, hata, sonGuncelleme,
      komutGonder, alarmOnayla,
    }}>
      {children}
    </DataContext.Provider>
  )
}

export function useData() {
  const ctx = useContext(DataContext)
  if (!ctx) throw new Error('useData must be used within DataProvider')
  return ctx
}
