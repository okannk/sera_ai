import { useState, FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'

export function Login() {
  const { login }               = useAuth()
  const [adi, setAdi]           = useState('')
  const [sifre, setSifre]       = useState('')
  const [yukleniyor, setYuk]    = useState(false)
  const [hata, setHata]         = useState<string | null>(null)

  async function gonder(e: FormEvent) {
    e.preventDefault()
    setYuk(true)
    setHata(null)
    try {
      await login(adi, sifre)
    } catch (err: unknown) {
      setHata(err instanceof Error ? err.message : 'Giriş başarısız')
    } finally {
      setYuk(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ width: '100%', maxWidth: 360, padding: '0 16px' }}>

        {/* Logo / Başlık */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🌿</div>
          <div style={{
            fontSize: 18, fontWeight: 700, color: 'var(--t1)',
            fontFamily: 'var(--mono)', letterSpacing: '3px',
          }}>
            SERA AI
          </div>
          <div className="lbl" style={{ marginTop: 4 }}>
            Endüstriyel Kontrol Sistemi
          </div>
        </div>

        {/* Kart */}
        <div className="card" style={{ padding: '28px 24px' }}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: 'var(--t2)',
            fontFamily: 'var(--mono)', letterSpacing: '2px', marginBottom: 20,
          }}>
            SİSTEM GİRİŞİ
          </div>

          <form onSubmit={gonder} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label className="lbl" style={{ display: 'block', marginBottom: 5 }}>
                KULLANICI ADI
              </label>
              <input
                type="text"
                value={adi}
                onChange={e => setAdi(e.target.value)}
                required
                autoFocus
                autoComplete="username"
                placeholder="admin"
                style={{
                  width: '100%', padding: '8px 10px',
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 4, color: 'var(--t1)',
                  fontFamily: 'var(--mono)', fontSize: 13,
                  outline: 'none', boxSizing: 'border-box',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                onBlur={e => e.target.style.borderColor  = 'var(--border)'}
              />
            </div>

            <div>
              <label className="lbl" style={{ display: 'block', marginBottom: 5 }}>
                ŞİFRE
              </label>
              <input
                type="password"
                value={sifre}
                onChange={e => setSifre(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                style={{
                  width: '100%', padding: '8px 10px',
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 4, color: 'var(--t1)',
                  fontFamily: 'var(--mono)', fontSize: 13,
                  outline: 'none', boxSizing: 'border-box',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                onBlur={e => e.target.style.borderColor  = 'var(--border)'}
              />
            </div>

            {hata && (
              <div style={{
                padding: '8px 10px', borderRadius: 4,
                background: 'rgba(239,68,68,.1)',
                color: 'var(--alarm)', fontSize: 11,
              }}>
                ⚠ {hata}
              </div>
            )}

            <button
              type="submit"
              disabled={yukleniyor}
              style={{
                marginTop: 4, padding: '10px',
                background: yukleniyor ? 'var(--border)' : 'var(--accent)',
                color: '#000', border: 'none', borderRadius: 4,
                fontFamily: 'var(--mono)', fontWeight: 700,
                fontSize: 12, letterSpacing: '1px', cursor: 'pointer',
                opacity: yukleniyor ? 0.6 : 1,
              }}
            >
              {yukleniyor ? 'GİRİŞ YAPILIYOR…' : 'GİRİŞ YAP'}
            </button>
          </form>
        </div>

        <div className="lbl" style={{ textAlign: 'center', marginTop: 16 }}>
          Varsayılan: admin / sera2024!
        </div>
      </div>
    </div>
  )
}
