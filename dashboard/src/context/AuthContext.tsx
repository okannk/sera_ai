import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface AuthCtx {
  kullanici_adi: string
  isAuthenticated: boolean
  login: (adi: string, sifre: string) => Promise<void>
  logout: () => void
}

function tokenVar(): boolean {
  return !!localStorage.getItem('access_token')
}

function tokendenKullaniciAdi(): string {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return ''
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.adi || payload.kullanici_adi || payload.username || payload.sub || 'admin'
  } catch {
    return ''
  }
}

const AuthContext = createContext<AuthCtx>({
  kullanici_adi: '',
  isAuthenticated: false,
  login: async () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [kullanici_adi, setKullaniciAdi] = useState(tokendenKullaniciAdi)
  const [isAuthenticated, setIsAuthenticated] = useState(tokenVar)

  useEffect(() => {
    function guncelle() {
      setKullaniciAdi(tokendenKullaniciAdi())
      setIsAuthenticated(tokenVar())
    }
    window.addEventListener('auth:token-updated', guncelle)
    return () => window.removeEventListener('auth:token-updated', guncelle)
  }, [])

  async function login(adi: string, sifre: string) {
    const r = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kullanici_adi: adi, sifre }),
    })
    const json = await r.json()
    const token = json.access_token ?? json.data?.access_token
    if (!token) throw new Error(json.detail ?? json.hata ?? 'Giriş başarısız')
    localStorage.setItem('access_token', token)
    const refresh = json.refresh_token ?? json.data?.refresh_token
    if (refresh) localStorage.setItem('refresh_token', refresh)
    setKullaniciAdi(tokendenKullaniciAdi())
    setIsAuthenticated(true)
    window.dispatchEvent(new Event('auth:token-updated'))
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setKullaniciAdi('')
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ kullanici_adi, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
