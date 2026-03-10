import { useEffect, useRef, useState } from 'react'
import {
  AreaChart, Area, YAxis, ResponsiveContainer, Tooltip,
} from 'recharts'
import type { SeraDetay, SensorGecmis, KomutAdi } from '../types'
import { StatusBadge } from './StatusBadge'
import { KomutPanel } from './KomutPanel'
import { api } from '../api'
import { useData } from '../context/DataContext'

interface Props {
  seraId: string
  onKapat: () => void
}

const SENSOR_TANIM = [
  { alan: 'T'      as keyof SensorGecmis, label: 'Sıcaklık',   unit: '°C',   icon: '🌡️', color: '#f97316' },
  { alan: 'H'      as keyof SensorGecmis, label: 'Nem',         unit: '%',    icon: '💧', color: '#3b82f6' },
  { alan: 'co2'    as keyof SensorGecmis, label: 'CO₂',         unit: ' ppm', icon: '🌬️', color: '#a855f7' },
  { alan: 'toprak' as keyof SensorGecmis, label: 'Toprak Nemi', unit: '%',    icon: '🌱', color: '#22c55e' },
]

const SENSOR_EKSTRA = [
  { alan: 'isik'  as keyof SensorGecmis, label: 'Işık',  unit: ' lx',    icon: '☀️', color: '#fbbf24' },
  { alan: 'ph'    as keyof SensorGecmis, label: 'pH',    unit: '',        icon: '⚗️', color: '#06b6d4' },
  { alan: 'ec'    as keyof SensorGecmis, label: 'EC',    unit: ' mS/cm', icon: '⚡', color: '#f59e0b' },
]

const KOMUT_ICON: Record<string, string> = {
  SULAMA_AC: '💧', SULAMA_KAPAT: '💧',
  ISITICI_AC: '🔥', ISITICI_KAPAT: '🔥',
  SOGUTMA_AC: '❄️', SOGUTMA_KAPAT: '❄️',
  FAN_AC: '🌀', FAN_KAPAT: '🌀',
  ISIK_AC: '💡', ISIK_KAPAT: '💡',
  ACIL_DURDUR: '🚨',
}

