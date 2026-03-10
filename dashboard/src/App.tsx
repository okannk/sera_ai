import { useState } from 'react'
import { DataProvider, useData } from './context/DataContext'
import { Sidebar, type Sayfa } from './components/Sidebar'
import { GenelBakis }    from './pages/GenelBakis'
import { Grafikler }     from './pages/Grafikler'
import { AlarmMerkezi }  from './pages/AlarmMerkezi'
import { Ekonomi }       from './pages/Ekonomi'
import { LogKomutlar }   from './pages/LogKomutlar'
import { Ayarlar }       from './pages/Ayarlar'

function Layout() {
  const [sayfa, setSayfa]           = useState<Sayfa>('genel')
  const [sidebarAcik, setSidebarAcik] = useState(false)
  const { saglik, hata, sonGuncelleme } = useData()

  const alarmSayisi = saglik?.alarm_sayisi ?? 0

  const SAYFALAR: Record<Sayfa, React.ReactNode> = {
    genel:     <GenelBakis />,
    grafikler: <Grafikler />,
    alarm:     <AlarmMerkezi />,
    ekonomi:   <Ekonomi />,
    loglar:    <LogKomutlar />,
    ayarlar:   <Ayarlar />,
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Desktop: sidebar always visible via CSS */}
      <div className="hidden lg:block" style={{ width: 220, flexShrink: 0 }} />

      <Sidebar
        aktif={sayfa}
        onChange={setSayfa}
        alarmSayisi={alarmSayisi}
        hata={!!hata}
        acik={sidebarAcik}
        onKapat={() => setSidebarAcik(false)}
      />

      {/* Ana içerik */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header
          className="flex items-center gap-3 px-4 flex-shrink-0"
          style={{
            height: 60,
            background: 'var(--card)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {/* Hamburger (mobile) */}
          <button
            className="lg:hidden"
            onClick={() => setSidebarAcik(true)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--t2)', fontSize: 20, padding: 4,
            }}
          >
            ☰
          </button>

          <div style={{ color: 'var(--t2)', fontSize: 13 }}>
            {alarmSayisi > 0 && (
              <span
                className="rounded-full font-bold"
                style={{
                  background: 'var(--alarm-dim)', color: 'var(--alarm)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  padding: '2px 10px', marginRight: 12, fontSize: 12,
                  animation: 'pulse 2s infinite',
                }}
              >
                🚨 {alarmSayisi} aktif alarm
              </span>
            )}
          </div>

          <div className="ml-auto flex items-center gap-4" style={{ fontSize: 12, color: 'var(--t3)' }}>
            {saglik && (
              <>
                <span>⏱ {saglik.uptime_fmt}</span>
                <span style={{ color: 'var(--border-lt)' }}>|</span>
                <span>{saglik.seralar ? Object.keys(saglik.seralar).length : 0} sera</span>
              </>
            )}
            {sonGuncelleme && (
              <>
                <span style={{ color: 'var(--border-lt)' }}>|</span>
                <span className="flex items-center gap-1">
                  <span
                    className="rounded-full"
                    style={{
                      width: 6, height: 6, display: 'inline-block',
                      background: hata ? 'var(--alarm)' : 'var(--accent)',
                    }}
                  />
                  {sonGuncelleme.toLocaleTimeString('tr-TR')}
                </span>
              </>
            )}
          </div>
        </header>

        {/* Sayfa içeriği */}
        <main className="flex-1 overflow-y-auto" style={{ padding: 24 }}>
          {hata && (
            <div
              className="rounded-xl flex items-start gap-3 mb-5"
              style={{
                background: 'var(--alarm-dim)', border: '1px solid rgba(239,68,68,0.3)',
                padding: '12px 16px',
              }}
            >
              <span style={{ fontSize: 18 }}>⚠️</span>
              <div>
                <div style={{ color: 'var(--alarm)', fontWeight: 600, fontSize: 13 }}>API Bağlantı Hatası</div>
                <div style={{ color: 'rgba(239,68,68,0.7)', fontSize: 12 }}>{hata}</div>
                <div style={{ color: 'var(--t3)', fontSize: 11, marginTop: 2 }}>
                  Backend: <code style={{ color: 'var(--t2)' }}>python -m sera_ai --demo --api</code>
                </div>
              </div>
            </div>
          )}
          {SAYFALAR[sayfa]}
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <DataProvider>
      <Layout />
    </DataProvider>
  )
}
