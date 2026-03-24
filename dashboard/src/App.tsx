import { useState, useEffect, useRef } from 'react'
import { DataProvider, useData } from './context/DataContext'
import { KomutGuvenlikProvider, useKomutGuvenlik } from './context/KomutGuvenlik'
import { type Sayfa } from './components/Sidebar'
import { GenelBakis }   from './pages/GenelBakis'
import { Grafikler }    from './pages/Grafikler'
import { AlarmMerkezi } from './pages/AlarmMerkezi'
import { Sulama }       from './pages/Sulama'
import { SulamaGrup }  from './pages/SulamaGrup'
import { Ekonomi }      from './pages/Ekonomi'
import { LogKomutlar }  from './pages/LogKomutlar'
import { Ayarlar }      from './pages/Ayarlar'

const TABS: { id: Sayfa; label: string; badge?: boolean; kilitli?: boolean }[] = [
  { id: 'genel',     label: 'Genel Bakış' },
  { id: 'grafikler', label: 'Grafikler' },
  { id: 'alarm',     label: 'Alarm Merkezi', badge: true },
  { id: 'ekonomi',   label: 'Ekonomi',        kilitli: true },
  { id: 'loglar',    label: 'Log & Komutlar', kilitli: true },
  { id: 'ayarlar',   label: 'Ayarlar',        kilitli: true },
]

const KİLİTLİ_SAYFALAR: Sayfa[] = ['sulama', 'sulama_grup', 'ekonomi', 'loglar', 'ayarlar']

// ─── NavTab — tekrar eden sekme butonu ───────────────────────────────────────

function NavTab({ tab, aktif, kilitli, alarmSayisi, onSec }: {
  tab: typeof TABS[number]
  aktif: Sayfa
  kilitli: boolean
  alarmSayisi: number
  onSec: (id: Sayfa) => void
}) {
  const isActive  = aktif === tab.id
  const isKilitli = !!tab.kilitli && kilitli
  return (
    <button
      onClick={() => onSec(tab.id)}
      style={{
        background: 'none', border: 'none',
        borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
        color: isActive ? 'var(--accent)' : 'var(--t1)',
        padding: '0 12px', paddingBottom: 2,
        fontSize: 13, fontWeight: isActive ? 700 : 500,
        fontFamily: 'var(--mono)', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 5,
        transition: 'color 0.12s, border-color 0.12s',
        flexShrink: 0, whiteSpace: 'nowrap',
        letterSpacing: isActive ? '0.5px' : '0',
      }}
      onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)' }}
      onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = 'var(--t1)' }}
    >
      {tab.label}
      {isKilitli && <span style={{ fontSize: 9, opacity: 0.6, lineHeight: 1 }}>🔒</span>}
      {tab.badge && alarmSayisi > 0 && (
        <span style={{
          background: 'var(--alarm)', color: '#fff', borderRadius: 10,
          minWidth: 16, height: 16, fontSize: 10, fontWeight: 700,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0 4px',
        }}>
          {alarmSayisi}
        </span>
      )}
    </button>
  )
}

// ─── NavBar ──────────────────────────────────────────────────────────────────

