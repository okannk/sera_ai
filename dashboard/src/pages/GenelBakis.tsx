import { useState } from 'react'
import {
  AreaChart, Area, YAxis, LineChart, Line,
  XAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Legend,
} from 'recharts'
import { useData } from '../context/DataContext'
import { durumBadgeClass, durumLabel, durumRengi } from '../components/Sidebar'
import { SeraDetayPanel } from '../components/SeraDetayPanel'
import { KaynakBadge } from '../components/KaynakBadge'
import type { KomutAdi, KomutKaynak, SeraOzet } from '../types'

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }

// Renk haritası — CSS variable yerine hex (SVG uyumlu)
const DURUM_HEX: Record<string, string> = {
  NORMAL:      '#00d4aa',
  UYARI:       '#f59e0b',
  ALARM:       '#ef4444',
  ACIL_DURDUR: '#7c3aed',
}
function durumHex(durum: string): string {
  return DURUM_HEX[durum] ?? '#475569'
}

// Sera renkleri (trend grafiği için)
const SERA_RENK: Record<string, string> = {
  s1: '#00d4aa',
  s2: '#f59e0b',
  s3: '#a855f7',
  s4: '#3b82f6',
  s5: '#f97316',
}

function fmt(v: number | null | undefined, suffix = ''): string {
  if (v == null) return '—'
  return `${v}${suffix}`
}

function SummaryCard({ icon, label, value, sub, color = '#00d4aa', pulse = false }: {
  icon: string; label: string; value: string | number; sub?: string; color?: string; pulse?: boolean
}) {
  return (
    <div className="card rounded-xl p-5 flex flex-col gap-2">
      <div className="flex items-start justify-between">
        <span style={{ fontSize: 22 }}>{icon}</span>
        <span
          className="rounded-full"
          style={{
            width: 8, height: 8, background: color,
            boxShadow: `0 0 8px ${color}`, marginTop: 4,
            animation: pulse ? 'pulse 2s infinite' : undefined,
          }}
        />
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--t2)' }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--t3)' }}>{sub}</div>}
    </div>
  )
}