function MiniChart({ data, alan, color }: {
  data: SensorGecmis[]; alan: keyof SensorGecmis; color: string
}) {
  const son30 = data.slice(-30)
  const vals = son30.map(d => ({ v: d[alan] as number })).filter(d => d.v != null)
  if (vals.length < 3) return <div style={{ height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--t3)' }}>veri toplanıyor…</div>
  const gradId = `mc-${alan}`
  const nums = vals.map(d => d.v)
  const minV = Math.min(...nums); const maxV = Math.max(...nums)
  const range = Math.max(maxV - minV, 0.01)
  return (
    <ResponsiveContainer width="100%" height={40}>
      <AreaChart data={vals} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  style={{ stopColor: color, stopOpacity: 0.3 }} />
            <stop offset="95%" style={{ stopColor: color, stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <YAxis hide domain={[minV - range * 0.3, maxV + range * 0.3]} />
        <Tooltip
          contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 10, padding: '2px 8px' }}
          formatter={(v) => [Number(v).toFixed(1), '']}
          labelFormatter={() => ''}
        />
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} fill={`url(#${gradId})`} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function SeraDetayPanel({ seraId, onKapat }: Props) {
  const [detay, setDetay] = useState<SeraDetay | null>(null)
  const { sensorGecmis, komutLog, komutGonder } = useData()
  const overlayRef = useRef<HTMLDivElement>(null)
  const gecmis = sensorGecmis[seraId] ?? []
  const sonKomutlar = komutLog.filter(k => k.sera_id === seraId).slice(0, 20)

  useEffect(() => {
    let aktif = true
    async function yukle() {
      try {
        const d = await api.seraDetay(seraId)
        if (aktif) setDetay(d)
      } catch { /* sessiz */ }
    }
    yukle()
    const id = setInterval(yukle, 2000)
    return () => { aktif = false; clearInterval(id) }
  }, [seraId])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onKapat() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onKapat])

  async function komutGonderLocal(komut: KomutAdi) {
    await komutGonder(seraId, komut, detay?.isim ?? seraId)
  }

  const s = detay?.sensor
  const profil = detay?.profil

  return (
    <div
      ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onKapat() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'flex-end',
      }}
    >
      <div
        style={{
          width: 'min(960px, 95vw)', height: '100%',
          background: 'var(--bg)', borderLeft: '1px solid var(--border)',
          overflowY: 'auto', display: 'flex', flexDirection: 'column',
        }}
      >
        {/* ── Header ──────────────────────────────── */}
        <div style={{
          padding: '20px 24px 16px', borderBottom: '1px solid var(--border)',
          background: 'var(--card)', position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>
                {detay ? detay.isim : 'Yükleniyor…'}
              </h2>
              {detay && <StatusBadge durum={detay.durum} size="lg" />}
            </div>
            {detay && (
              <p style={{ fontSize: 12, color: 'var(--t3)', marginTop: 4 }}>
                {detay.bitki} · {detay.alan} m²
                {detay.esp32_ip && <span style={{ marginLeft: 10, color: 'var(--t3)' }}>IP: {detay.esp32_ip}</span>}
              </p>
            )}
          </div>
          <button
            onClick={onKapat}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--t2)', fontSize: 22, padding: '2px 6px',
              borderRadius: 6, lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: 24, flex: 1 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

            {/* ── Sol: Sensörler + Grafikler ─────── */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Ana sensörler: grafik + değer */}
              <div style={{ background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>
                  📡 Sensörler
                </div>
                <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {SENSOR_TANIM.map(({ alan, label, unit, icon, color }) => {
                    const val = s?.[alan as keyof typeof s] as number | undefined
                    const durum = val == null ? 'Hata' : 'Normal'
                    const durumRenk = val == null ? 'var(--alarm)' : 'var(--accent)'
                    return (
                      <div key={label}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 14 }}>{icon}</span>
                            <span style={{ fontSize: 12, color: 'var(--t2)' }}>{label}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 14, fontWeight: 700, color }}>
                              {val != null ? `${val}${unit}` : '—'}
                            </span>
                            <span style={{
                              fontSize: 10, padding: '1px 6px', borderRadius: 10,
                              background: val == null ? 'var(--alarm-dim)' : 'rgba(16,185,129,0.12)',
                              color: durumRenk, border: `1px solid ${durumRenk}33`,
                            }}>
                              {durum}
                            </span>
                          </div>
                        </div>
                        <MiniChart data={gecmis} alan={alan} color={color} />
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Ekstra sensörler */}
              <div style={{ background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>
                  🔬 Diğer Parametreler
                </div>
                <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {SENSOR_EKSTRA.map(({ alan, label, unit, icon, color }) => {
                    const val = s?.[alan as keyof typeof s] as number | undefined
                    return (
                      <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 14 }}>{icon}</span>
                          <span style={{ fontSize: 12, color: 'var(--t2)' }}>{label}</span>
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 700, color }}>
                          {val != null ? `${val}${unit}` : '—'}
                        </span>
                      </div>
                    )
                  })}
                  {s?.zaman && (
                    <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                      Son güncelleme: {new Date(s.zaman).toLocaleTimeString('tr-TR')}
                    </div>
                  )}
                </div>
              </div>

              {/* Circuit Breaker */}
              {detay?.cb && (
                <div style={{ background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', padding: '12px 16px' }}>
                  <div style={{ fontSize: 12, color: 'var(--t3)', marginBottom: 6 }}>Circuit Breaker</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--t2)' }}>{detay.cb.durum}</span>
                    <span style={{ color: 'var(--t3)' }}>{detay.cb.hata_sayisi} hata</span>
                  </div>
                </div>
              )}
            </div>

            {/* ── Sağ: Aktüatörler + Profil ─────── */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Aktüatörler */}
              <div style={{ background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', padding: '16px' }}>
                <KomutPanel seraId={seraId} onKomut={komutGonderLocal} />
              </div>

              {/* Bitki Profili */}
              {profil && (
                <div style={{ background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>
                    🌿 Bitki Profili
                  </div>
                  <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {[
                      ['Min T', `${profil.min_T ?? profil.minT ?? '—'}°C`],
                      ['Maks T', `${profil.max_T ?? profil.maxT ?? '—'}°C`],
                      ['Opt T', `${profil.opt_T ?? profil.optT ?? '—'}°C`],
                      ['Min H', `${profil.min_H ?? profil.minH ?? '—'}%`],
                      ['Maks H', `${profil.max_H ?? profil.maxH ?? '—'}%`],
                      ['Opt CO₂', `${profil.opt_CO2 ?? '—'} ppm`],
                    ].map(([k, v]) => (
                      <div key={k} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: '8px 12px', textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 3 }}>{k}</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Komut Geçmişi ────────────────────── */}
          <div style={{ marginTop: 20, background: 'var(--card)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, color: 'var(--t1)' }}>
              📝 Son Komutlar
              <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--t3)', marginLeft: 8 }}>son {sonKomutlar.length}</span>
            </div>
            {sonKomutlar.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>Henüz komut gönderilmedi</div>
            ) : (
              <div>
                {sonKomutlar.map(k => (
                  <div key={k.id} className="table-row" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 16 }}>{KOMUT_ICON[k.komut] ?? '⚙️'}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{k.komut}</div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 10, color: k.basarili ? 'var(--accent)' : 'var(--alarm)' }}>
                        {k.basarili ? '✓ Başarılı' : '✗ Hata'}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--t3)' }}>
                        {new Date(k.zaman).toLocaleTimeString('tr-TR')}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