function NavBar({ aktif, onChange, alarmSayisi, hata }: {
  aktif: Sayfa
  onChange: (s: Sayfa) => void
  alarmSayisi: number
  hata: boolean
}) {
  const [saat, setSaat] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setSaat(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  const { kilitli, kilitle, komutOnayIste, aktifKullanici } = useKomutGuvenlik()
  const [sulamaAcik, setSulamaAcik] = useState(false)
  const sulamaRef = useRef<HTMLDivElement>(null)

  // Dışarı tıklayınca dropdown kapansın
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (sulamaRef.current && !sulamaRef.current.contains(e.target as Node)) {
        setSulamaAcik(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  function handleSekme(id: Sayfa) {
    setSulamaAcik(false)
    if (KİLİTLİ_SAYFALAR.includes(id) && kilitli) {
      komutOnayIste(() => onChange(id))
      return
    }
    onChange(id)
  }
  return (
    <header style={{
      height: 44, background: 'var(--card)', borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'stretch', flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 14px', borderRight: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <svg width="20" height="20" viewBox="0 0 26 26" fill="none" style={{ flexShrink: 0 }}>
          <polygon points="13,2 23,7.5 23,18.5 13,24 3,18.5 3,7.5"
            stroke="var(--accent)" strokeWidth="1.5" fill="var(--accent-dim)" />
          <text x="13" y="17" textAnchor="middle"
            style={{ fontFamily: 'var(--mono)', fontSize: '7px', fill: 'var(--accent)', fontWeight: '700' }}>
            AI
          </text>
        </svg>
        <span style={{
          fontSize: 13, fontWeight: 700, color: 'var(--accent)',
          fontFamily: 'var(--mono)', letterSpacing: '0.07em',
        }}>SERA.AI</span>
      </div>

      {/* Sekmeler */}
      <nav style={{ display: 'flex', alignItems: 'stretch', flex: 1, overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none' }}>

        {/* Sulama dropdown — Alarm'dan sonra, Ekonomi'den önce */}
        {TABS.slice(0, 3).map(tab => <NavTab key={tab.id} tab={tab} aktif={aktif} kilitli={kilitli} alarmSayisi={alarmSayisi} onSec={handleSekme} />)}

        <div ref={sulamaRef} style={{ display: 'flex', alignItems: 'stretch' }}>
          <button
            onClick={() => setSulamaAcik(v => !v)}
            style={{
              background: 'none', border: 'none',
              borderBottom: (aktif === 'sulama' || aktif === 'sulama_grup')
                ? '2px solid var(--accent)' : '2px solid transparent',
              color: (aktif === 'sulama' || aktif === 'sulama_grup') ? 'var(--accent)' : 'var(--t1)',
              padding: '0 12px', paddingBottom: 2,
              fontSize: 13, fontWeight: (aktif === 'sulama' || aktif === 'sulama_grup') ? 700 : 500,
              fontFamily: 'var(--mono)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 4,
              flexShrink: 0, whiteSpace: 'nowrap',
              transition: 'color 0.12s, border-color 0.12s',
            }}
          >
            Sulama
            {kilitli && <span style={{ fontSize: 9, opacity: 0.6 }}>🔒</span>}
            <span style={{ fontSize: 9, opacity: 0.5, marginLeft: 1 }}>{sulamaAcik ? '▲' : '▼'}</span>
          </button>

          {sulamaAcik && (
            <div style={{
              position: 'fixed', top: 44, zIndex: 9000,
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 6, minWidth: 170, boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              overflow: 'hidden',
            }}>
              {([
                { id: 'sulama'      as Sayfa, label: '💧 Sulama Sistemi' },
                { id: 'sulama_grup' as Sayfa, label: '📋 Sulama Grupları' },
              ] as const).map(item => (
                <button
                  key={item.id}
                  onClick={() => handleSekme(item.id)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '9px 14px', background: aktif === item.id ? 'var(--accent-dim)' : 'none',
                    border: 'none', color: aktif === item.id ? 'var(--accent)' : 'var(--t1)',
                    fontSize: 12, fontFamily: 'var(--mono)', cursor: 'pointer',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => { if (aktif !== item.id) (e.currentTarget as HTMLButtonElement).style.background = 'var(--border)' }}
                  onMouseLeave={e => { if (aktif !== item.id) (e.currentTarget as HTMLButtonElement).style.background = 'none' }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {TABS.slice(3).map(tab => <NavTab key={tab.id} tab={tab} aktif={aktif} kilitli={kilitli} alarmSayisi={alarmSayisi} onSec={handleSekme} />)}
      </nav>

      {/* Sağ: kullanıcı + kilit + durum noktası + saat */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 14px', borderLeft: '1px solid var(--border)',
        fontSize: 13, color: 'var(--t1)', fontFamily: 'var(--mono)', flexShrink: 0,
      }}>
        {kilitli ? (
          <button
            onClick={() => komutOnayIste(() => {})}
            style={{
              cursor: 'pointer',
              background: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.45)',
              borderRadius: 5, padding: '4px 12px',
              color: '#f87171',
              fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700,
              letterSpacing: '0.5px', whiteSpace: 'nowrap',
            }}
          >
            🔒 KİLİTLİ — GİRİŞ YAP
          </button>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'var(--mono)', fontWeight: 600, letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>
            🔓{aktifKullanici ? ` ${aktifKullanici}` : ''}
          </span>
        )}
        {!kilitli && (
          <button
            onClick={kilitle}
            className="btn-ghost"
            style={{ fontSize: 11, padding: '3px 9px' }}
            title="Komut kilidini etkinleştir"
          >
            🔒 Kilitle
          </button>
        )}
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0, display: 'inline-block',
          background: hata ? 'var(--alarm)' : 'var(--accent)',
          boxShadow: hata ? '0 0 6px var(--alarm)' : '0 0 6px var(--accent)',
          animation: hata ? 'pulse-glow 2s infinite' : undefined,
        }} />
        <span style={{ color: 'var(--t1)', fontWeight: 600 }}>{saat.toLocaleTimeString('tr-TR')}</span>
      </div>
    </header>
  )
}

// ─── Layout ───────────────────────────────────────────────────────────────────

function Layout() {
  const [sayfa, setSayfa] = useState<Sayfa>('genel')
  const { saglik, hata }  = useData()
  const alarmSayisi = saglik?.alarm_sayisi ?? 0
  const { kilitli, komutOnayIste } = useKomutGuvenlik()

  useEffect(() => {
    const kilit = () => setSayfa('genel')
    const goto  = (e: Event) => {
      const hedef = (e as CustomEvent<Sayfa>).detail
      if (KİLİTLİ_SAYFALAR.includes(hedef) && kilitli) {
        komutOnayIste(() => setSayfa(hedef))
      } else {
        setSayfa(hedef)
      }
    }
    window.addEventListener('sera-kilit-aktif', kilit)
    window.addEventListener('goto-sayfa', goto)
    return () => {
      window.removeEventListener('sera-kilit-aktif', kilit)
      window.removeEventListener('goto-sayfa', goto)
    }
  }, [kilitli, komutOnayIste])

  const gercekSayfa = sayfa

  const SAYFALAR: Record<Sayfa, React.ReactNode> = {
    genel:       <GenelBakis />,
    grafikler:   <Grafikler />,
    alarm:       <AlarmMerkezi />,
    sulama:      <Sulama />,
    sulama_grup: <SulamaGrup />,
    ekonomi:     <Ekonomi />,
    loglar:      <LogKomutlar />,
    ayarlar:     <Ayarlar />,
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      <NavBar
        aktif={sayfa}
        onChange={s => setSayfa(s)}
        alarmSayisi={alarmSayisi}
        hata={!!hata}
      />
      <main className="flex-1 overflow-y-auto" style={{ padding: 20 }}>
        {hata && (
          <div
            className="rounded flex items-start gap-3 mb-4"
            style={{
              background: 'var(--alarm-dim)', border: '1px solid rgba(239,68,68,0.2)',
              padding: '10px 14px',
            }}
          >
            <span>⚠️</span>
            <div>
              <div style={{ color: 'var(--alarm)', fontWeight: 600, fontSize: 12 }}>
                API Bağlantı Hatası
              </div>
              <div className="lbl" style={{ marginTop: 3 }}>
                <code style={{ color: 'var(--t2)', fontFamily: 'var(--mono)' }}>
                  python -m sera_ai --demo --api
                </code>
              </div>
            </div>
          </div>
        )}
        {SAYFALAR[gercekSayfa]}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <DataProvider>
      <KomutGuvenlikProvider>
        <Layout />
      </KomutGuvenlikProvider>
    </DataProvider>
  )
}
