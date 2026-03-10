import { useEffect, useRef, useState } from 'react'
import type { SeraDetay, SensorGecmis, KomutAdi } from '../types'
import { StatusBadge } from './StatusBadge'
import { SensorChart } from './SensorChart'
import { KomutPanel } from './KomutPanel'
import { api } from '../api'

interface Props {
  seraId: string
  onKapat: () => void
}

const MAX_GECMIS = 60

export function SeraModal({ seraId, onKapat }: Props) {
  const [detay, setDetay] = useState<SeraDetay | null>(null)
  const [gecmis, setGecmis] = useState<SensorGecmis[]>([])
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let aktif = true

    async function yukle() {
      try {
        const d = await api.seraDetay(seraId)
        if (!aktif) return
        setDetay(d)
        if (d.sensor) {
          setGecmis(prev => {
            const yeni: SensorGecmis = {
              zaman: d.sensor!.zaman,
              T: d.sensor!.T,
              H: d.sensor!.H,
              co2: d.sensor!.co2,
            }
            const son = prev[prev.length - 1]
            if (son && son.zaman === yeni.zaman) return prev
            return [...prev.slice(-MAX_GECMIS + 1), yeni]
          })
        }
      } catch { /* sessiz */ }
    }

    yukle()
    const id = setInterval(yukle, 2000)
    return () => { aktif = false; clearInterval(id) }
  }, [seraId])

  // ESC ile kapat
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onKapat() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onKapat])

  async function komutGonder(komut: KomutAdi) {
    await api.komutGonder(seraId, komut)
  }

  const profil = detay?.profil
  const optT = profil?.opt_T ?? profil?.optT
  const optCO2 = profil?.opt_CO2 ?? 1000

  return (
    <div
      ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onKapat() }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <div>
            <h2 className="text-xl font-bold text-slate-100">
              {detay ? `${detay.isim} — ${detay.bitki}` : 'Yükleniyor…'}
            </h2>
            {detay && (
              <p className="text-sm text-slate-400">{detay.alan} m²</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {detay && <StatusBadge durum={detay.durum} size="lg" />}
            <button
              onClick={onKapat}
              className="text-slate-400 hover:text-slate-100 transition-colors text-xl leading-none"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Grafikler */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Anlık Grafikler</h3>
            {gecmis.length < 2 ? (
              <div className="text-center py-8 text-slate-500 text-sm">Veri toplanıyor…</div>
            ) : (
              <>
                <SensorChart data={gecmis} field="T"   label="Sıcaklık" unit="°C"   color="#f97316" optLine={optT} />
                <SensorChart data={gecmis} field="H"   label="Nem"      unit="%"    color="#3b82f6" />
                <SensorChart data={gecmis} field="co2" label="CO₂"      unit=" ppm" color="#a855f7" optLine={optCO2} />
              </>
            )}
          </div>

          {/* Komutlar + Profil */}
          <div className="space-y-5">
            <KomutPanel seraId={seraId} onKomut={komutGonder} />

            {profil && (
              <div>
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-2">Bitki Profili</h3>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    ['Min T', `${profil.min_T ?? profil.minT}°C`],
                    ['Maks T', `${profil.max_T ?? profil.maxT}°C`],
                    ['Opt T', `${profil.opt_T ?? profil.optT ?? '—'}°C`],
                    ['Min H', `${profil.min_H ?? profil.minH}%`],
                    ['Maks H', `${profil.max_H ?? profil.maxH}%`],
                    ['Opt CO₂', `${profil.opt_CO2 ?? '—'} ppm`],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-slate-800/60 rounded-lg p-2 text-center">
                      <p className="text-xs text-slate-500">{k}</p>
                      <p className="text-sm font-semibold text-slate-200">{v}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detay?.cb && (
              <div className="bg-slate-800/60 rounded-lg p-3">
                <p className="text-xs text-slate-400 mb-1">Circuit Breaker</p>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-300">{detay.cb.durum}</span>
                  <span className="text-slate-400">{detay.cb.hata_sayisi} hata</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