// SVG gradient fix: use style prop, not presentation attributes
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const gecerli = values.filter(v => v != null && !isNaN(v))
  const minV = gecerli.length ? Math.min(...gecerli) : 0
  const maxV = gecerli.length ? Math.max(...gecerli) : 0
  if (gecerli.length < 3 || maxV - minV < 0.05) {
    return (
      <div style={{ height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 9, color: 'var(--t3)' }}>veri toplanıyor…</span>
      </div>
    )
  }
  const data = gecerli.map(v => ({ v }))
  const gradId = `sp-${color.replace(/[^a-z0-9]/gi, '')}`
  // Veri aralığına göre padding: küçük varyasyonlar görünür olsun
  const range = Math.max(maxV - minV, 0.1)
  const domainMin = minV - range * 0.4
  const domainMax = maxV + range * 0.4
  return (
    <ResponsiveContainer width="100%" height={36}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        {/* YAxis gizli ama domain data-relative → sparkline eğri görünür */}
        <YAxis hide domain={[domainMin, domainMax]} />
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  style={{ stopColor: color, stopOpacity: 0.35 }} />
            <stop offset="95%" style={{ stopColor: color, stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <Area
          type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
          fill={`url(#${gradId})`} dot={false} isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function SeraKart({ sera, onDetay }: { sera: SeraOzet; onDetay: (id: string) => void }) {
  const { sensorGecmis, komutLog, komutGonder } = useData()
  const [komutYuklenen, setKomutYuklenen] = useState<string | null>(null)
  const [komutSonuc, setKomutSonuc]       = useState<{ ok: boolean; mesaj: string } | null>(null)

  const gecmis      = sensorGecmis[sera.id] ?? []
  const sicakliklar = gecmis.map(g => g.T)
  const s           = sera.sensor
  const c           = durumRengi(sera.durum)
  const cHex        = durumHex(sera.durum)
  const sonKomut    = komutLog.find(k => k.sera_id === sera.id)

  async function gonder(komut: KomutAdi) {
    setKomutYuklenen(komut)
    setKomutSonuc(null)
    const sonuc = await komutGonder(sera.id, komut, sera.isim)
    setKomutSonuc(sonuc)
    setKomutYuklenen(null)
    setTimeout(() => setKomutSonuc(null), 2500)
  }

  return (
    <div
      className="card card-hover rounded-xl flex flex-col"
      style={{ borderTop: `3px solid ${c}`, cursor: 'pointer' }}
      onClick={e => {
        // Buton tıklamalarının karta tıklamayla çakışmaması için
        if ((e.target as HTMLElement).closest('button')) return
        onDetay(sera.id)
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-2">
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 24 }}>{BITKI_EMOJI[sera.bitki] ?? '🌱'}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--t1)' }}>{sera.isim}</div>
            <div style={{ fontSize: 11, color: 'var(--t3)' }}>{sera.bitki} · {sera.alan} m²</div>
          </div>
        </div>
        <span
          className={`${durumBadgeClass(sera.durum)} rounded-full px-2.5 py-1 text-xs font-semibold flex items-center gap-1`}
          style={{ flexShrink: 0 }}
        >
          {(sera.durum === 'ALARM' || sera.durum === 'ACIL_DURDUR') && (
            <span style={{
              width: 5, height: 5, borderRadius: '50%', background: 'currentColor',
              display: 'inline-block', animation: 'pulse 1.5s infinite',
            }} />
          )}
          {durumLabel(sera.durum)}
        </span>
      </div>

      {/* Sparkline */}
      <div style={{ padding: '0 12px' }}>
        <Sparkline values={sicakliklar.slice(-60)} color={cHex} />
        {gecmis.length >= 3 && (
          <div style={{ fontSize: 9, color: 'var(--t3)', textAlign: 'right', marginTop: -4 }}>
            sıcaklık trendi ({gecmis.length} nokta)
          </div>
        )}
      </div>

      {/* Sensör değerleri */}
      {s ? (
        <div style={{ padding: '8px 14px 0' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {[
              { icon: '🌡️', label: 'Sıcaklık', val: fmt(s.T,      '°C'),  color: '#f97316' },
              { icon: '💧', label: 'Nem',       val: fmt(s.H,      '%'),   color: '#3b82f6' },
              { icon: '🌬️', label: 'CO₂',       val: fmt(s.co2,    ' ppm'), color: '#a855f7' },
              { icon: '🌱', label: 'Toprak',     val: fmt(s.toprak, '%'),  color: '#22c55e' },
            ].map(({ icon, label, val, color }) => (
              <div
                key={label}
                className="rounded-lg flex items-center gap-2"
                style={{ background: 'rgba(255,255,255,0.04)', padding: '6px 8px' }}
              >
                <span style={{ fontSize: 14 }}>{icon}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 10, color: 'var(--t3)' }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color }}>{val}</div>
                </div>
              </div>
            ))}
          </div>

          {/* pH + EC satırı */}
          <div className="flex gap-2 mt-2">
            {[
              { label: 'pH',     val: fmt(s.ph),                               color: '#06b6d4' },
              { label: 'EC',     val: s.ec != null ? `${s.ec} mS/cm` : '—',    color: '#f59e0b' },
              { label: 'Işık',   val: s.isik != null ? `${s.isik} lx` : '—',   color: '#fbbf24' },
            ].map(({ label, val, color }) => (
              <div
                key={label}
                className="flex-1 rounded-lg flex items-center justify-between"
                style={{ background: 'rgba(255,255,255,0.04)', padding: '4px 8px' }}
              >
                <span style={{ fontSize: 10, color: 'var(--t3)' }}>{label}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color }}>{val}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ padding: '16px 14px', color: 'var(--t3)', fontSize: 13, textAlign: 'center' }}>
          Veri bekleniyor…
        </div>
      )}

      {/* Hızlı komutlar */}
      <div style={{ padding: '10px 14px 14px', marginTop: 'auto' }}>
        <div className="flex gap-1.5 flex-wrap">
          {([
            ['💧', 'SULAMA_AC'], ['❄️', 'SOGUTMA_AC'], ['🌀', 'FAN_AC'], ['🔥', 'ISITICI_AC'],
          ] as [string, KomutAdi][]).map(([ico, k]) => (
            <button
              key={k}
              onClick={() => gonder(k)}
              disabled={komutYuklenen !== null}
              className="btn-ghost"
              style={{ padding: '4px 10px', fontSize: 12 }}
              title={k}
            >
              {komutYuklenen === k ? '…' : ico}
            </button>
          ))}
        </div>
        {komutSonuc ? (
          <div style={{ fontSize: 10, marginTop: 4, color: komutSonuc.ok ? 'var(--accent)' : 'var(--alarm)' }}>
            {komutSonuc.ok ? '✓' : '✗'} {komutSonuc.mesaj}
          </div>
        ) : sonKomut ? (
          <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
            Son: {sonKomut.komut} · {new Date(sonKomut.zaman).toLocaleTimeString('tr-TR')}
          </div>
        ) : null}
      </div>
    </div>
  )
}

