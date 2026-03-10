import type { Durum } from '../types'

export type Sayfa =
  | 'genel' | 'grafikler' | 'alarm'
  | 'ekonomi' | 'loglar' | 'ayarlar'

interface NavItem {
  id: Sayfa
  label: string
  icon: string
  alarmBadge?: boolean
}

const NAV: NavItem[] = [
  { id: 'genel',     label: 'Genel Bakış',   icon: '🗺' },
  { id: 'grafikler', label: 'Grafikler',      icon: '📊' },
  { id: 'alarm',     label: 'Alarm Merkezi', icon: '🚨', alarmBadge: true },
  { id: 'ekonomi',   label: 'Ekonomi',       icon: '💰' },
  { id: 'loglar',    label: 'Log & Komutlar', icon: '📋' },
  { id: 'ayarlar',   label: 'Ayarlar',        icon: '⚙️' },
]

interface Props {
  aktif: Sayfa
  onChange: (s: Sayfa) => void
  alarmSayisi: number
  hata: boolean
  acik: boolean
  onKapat: () => void
}

export function Sidebar({ aktif, onChange, alarmSayisi, hata, acik, onKapat }: Props) {
  function sec(s: Sayfa) { onChange(s); onKapat() }

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
        className="fixed top-0 left-0 h-full z-40 flex flex-col sidebar-panel"
        style={{
          width: 220,
          background: 'var(--card)',
          borderRight: '1px solid var(--border)',
          transform: acik ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 0.25s ease',
        }}
      >
        {/* Logo */}
        <div
          className="flex items-center gap-3 px-5"
          style={{
            height: 60, borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 22 }}>🌿</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--t1)' }}>Sera AI</div>
            <div style={{ fontSize: 11, color: 'var(--t3)' }}>v1.0 · FastAPI</div>
          </div>
          {/* Mobile close */}
          <button
            onClick={onKapat}
            className="ml-auto lg:hidden"
            style={{ color: 'var(--t3)', fontSize: 18, background: 'none', border: 'none', cursor: 'pointer' }}
          >✕</button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3">
          {NAV.map(item => {
            const isActive = aktif === item.id
            return (
              <button
                key={item.id}
                onClick={() => sec(item.id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left relative"
                style={{
                  background:  isActive ? 'var(--accent-dim)' : 'transparent',
                  color:       isActive ? 'var(--accent)'     : 'var(--t2)',
                  borderLeft:  isActive ? '3px solid var(--accent)' : '3px solid transparent',
                  fontSize:    14,
                  fontWeight:  isActive ? 600 : 400,
                  transition:  'all 0.15s',
                  cursor:      'pointer',
                  border:      'none',
                  width:       '100%',
                }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)' }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                <span style={{ fontSize: 17, width: 24, textAlign: 'center' }}>{item.icon}</span>
                <span>{item.label}</span>
                {item.alarmBadge && alarmSayisi > 0 && (
                  <span
                    className="ml-auto rounded-full text-xs font-bold flex items-center justify-center"
                    style={{
                      background: 'var(--alarm)', color: '#fff',
                      minWidth: 20, height: 20, padding: '0 5px', fontSize: 11,
                    }}
                  >
                    {alarmSayisi}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Alt bilgi */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div className="flex items-center gap-2">
            <span
              className="rounded-full"
              style={{
                width: 7, height: 7,
                background: hata ? 'var(--alarm)' : 'var(--accent)',
                boxShadow: hata ? '0 0 6px var(--alarm)' : '0 0 6px var(--accent)',
              }}
            />
            <span style={{ fontSize: 12, color: 'var(--t3)' }}>
              {hata ? 'Bağlantı hatası' : 'Sistem çalışıyor'}
            </span>
          </div>
        </div>
      </aside>
    </>
  )
}

// Durum renk yardımcısı — tüm sayfalarda kullanılır
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
