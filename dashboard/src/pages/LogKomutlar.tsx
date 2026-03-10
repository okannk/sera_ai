import { useState, useMemo } from 'react'
import { useData } from '../context/DataContext'
import { KaynakBadge } from '../components/KaynakBadge'
import type { KomutAdi, SistemLog, KomutKaynak } from '../types'

const KOMUT_GRUPLARI: { grup: string; icon: string; ac: KomutAdi; kapat: KomutAdi }[] = [
  { grup: 'Sulama',  icon: '💧', ac: 'SULAMA_AC',  kapat: 'SULAMA_KAPAT' },
  { grup: 'Isıtıcı', icon: '🔥', ac: 'ISITICI_AC', kapat: 'ISITICI_KAPAT' },
  { grup: 'Soğutma', icon: '❄️', ac: 'SOGUTMA_AC', kapat: 'SOGUTMA_KAPAT' },
  { grup: 'Fan',     icon: '🌀', ac: 'FAN_AC',     kapat: 'FAN_KAPAT' },
  { grup: 'Işık',    icon: '💡', ac: 'ISIK_AC',    kapat: 'ISIK_KAPAT' },
]

export function LogKomutlar() {
  const { seralar, komutLog, sistemLog, komutGonder } = useData()

  const [secilenSera, setSecilenSera] = useState<string>('')
  const [logFiltre, setLogFiltre]     = useState<'hepsi' | 'INFO' | 'WARN' | 'ERROR'>('hepsi')
  const [komutSonuc, setKomutSonuc]   = useState<string | null>(null)
  const [yuklenen, setYuklenen]       = useState<string | null>(null)

  const aktifSeraId = secilenSera || seralar[0]?.id || ''
  const aktifSera   = seralar.find(s => s.id === aktifSeraId)

  const filtreliLog = sistemLog.filter(l => logFiltre === 'hepsi' || l.seviye === logFiltre)

  // Aynı mesaj tekrar ediyorsa "×N" sayacıyla birleştir
  const sikistirilmisLog = useMemo(() => {
    return filtreliLog.reduce<(SistemLog & { tekrar: number })[]>((acc, log) => {
      const son = acc[acc.length - 1]
      if (son && son.mesaj === log.mesaj && son.seviye === log.seviye) {
        son.tekrar++
        son.zaman = log.zaman // en son zamanı tut
      } else {
        acc.push({ ...log, tekrar: 1 })
      }
      return acc
    }, [])
  }, [filtreliLog])
  const filtreliKomut = secilenSera
    ? komutLog.filter(k => k.sera_id === secilenSera)
    : komutLog

  async function gonder(komut: KomutAdi) {
    if (!aktifSeraId) return
    setYuklenen(komut)
    setKomutSonuc(null)
    const r = await komutGonder(aktifSeraId, komut, aktifSera?.isim)
    setKomutSonuc(r.mesaj)
    setYuklenen(null)
    setTimeout(() => setKomutSonuc(null), 3000)
  }

  const seviyeRenk = (s: string) =>
    s === 'ERROR' ? 'var(--alarm)' : s === 'WARN' ? 'var(--warn)' : 'var(--t3)'

  return (
    <div className="page-root">
      <div className="mb-6" style={{ flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Log & Komutlar</h1>
        <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Sistem olayları ve manuel kontrol</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Sol: Sistem logu */}
        <div className="card rounded-xl flex flex-col" style={{ maxHeight: 600 }}>
          <div
            style={{
              padding: '12px 16px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              flexShrink: 0,
            }}
          >
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
              📋 Sistem Logu
            </span>
            <div className="flex gap-1">
              {(['hepsi', 'INFO', 'WARN', 'ERROR'] as const).map(f => (
                <button
                  key={f}
                  className={`btn-ghost ${logFiltre === f ? 'active' : ''}`}
                  style={{ padding: '2px 8px', fontSize: 11 }}
                  onClick={() => setLogFiltre(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto" style={{ fontFamily: 'monospace', fontSize: 11 }}>
            {sikistirilmisLog.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)' }}>Log yok</div>
            ) : sikistirilmisLog.map(l => (
              <div
                key={l.id}
                className="table-row"
                style={{ padding: '6px 16px', display: 'flex', gap: 8, alignItems: 'baseline' }}
              >
                <span style={{ color: 'var(--t3)', flexShrink: 0, fontSize: 10 }}>
                  {new Date(l.zaman).toLocaleTimeString('tr-TR')}
                </span>
                <span
                  style={{
                    color: seviyeRenk(l.seviye), flexShrink: 0, fontWeight: 700, fontSize: 10,
                    minWidth: 38,
                  }}
                >
                  [{l.seviye}]
                </span>
                <span style={{ color: 'var(--t2)', wordBreak: 'break-word', flex: 1 }}>{l.mesaj}</span>
                {l.tekrar > 1 && (
                  <span
                    style={{
                      flexShrink: 0, fontSize: 10, fontWeight: 700,
                      background: 'var(--border)', color: 'var(--t3)',
                      borderRadius: 10, padding: '1px 6px',
                    }}
                  >
                    ×{l.tekrar}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Sağ: Komut paneli + geçmiş */}
        <div className="flex flex-col gap-4">

          {/* Manuel komut paneli */}
          <div className="card rounded-xl p-4">
            <div
              style={{
                fontWeight: 600, fontSize: 14, color: 'var(--t1)',
                marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}
            >
              <span>⚙️ Manuel Komut</span>
              <select
                className="input-field"
                value={secilenSera}
                onChange={e => setSecilenSera(e.target.value)}
                style={{ fontSize: 12 }}
              >
                {seralar.map(s => (
                  <option key={s.id} value={s.id}>{s.isim}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-2">
              {KOMUT_GRUPLARI.map(({ grup, icon, ac, kapat }) => (
                <div key={grup} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 15, width: 20, textAlign: 'center' }}>{icon}</span>
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--t2)' }}>{grup}</span>
                  <button
                    className="btn-accent"
                    style={{ padding: '4px 12px', fontSize: 12 }}
                    disabled={yuklenen !== null}
                    onClick={() => gonder(ac)}
                  >
                    {yuklenen === ac ? '…' : 'Aç'}
                  </button>
                  <button
                    className="btn-ghost"
                    style={{ padding: '4px 12px', fontSize: 12 }}
                    disabled={yuklenen !== null}
                    onClick={() => gonder(kapat)}
                  >
                    {yuklenen === kapat ? '…' : 'Kapat'}
                  </button>
                </div>
              ))}
            </div>

            <button
              className="w-full mt-3"
              style={{
                background: 'var(--alarm-dim)', color: 'var(--alarm)',
                border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8,
                padding: '8px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
                transition: 'background 0.15s',
              }}
              disabled={yuklenen !== null}
              onClick={() => gonder('ACIL_DURDUR')}
            >
              🚨 ACİL DURDUR
            </button>

            {komutSonuc && (
              <div style={{ fontSize: 12, textAlign: 'center', marginTop: 8, color: 'var(--accent)' }}>
                ✓ {komutSonuc}
              </div>
            )}
          </div>

          {/* Komut geçmişi */}
          <div className="card rounded-xl flex flex-col" style={{ flex: 1, minHeight: 200, maxHeight: 300 }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
                📝 Komut Geçmişi
                {secilenSera && <span style={{ fontSize: 11, color: 'var(--t3)', marginLeft: 6 }}>({aktifSera?.isim})</span>}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
              {filtreliKomut.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
                  Henüz komut gönderilmedi
                </div>
              ) : filtreliKomut.map(k => (
                <div key={k.id} className="table-row" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, color: k.basarili ? 'var(--accent)' : 'var(--alarm)', flexShrink: 0 }}>
                    {k.basarili ? '✓' : '✗'}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', flex: 1, minWidth: 0 }}>{k.komut}</span>
                  <KaynakBadge kaynak={(k.kaynak ?? 'kullanici') as KomutKaynak} />
                  <span style={{ fontSize: 11, color: 'var(--t3)', flexShrink: 0 }}>{k.sera_isim}</span>
                  <span style={{ fontSize: 10, color: 'var(--t3)', flexShrink: 0 }}>
                    {new Date(k.zaman).toLocaleTimeString('tr-TR')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
