import { useState, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'
import { useData } from '../context/DataContext'
import type { SensorGecmis } from '../types'

type ZamanAraligi = '5dk' | '15dk' | 'tamami'
type Mod = 'tekli' | 'karsilastirma'

const SERA_RENKLER: Record<string, string> = {
  s1: '#00d4aa',
  s2: '#f59e0b',
  s3: '#a855f7',
  s4: '#3b82f6',
}

interface GrafikProps {
  baslik: string
  alan: keyof Omit<SensorGecmis, 'zaman'>
  birim: string
  renk: string
  data: SensorGecmis[]
  optLine?: number
  mod: Mod
  tumData: Record<string, SensorGecmis[]>
  seralar: { id: string; isim: string }[]
  yukseklik?: number
}

function Grafik({ baslik, alan, birim, renk, data, optLine, mod, tumData, seralar, yukseklik = 160 }: GrafikProps) {
  const formatTime = (v: string) =>
    new Date(v).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartData: any[] = useMemo(() => {
    if (mod === 'tekli') return data
    const maxLen = Math.max(...Object.values(tumData).map(d => d.length), 0)
    return Array.from({ length: maxLen }, (_, i) => {
      const row: Record<string, string | number> = {
        zaman: tumData[seralar[0]?.id]?.[i]?.zaman ?? '',
      }
      seralar.forEach(s => {
        const val = tumData[s.id]?.[i]?.[alan]
        if (val !== undefined) row[s.id] = val as number
      })
      return row
    })
  }, [mod, data, tumData, seralar, alan])

  const sonDeger = data.length > 0 ? (data[data.length - 1]?.[alan] as number) : null

  return (
    <div className="card rounded-xl p-4 flex flex-col">
      <div className="panel-title" style={{ marginBottom: 12, flexShrink: 0 }}>
        {baslik}
        {sonDeger != null && mod === 'tekli' && (
          <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--t3)', marginLeft: 8 }}>
            son: <span style={{ color: renk, fontWeight: 600 }}>
              {sonDeger.toFixed(1)}{birim}
            </span>
          </span>
        )}
      </div>
      <div style={{ flex: 1 }}>
        <ResponsiveContainer width="100%" height={yukseklik}>
          <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="zaman"
              tickFormatter={formatTime}
              tick={{ fontSize: 9, fill: 'var(--t3)', fontFamily: 'monospace' }}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 9, fill: 'var(--t3)', fontFamily: 'monospace' }} tickFormatter={v => `${Math.round(v)}`} />
            <Tooltip
              contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11, fontFamily: 'monospace' }}
              labelFormatter={v => formatTime(v as string)}
              formatter={(v) => [`${Number(v).toFixed(1)}${birim}`, '']}
            />
            {optLine !== undefined && (
              <ReferenceLine y={optLine} stroke={renk} strokeDasharray="4 4" opacity={0.4} />
            )}
            {mod === 'tekli' ? (
              <Line type="monotone" dataKey={alan} stroke={renk} strokeWidth={2} dot={false} isAnimationActive={false} />
            ) : (
              <>
                <Legend wrapperStyle={{ fontSize: 11, color: 'var(--t2)' }} />
                {seralar.map(s => (
                  <Line
                    key={s.id}
                    type="monotone"
                    dataKey={s.id}
                    name={s.isim}
                    stroke={SERA_RENKLER[s.id] ?? '#888'}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function Grafikler() {
  const { seralar, sensorGecmis } = useData()
  const [secilenId, setSecilenId] = useState<string>('')
  const [aralik, setAralik]       = useState<ZamanAraligi>('5dk')
  const [mod, setMod]             = useState<Mod>('tekli')

  const aktifId = secilenId || seralar[0]?.id || ''

  const filtrele = (data: SensorGecmis[]): SensorGecmis[] => {
    const limitler: Record<ZamanAraligi, number> = { '5dk': 150, '15dk': 450, tamami: 9999 }
    return data.slice(-limitler[aralik])
  }

  const aktifData   = filtrele(sensorGecmis[aktifId] ?? [])
  const tumFiltreli = Object.fromEntries(
    Object.entries(sensorGecmis).map(([k, v]) => [k, filtrele(v)])
  )

  const aktifSera = seralar.find(s => s.id === aktifId)

  // Toprak mock verisi: backend randint(300,700) → 300-700 arası
  // Işık mock verisi: backend randint(200,900) → 200-900 arası
  const hasToprak = aktifData.some(d => d.toprak != null)
  const hasIsik   = aktifData.some(d => d.isik != null)

  return (
    <div className="page-root">
      {/* Başlık + kontroller */}
      <div className="mb-5 flex flex-wrap items-end gap-4" style={{ flexShrink: 0 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Grafikler</h1>
          <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Anlık sensör verileri</p>
        </div>

        <div className="flex flex-wrap gap-2 ml-auto items-center">
          {/* Sera seçici */}
          <select
            className="input-field"
            value={secilenId}
            onChange={e => setSecilenId(e.target.value)}
            disabled={mod === 'karsilastirma'}
          >
            {seralar.map(s => (
              <option key={s.id} value={s.id}>{s.isim} — {s.bitki}</option>
            ))}
          </select>

          {/* Zaman aralığı */}
          <div className="flex gap-1">
            {(['5dk', '15dk', 'tamami'] as ZamanAraligi[]).map(a => (
              <button key={a} className={`btn-ghost ${aralik === a ? 'active' : ''}`} onClick={() => setAralik(a)}>
                {a === 'tamami' ? 'Tümü' : a}
              </button>
            ))}
          </div>

          {/* Karşılaştırma */}
          <button
            className={`btn-ghost ${mod === 'karsilastirma' ? 'active' : ''}`}
            onClick={() => setMod(m => m === 'tekli' ? 'karsilastirma' : 'tekli')}
          >
            🔀 Karşılaştır
          </button>
        </div>
      </div>

      {mod === 'karsilastirma' && (
        <div
          className="rounded-xl mb-4 flex items-center gap-2"
          style={{ background: 'var(--accent-dim)', border: '1px solid rgba(0,212,170,0.2)', padding: '8px 14px', flexShrink: 0 }}
        >
          <span style={{ color: 'var(--accent)', fontSize: 13 }}>
            Karşılaştırma modu: tüm seralar aynı grafikte gösteriliyor
          </span>
          {seralar.map(s => (
            <span key={s.id} className="flex items-center gap-1" style={{ fontSize: 12, color: 'var(--t2)' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: SERA_RENKLER[s.id], display: 'inline-block' }} />
              {s.isim}
            </span>
          ))}
        </div>
      )}

      {/* Veri yok durumu */}
      {aktifData.length === 0 && seralar.length > 0 && (
        <div
          className="card rounded-xl flex-1 flex items-center justify-center"
          style={{ color: 'var(--t3)', flexDirection: 'column', gap: 12 }}
        >
          <div style={{ fontSize: 40 }}>📊</div>
          <div style={{ fontSize: 13 }}>Veri toplanıyor… (2 sn aralıkla güncellenir)</div>
        </div>
      )}

      {/* 2x2 ana grafik grid: T, H, CO₂, Işık */}
      {aktifData.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <Grafik
              baslik="🌡️ Sıcaklık" alan="T" birim="°C" renk="#f97316"
              data={aktifData}
              optLine={aktifSera ? undefined : undefined}
              mod={mod} tumData={tumFiltreli} seralar={seralar}
            />
            <Grafik
              baslik="💧 Nem" alan="H" birim="%" renk="#3b82f6"
              data={aktifData}
              mod={mod} tumData={tumFiltreli} seralar={seralar}
            />
            <Grafik
              baslik="🌬️ CO₂" alan="co2" birim=" ppm" renk="#a855f7"
              data={aktifData}
              mod={mod} tumData={tumFiltreli} seralar={seralar}
            />
            <Grafik
              baslik={`💡 Işık${!hasIsik ? ' (veri bekleniyor)' : ''}`}
              alan="isik" birim=" lx" renk="#fbbf24"
              data={aktifData}
              mod={mod} tumData={tumFiltreli} seralar={seralar}
            />
          </div>

          {/* Toprak Nemi — tam genişlik */}
          <div>
            <Grafik
              baslik={`🌱 Toprak Nemi${!hasToprak ? ' (veri bekleniyor)' : ''}`}
              alan="toprak" birim="" renk="#22c55e"
              data={aktifData}
              mod={mod} tumData={tumFiltreli} seralar={seralar}
              yukseklik={140}
            />
          </div>
        </>
      )}
    </div>
  )
}
