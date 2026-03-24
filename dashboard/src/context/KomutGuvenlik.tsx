import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

interface KomutGuvenlikCtx {
  kilitli: boolean
  modalAcik: boolean
  setModalAcik: (v: boolean) => void
  aktifKullanici: string | null
  kilitle: () => void
  komutOnayIste: (fn: () => void) => void
  timerSifirla: () => void
}

const KomutGuvenlikContext = createContext<KomutGuvenlikCtx | null>(null)

export function KomutGuvenlikProvider({ children }: { children: ReactNode }) {
  const [kilitli, setKilitli]               = useState(() => localStorage.getItem('sera_kilitli') !== 'false')
  const [modalAcik, setModalAcik]           = useState(false)
  const [sifre, setSifre]                   = useState('')
  const [hata, setHata]                     = useState('')
  const [aktifKullanici, setAktifKullanici] = useState<string | null>(() => localStorage.getItem('sera_kullanici'))
  const [bekleyenFn, setBekleyenFn]         = useState<(() => void) | null>(null)

  const kilitle = useCallback(() => {
    localStorage.setItem('sera_kilitli', 'true')
    localStorage.removeItem('sera_kullanici')
    setKilitli(true)
    setAktifKullanici(null)
    window.dispatchEvent(new CustomEvent('sera-kilit-aktif'))
  }, [])

  const komutOnayIste = useCallback((fn: () => void) => {
    if (!kilitli) { fn(); return }
    setBekleyenFn(() => fn)
    setSifre('')
    setHata('')
    setModalAcik(true)
  }, [kilitli])

  const sifreOnayla = async () => {
    if (!sifre) { setHata('Şifre girin'); return }
    try {
      const res = await fetch('/api/v1/auth/sifre-dogrula', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sifre }),
      })
      if (res.ok) {
        const d = await res.json()
        const token = d.access_token ?? d.data?.access_token
        if (token) {
          localStorage.setItem('access_token', token)
          window.dispatchEvent(new Event('auth:token-updated'))
        }
        if (d.refresh_token) localStorage.setItem('refresh_token', d.refresh_token)
        const kullanici = d.kullanici_adi ?? null
        setAktifKullanici(kullanici)
        if (kullanici) localStorage.setItem('sera_kullanici', kullanici)
        localStorage.setItem('sera_kilitli', 'false')
        setKilitli(false)
        setModalAcik(false)
        setSifre('')
        setHata('')
        const fn = bekleyenFn
        setBekleyenFn(null)
        fn?.()
      } else {
        setHata('Şifre hatalı')
        setSifre('')
      }
    } catch {
      setHata('Bağlantı hatası')
    }
  }

  return (
    <KomutGuvenlikContext.Provider value={{
      kilitli,
      modalAcik, setModalAcik,
      aktifKullanici,
      kilitle, komutOnayIste,
      timerSifirla: () => {},
    }}>
      {children}

      {modalAcik && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: '#0d1826', border: '1px solid #1a2535',
            borderRadius: 8, padding: 24, width: 340,
          }}>
            <div style={{ fontSize: 13, color: '#dce8f5', marginBottom: 16 }}>
              🔒 KOMUT ONAYI
            </div>
            <div style={{ fontSize: 11, color: '#5a7a96', marginBottom: 12 }}>
              KOMUT KİLİDİ AKTİF. DEVAM ETMEK İÇİN ŞİFRENİZİ GİRİN.
            </div>

            <input
              type="password"
              value={sifre}
              onChange={e => setSifre(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') sifreOnayla() }}
              placeholder="Şifre"
              autoFocus
              style={{
                width: '100%', background: '#091018', border: '1px solid #1a2535',
                borderRadius: 4, padding: '8px 12px', color: '#dce8f5',
                fontFamily: 'monospace', fontSize: 14, marginBottom: 8,
                outline: 'none', boxSizing: 'border-box',
              }}
            />

            {hata && (
              <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>
                ⚠ {hata}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={sifreOnayla}
                style={{
                  flex: 1, padding: '8px', background: '#00d4aa',
                  border: 'none', borderRadius: 4, color: '#070c14',
                  fontWeight: 700, fontSize: 12, cursor: 'pointer',
                  fontFamily: 'monospace', letterSpacing: 1,
                }}
              >
                ONAYLA
              </button>
              <button
                type="button"
                onClick={() => { setModalAcik(false); setSifre(''); setHata('') }}
                style={{
                  padding: '8px 16px', background: 'transparent',
                  border: '1px solid #1a2535', borderRadius: 4,
                  color: '#5a7a96', fontSize: 12, cursor: 'pointer',
                  fontFamily: 'monospace',
                }}
              >
                İPTAL
              </button>
            </div>
          </div>
        </div>
      )}
    </KomutGuvenlikContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useKomutGuvenlik() {
  const ctx = useContext(KomutGuvenlikContext)
  if (!ctx) throw new Error('useKomutGuvenlik: KomutGuvenlikProvider dışında kullanıldı')
  return ctx
}
