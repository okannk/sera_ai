import { useState } from 'react'
import { useData } from '../context/DataContext'
import type { Durum, KomutAdi, SeraOzet } from '../types'

export type Sayfa =
  | 'genel' | 'grafikler' | 'alarm'
  | 'sulama' | 'sulama_grup'
  | 'ekonomi' | 'loglar' | 'ayarlar'

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }

const AKTUATORLER: { komutAc: KomutAdi; komutKapat: KomutAdi; icon: string }[] = [
  { komutAc: 'SULAMA_AC',  komutKapat: 'SULAMA_KAPAT',  icon: '💧' },
  { komutAc: 'SOGUTMA_AC', komutKapat: 'SOGUTMA_KAPAT', icon: '❄️' },
  { komutAc: 'FAN_AC',     komutKapat: 'FAN_KAPAT',     icon: '🌀' },
  { komutAc: 'ISITICI_AC', komutKapat: 'ISITICI_KAPAT', icon: '🔥' },
]

function SeraItem({ sera }: { sera: SeraOzet }) {
  const { komutGonder, komutLog } = useData()
  const [yuklenen, setYuklenen] = useState<string | null>(null)

  function isAcik(komutAc: string, komutKapat: string): boolean {
    const son = komutLog
      .filter(k => k.sera_id === sera.id && (k.komut === komutAc || k.komut === komutKapat))
      .sort((a, b) => new Date(b.zaman).getTime() - new Date(a.zaman).getTime())[0]
    return son?.komut === komutAc
  }

  async function toggle(komutAc: KomutAdi, komutKapat: KomutAdi, icon: string) {
    const acik = isAcik(komutAc, komutKapat)
    setYuklenen(icon)
    await komutGonder(sera.id, acik ? komutKapat : komutAc, sera.isim)
    setYuklenen(null)
  }

  const c = durumRengi(sera.durum)

  return (
    <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
      {/* Sera adı + durum noktası */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: c, boxShadow: `0 0 5px ${c}`,
          animation: (sera.durum === 'ALARM' || sera.durum === 'ACIL_DURDUR') ? 'pulse 1.5s infinite' : 'none',
        }} />
        <span style={{ fontSize: 13 }}>{BITKI_EMOJI[sera.bitki] ?? '🌱'}</span>
        <span style={{
          fontSize: 12, fontWeight: 600, color: 'var(--t1)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
        }}>
          {sera.isim}
        </span>
      </div>

      {/* Aktüatör toggle'ları */}
      <div style={{ display: 'flex', gap: 3 }}>
        {AKTUATORLER.map(({ komutAc, komutKapat, icon }) => {
          const on = isAcik(komutAc, komutKapat)
          return (
            <button
              key={komutAc}
              onClick={() => toggle(komutAc, komutKapat, icon)}
              disabled={yuklenen !== null}
              title={`${komutAc.replace('_AC', '')} — ${on ? 'Kapat' : 'Aç'}`}
              style={{
                flex: 1, height: 24, fontSize: 11,
                background: on ? 'var(--accent-dim)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${on ? 'rgba(0,212,170,0.35)' : 'var(--border)'}`,
                borderRadius: 4, cursor: 'pointer',
                opacity: yuklenen !== null ? 0.5 : 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              {yuklenen === icon ? '·' : icon}
            </button>
          )
        })}
      </div>
    </div>
  )
}

interface Props {
  hata: boolean
  acik: boolean
  onKapat: () => void
}

export function Sidebar({ hata, acik, onKapat }: Props) {
  const { seralar } = useData()

  return (
    <>
      {/* Overlay (mobile) */}
      {acik && (
        <div
          className="fixed inset-0 z-30 lg:hidden"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={onKapat}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className="fixed left-0 z-40 flex flex-col sidebar-panel"
        style={{
          top: 44,
          bottom: 0,
          width: 200,
          background: 'var(--card)',
          borderRight: '1px solid var(--border)',
          transform: acik ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 0.25s ease',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '7px 12px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <span className="scada-label" style={{ color: 'var(--t2)' }}>Seralar</span>
          <span style={{
            fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
            color: 'var(--accent)', background: 'var(--accent-dim)',
            padding: '1px 7px', borderRadius: 4,
          }}>
            {seralar.length}
          </span>
        </div>

        {/* Sera listesi */}
        <div className="flex-1 overflow-y-auto">
          {seralar.map(sera => (
            <SeraItem key={sera.id} sera={sera} />
          ))}
          {seralar.length === 0 && (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)', fontSize: 12 }}>
              Bağlantı bekleniyor…
            </div>
          )}
        </div>

        {/* Durum footer */}
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span className="rounded-full" style={{
              width: 6, height: 6, display: 'inline-block',
              background: hata ? 'var(--alarm)' : 'var(--accent)',
              boxShadow: hata ? '0 0 5px var(--alarm)' : '0 0 5px var(--accent)',
            }} />
            <span style={{ fontSize: 11, color: 'var(--t3)', fontFamily: 'monospace' }}>
              {hata ? 'Bağlantı hatası' : 'Sistem çalışıyor'}
            </span>
          </div>
        </div>
      </aside>
    </>
  )
}

// ─── Utility helpers (used across pages) ─────────────────────────────────────

export function durumRengi(durum: Durum): string {
  switch (durum) {
    case 'NORMAL':      return 'var(--accent)'
    case 'UYARI':       return 'var(--warn)'
    case 'ALARM':       return 'var(--alarm)'
    case 'ACIL_DURDUR': return 'var(--crit)'
    default:            return 'var(--t3)'
  }
}

export function durumBadgeClass(durum: Durum): string {
  switch (durum) {
    case 'NORMAL':      return 'badge-normal'
    case 'UYARI':       return 'badge-uyari'
    case 'ALARM':       return 'badge-alarm'
    case 'ACIL_DURDUR': return 'badge-acil'
    default:            return 'badge-bilinmiyor'
  }
}

export function durumLabel(durum: Durum): string {
  switch (durum) {
    case 'NORMAL':      return 'Normal'
    case 'UYARI':       return 'Uyarı'
    case 'ALARM':       return 'Alarm'
    case 'ACIL_DURDUR': return 'Acil Dur!'
    case 'BAKIM':       return 'Bakım'
    default:            return '?'
  }
}
