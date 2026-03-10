import { useState } from 'react'
import type { KomutAdi } from '../types'

interface Props {
  seraId: string
  onKomut: (komut: KomutAdi) => Promise<void>
}

const AKTÜATÖRLER: { ad: string; icon: string; ac: KomutAdi; kapat: KomutAdi }[] = [
  { ad: 'SULAMA',  icon: '💧', ac: 'SULAMA_AC',  kapat: 'SULAMA_KAPAT' },
  { ad: 'ISITICI', icon: '🔥', ac: 'ISITICI_AC', kapat: 'ISITICI_KAPAT' },
  { ad: 'SOGUTMA', icon: '❄️', ac: 'SOGUTMA_AC', kapat: 'SOGUTMA_KAPAT' },
  { ad: 'FAN',     icon: '🌀', ac: 'FAN_AC',     kapat: 'FAN_KAPAT' },
  { ad: 'ISIK',    icon: '💡', ac: 'ISIK_AC',    kapat: 'ISIK_KAPAT' },
]

export function KomutPanel({ seraId: _seraId, onKomut }: Props) {
  const [aktifler, setAktifler] = useState<Record<string, boolean>>({
    SULAMA: false, ISITICI: false, SOGUTMA: false, FAN: false, ISIK: false,
  })
  const [yuklenen, setYuklenen] = useState<string | null>(null)
  const [sonuc, setSonuc]       = useState<{ komut: string; ok: boolean } | null>(null)

  async function toggle(ad: string, acKomut: KomutAdi, kapatKomut: KomutAdi) {
    setYuklenen(ad)
    setSonuc(null)
    const yeniDurum = !aktifler[ad]
    const komut = yeniDurum ? acKomut : kapatKomut
    try {
      await onKomut(komut)
      setAktifler(prev => ({ ...prev, [ad]: yeniDurum }))
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
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Aktüatörler</h3>

      <div className="grid grid-cols-1 gap-2">
        {AKTÜATÖRLER.map(({ ad, icon, ac, kapat }) => {
          const acik    = aktifler[ad]
          const bekliyor = yuklenen === ad
          return (
            <div key={ad} className="flex items-center gap-3 bg-slate-800/60 rounded-lg px-3 py-2.5">
              <span className="text-base w-6">{icon}</span>
              <span className="text-sm text-slate-300 flex-1">{ad.charAt(0) + ad.slice(1).toLowerCase()}</span>
              <button
                onClick={() => toggle(ad, ac, kapat)}
                disabled={yuklenen !== null}
                style={{
                  minWidth: 80, padding: '5px 14px',
                  borderRadius: 8, fontSize: 12, fontWeight: 600,
                  border: `1px solid ${acik ? 'rgba(16,185,129,0.4)' : 'rgba(71,85,105,0.4)'}`,
                  background: acik ? 'rgba(16,185,129,0.15)' : 'rgba(71,85,105,0.15)',
                  color: acik ? '#10b981' : '#64748b',
                  cursor: yuklenen !== null ? 'not-allowed' : 'pointer',
                  opacity: yuklenen !== null && !bekliyor ? 0.5 : 1,
                  transition: 'background 0.15s, color 0.15s, border-color 0.15s',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}
              >
                {bekliyor ? (
                  <span style={{ display: 'inline-block', animation: 'spin 0.8s linear infinite' }}>⟳</span>
                ) : (
                  <>
                    <span style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: acik ? '#10b981' : '#475569',
                      display: 'inline-block',
                      boxShadow: acik ? '0 0 6px #10b981' : 'none',
                    }} />
                    {acik ? 'Açık' : 'Kapalı'}
                  </>
                )}
              </button>
            </div>
          )
        })}
      </div>

      {/* Acil durdur */}
      <button
        onClick={async () => {
          setYuklenen('ACIL')
          try { await onKomut('ACIL_DURDUR'); setSonuc({ komut: 'ACIL_DURDUR', ok: true }) }
          catch { setSonuc({ komut: 'ACIL_DURDUR', ok: false }) }
          finally { setYuklenen(null); setTimeout(() => setSonuc(null), 2500) }
        }}
        disabled={yuklenen !== null}
        className="w-full mt-2 py-3 rounded-lg font-bold text-sm transition-colors"
        style={{
          background: 'rgba(239,68,68,0.15)', color: '#ef4444',
          border: '1px solid rgba(239,68,68,0.4)',
          cursor: yuklenen !== null ? 'not-allowed' : 'pointer',
          opacity: yuklenen !== null && yuklenen !== 'ACIL' ? 0.5 : 1,
          fontSize: 13,
        }}
      >
        {yuklenen === 'ACIL' ? '⟳ Gönderiliyor…' : '🚨 ACİL DURDUR'}
      </button>

      {sonuc && (
        <div className={`text-xs text-center py-1.5 rounded-lg ${sonuc.ok ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
          {sonuc.ok ? `✓ ${sonuc.komut} gönderildi` : `✗ ${sonuc.komut} başarısız`}
        </div>
      )}
    </div>
  )
}
