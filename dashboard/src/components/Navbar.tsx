import { useState, useEffect } from 'react'
import type { Sayfa } from './Sidebar'

const TABS: { id: Sayfa; label: string; alarmBadge?: boolean }[] = [
  { id: 'genel',     label: 'Genel Bakış' },
  { id: 'grafikler', label: 'Grafikler' },
  { id: 'alarm',     label: 'Alarm Merkezi', alarmBadge: true },
  { id: 'ekonomi',   label: 'Ekonomi' },
  { id: 'loglar',    label: 'Log & Komutlar' },
  { id: 'ayarlar',   label: 'Ayarlar' },
]

interface Props {
  aktif: Sayfa
  onChange: (s: Sayfa) => void
  alarmSayisi: number
  hata: boolean
  onHamburger: () => void
}

function tokenKullaniciAdi(): string {
  try {
    const token = localStorage.getItem('access_token') ?? ''
    if (!token) return ''
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.kullanici_adi || payload.adi || payload.sub || ''
  } catch { return '' }
}

export function Navbar({ aktif, onChange, alarmSayisi, hata, onHamburger }: Props) {
  const [saat, setSaat] = useState(new Date())
  const [kullaniciAdi, setKullaniciAdi] = useState(tokenKullaniciAdi)

  useEffect(() => {
    const t = setInterval(() => setSaat(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    function guncelle() { setKullaniciAdi(tokenKullaniciAdi()) }
    window.addEventListener('auth:token-updated', guncelle)
    return () => window.removeEventListener('auth:token-updated', guncelle)
  }, [])

  return (
    <header style={{
      height: 44,
      background: 'var(--card)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'stretch',
      flexShrink: 0,
    }}>
      {/* Logo — matches sidebar width on desktop */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 14px', borderRight: '1px solid var(--border)',
        flexShrink: 0, width: 200,
      }}>
        {/* Mobile hamburger */}
        <button
          className="lg:hidden"
          onClick={onHamburger}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--t2)', fontSize: 16, padding: '0 6px 0 0' }}
        >
          ☰
        </button>
        <svg width="22" height="22" viewBox="0 0 26 26" fill="none" style={{ flexShrink: 0 }}>
          <polygon points="13,2 23,7.5 23,18.5 13,24 3,18.5 3,7.5"
            stroke="var(--accent)" strokeWidth="1.5" fill="rgba(0,212,170,0.08)" />
          <text x="13" y="17" textAnchor="middle" style={{ fontFamily: 'monospace', fontSize: '8px', fill: 'var(--accent)', fontWeight: 'bold' }}>AI</text>
        </svg>
        <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent)', fontFamily: 'monospace', letterSpacing: '0.06em' }}>
          SERA.AI
        </span>
      </div>

      {/* Tabs */}
      <nav style={{ display: 'flex', alignItems: 'stretch', flex: 1, overflow: 'hidden' }}>
        {TABS.map(tab => {
          const isActive = aktif === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                color: isActive ? 'var(--accent)' : 'var(--t2)',
                padding: '0 14px',
                paddingBottom: 2,
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                fontFamily: isActive ? "'JetBrains Mono', 'Consolas', monospace" : 'inherit',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'color 0.15s, border-color 0.15s',
                flexShrink: 0,
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = 'var(--t1)' }}
              onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = 'var(--t2)' }}
            >
              {tab.label}
              {tab.alarmBadge && alarmSayisi > 0 && (
                <span style={{
                  background: 'var(--alarm)', color: '#fff',
                  borderRadius: 10, minWidth: 16, height: 16,
                  fontSize: 10, fontWeight: 700,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  padding: '0 4px',
                }}>
                  {alarmSayisi}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Right: username + connection dot + clock */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 16px', borderLeft: '1px solid var(--border)',
        fontSize: 11, color: 'var(--t3)', fontFamily: 'monospace',
        flexShrink: 0,
      }}>
        {kullaniciAdi && (
          <span style={{ color: 'var(--t2)', fontWeight: 600 }}>
            {kullaniciAdi}
          </span>
        )}
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
          background: hata ? 'var(--alarm)' : 'var(--accent)',
          boxShadow: hata ? '0 0 6px var(--alarm)' : '0 0 6px var(--accent)',
          display: 'inline-block',
        }} />
        <span>{saat.toLocaleTimeString('tr-TR')}</span>
      </div>
    </header>
  )
}
