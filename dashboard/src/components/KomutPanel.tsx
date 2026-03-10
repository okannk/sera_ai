import { useState } from 'react'
import type { KomutAdi } from '../types'

interface Props {
  seraId: string
  onKomut: (komut: KomutAdi) => Promise<void>
}

const KOMUTLAR: { grup: string; icon: string; ac: KomutAdi; kapat: KomutAdi }[] = [
  { grup: 'Sulama',   icon: '💧', ac: 'SULAMA_AC',   kapat: 'SULAMA_KAPAT' },
  { grup: 'Isıtıcı',  icon: '🔥', ac: 'ISITICI_AC',  kapat: 'ISITICI_KAPAT' },
  { grup: 'Soğutma',  icon: '❄️', ac: 'SOGUTMA_AC',  kapat: 'SOGUTMA_KAPAT' },
  { grup: 'Fan',      icon: '🌀', ac: 'FAN_AC',      kapat: 'FAN_KAPAT' },
  { grup: 'Işık',     icon: '💡', ac: 'ISIK_AC',     kapat: 'ISIK_KAPAT' },
]

export function KomutPanel({ seraId: _seraId, onKomut }: Props) {
  const [yuklenen, setYuklenen] = useState<string | null>(null)
  const [sonuc, setSonuc] = useState<{ komut: string; ok: boolean } | null>(null)

  async function gonder(komut: KomutAdi) {
    setYuklenen(komut)
    setSonuc(null)
    try {
      await onKomut(komut)
      setSonuc({ komut, ok: true })
    } catch {
      setSonuc({ komut, ok: false })
    } finally {
      setYuklenen(null)
      setTimeout(() => setSonuc(null), 2500)
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Manuel Komut</h3>

      <div className="grid grid-cols-1 gap-2">
        {KOMUTLAR.map(({ grup, icon, ac, kapat }) => (
          <div key={grup} className="flex items-center gap-2 bg-slate-800/60 rounded-lg px-3 py-2">
            <span className="text-base w-6">{icon}</span>
            <span className="text-sm text-slate-300 flex-1">{grup}</span>
            <button
              onClick={() => gonder(ac)}
              disabled={yuklenen !== null}
              className="px-3 py-1 text-xs rounded-md bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/40 disabled:opacity-40 transition-colors"
            >
              {yuklenen === ac ? '…' : 'Aç'}
            </button>
            <button
              onClick={() => gonder(kapat)}
              disabled={yuklenen !== null}
              className="px-3 py-1 text-xs rounded-md bg-slate-600/20 text-slate-400 border border-slate-600/30 hover:bg-slate-600/40 disabled:opacity-40 transition-colors"
            >
              {yuklenen === kapat ? '…' : 'Kapat'}
            </button>
          </div>
        ))}
      </div>

      {/* Acil durdur */}
      <button
        onClick={() => gonder('ACIL_DURDUR')}
        disabled={yuklenen !== null}
        className="w-full mt-2 py-2.5 rounded-lg bg-red-600/20 text-red-400 border border-red-600/40 hover:bg-red-600/30 disabled:opacity-40 font-bold text-sm transition-colors"
      >
        🚨 ACİL DURDUR
      </button>

      {sonuc && (
        <div className={`text-xs text-center py-1.5 rounded-lg ${sonuc.ok ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
          {sonuc.ok ? `✓ ${sonuc.komut} gönderildi` : `✗ ${sonuc.komut} başarısız`}
        </div>
      )}
    </div>
  )
}