// Alt panel: Çoklu sera sıcaklık trendi
function SicaklikTrendi() {
  const { seralar, sensorGecmis } = useData()

  // Son 30 ortak indeks
  const maxLen = Math.max(...seralar.map(s => (sensorGecmis[s.id] ?? []).length), 0)
  const baslangic = Math.max(0, maxLen - 30)

  const data = Array.from({ length: Math.min(maxLen, 30) }, (_, i) => {
    const idx = baslangic + i
    const row: Record<string, number | string> = {
      zaman: sensorGecmis[seralar[0]?.id]?.[idx]?.zaman ?? '',
    }
    seralar.forEach(s => {
      const val = sensorGecmis[s.id]?.[idx]?.T
      if (val !== undefined) row[s.id] = val
    })
    return row
  })

  const formatTime = (v: string) =>
    new Date(v).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  if (maxLen < 2) {
    return (
      <div className="card rounded-xl p-4">
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)', marginBottom: 8 }}>
          🌡️ Sıcaklık Trendi — Tüm Seralar
        </div>
        <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t3)', fontSize: 13 }}>
          Veri toplanıyor…
        </div>
      </div>
    )
  }

  return (
    <div className="card rounded-xl p-4">
      <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)', marginBottom: 12 }}>
        🌡️ Sıcaklık Trendi — Tüm Seralar
        <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--t3)', marginLeft: 8 }}>
          son {Math.min(maxLen, 30)} ölçüm
        </span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="zaman"
            tickFormatter={formatTime}
            tick={{ fontSize: 9, fill: 'var(--t3)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 9, fill: 'var(--t3)' }}
            tickFormatter={v => `${v}°`}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11 }}
            labelFormatter={v => formatTime(v as string)}
            formatter={(v) => [`${Number(v).toFixed(1)}°C`, '']}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: 'var(--t2)' }} />
          {seralar.map(s => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.isim}
              stroke={SERA_RENK[s.id] ?? '#888'}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// Alt panel: Son 10 komut
function SonKomutlar() {
  const { komutLog } = useData()
  const son10 = komutLog.slice(0, 10)

  const komutIcon: Record<string, string> = {
    SULAMA_AC: '💧', SULAMA_KAPAT: '💧',
    ISITICI_AC: '🔥', ISITICI_KAPAT: '🔥',
    SOGUTMA_AC: '❄️', SOGUTMA_KAPAT: '❄️',
    FAN_AC: '🌀', FAN_KAPAT: '🌀',
    ISIK_AC: '💡', ISIK_KAPAT: '💡',
    ACIL_DURDUR: '🚨',
  }

  return (
    <div className="card rounded-xl flex flex-col" style={{ height: '100%' }}>
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        fontWeight: 600, fontSize: 14, color: 'var(--t1)', flexShrink: 0,
      }}>
        📝 Son Komutlar
        <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--t3)', marginLeft: 8 }}>
          son {son10.length} işlem
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {son10.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
            Henüz komut gönderilmedi
          </div>
        ) : son10.map(k => (
          <div
            key={k.id}
            className="table-row"
            style={{ padding: '9px 16px', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <span style={{ fontSize: 16, flexShrink: 0 }}>{komutIcon[k.komut] ?? '⚙️'}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{k.komut}</div>
              <div style={{ fontSize: 11, color: 'var(--t3)' }}>{k.sera_isim}</div>
            </div>
            <KaynakBadge kaynak={(k.kaynak ?? 'kullanici') as KomutKaynak} />
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 10, color: k.basarili ? 'var(--accent)' : 'var(--alarm)' }}>
                {k.basarili ? '✓' : '✗'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--t3)' }}>
                {new Date(k.zaman).toLocaleTimeString('tr-TR')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function GenelBakis() {
  const { seralar, saglik, alarmlar, komutLog } = useData()
  const [secilenSera, setSecilenSera] = useState<string | null>(null)

  const alarmSayisi = saglik?.alarm_sayisi ?? 0
  const toplamKomut = komutLog.length

  return (
    <div className="page-root">
      {secilenSera && (
        <SeraDetayPanel seraId={secilenSera} onKapat={() => setSecilenSera(null)} />
      )}

      <div className="mb-5">
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Genel Bakış</h1>
        <p style={{ fontSize: 12, color: 'var(--t3)', marginTop: 1 }}>Tüm seraların anlık durumu · karta tıkla → detay</p>
      </div>

      {/* Özet kartlar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <SummaryCard
          icon="🏠" label="Toplam Sera" value={seralar.length}
          sub={`${seralar.filter(s => s.durum === 'NORMAL').length} normal`}
        />
        <SummaryCard
          icon="🚨" label="Aktif Alarm" value={alarmSayisi}
          color={alarmSayisi > 0 ? '#ef4444' : '#00d4aa'}
          pulse={alarmSayisi > 0}
          sub={alarmSayisi > 0 ? alarmlar.map(a => a.isim).join(', ') : 'Tümü normal'}
        />
        <SummaryCard
          icon="⏱" label="Sistem Uptime" value={saglik?.uptime_fmt ?? '—'}
          sub="Kesintisiz çalışma" color="#f59e0b"
        />
        <SummaryCard
          icon="⚙️" label="Toplam Komut" value={toplamKomut}
          sub="Bu oturumda" color="#a855f7"
        />
      </div>

      {/* Sera grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 mb-5">
        {seralar.map(sera => (
          <SeraKart key={sera.id} sera={sera} onDetay={setSecilenSera} />
        ))}
        {seralar.length === 0 && (
          <div
            className="col-span-3 text-center"
            style={{ padding: 60, color: 'var(--t3)' }}
          >
            <div style={{ fontSize: 48, marginBottom: 12 }}>🌿</div>
            <div style={{ fontSize: 13 }}>Backend bağlantısı bekleniyor…</div>
          </div>
        )}
      </div>

      {/* Alt panel: Sıcaklık trendi + Son komutlar */}
      {seralar.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            <SicaklikTrendi />
          </div>
          <SonKomutlar />
        </div>
      )}
    </div>
  )
}
