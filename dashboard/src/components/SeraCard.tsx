import type { SeraOzet } from '../types'
import { StatusBadge } from './StatusBadge'
import { SensorRow } from './SensorRow'

interface Props {
  sera: SeraOzet
  onClick: () => void
}

const BITKI_EMOJI: Record<string, string> = {
  Domates: '🍅',
  Biber:   '🌶️',
  Marul:   '🥬',
}

export function SeraCard({ sera, onClick }: Props) {
  const s = sera.sensor
  const emoji = BITKI_EMOJI[sera.bitki] ?? '🌱'

  return (
    <div
      onClick={onClick}
      className="bg-slate-800 border border-slate-700 hover:border-slate-500 rounded-xl p-5 cursor-pointer transition-all hover:shadow-lg hover:shadow-slate-900/50 hover:-translate-y-0.5"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{emoji}</span>
            <div>
              <h2 className="font-bold text-slate-100 text-lg leading-tight">{sera.isim}</h2>
              <p className="text-slate-400 text-xs">{sera.bitki} · {sera.alan} m²</p>
            </div>
          </div>
        </div>
        <StatusBadge durum={sera.durum} />
      </div>

      {/* Sensors */}
      {s ? (
        <div className="space-y-2.5">
          <SensorRow icon="🌡️" label="Sıcaklık"    value={s.T}      unit="°C"  min={5}   max={45}  color="bg-orange-400" />
          <SensorRow icon="💧" label="Nem"          value={s.H}      unit="%"   min={20}  max={98}  color="bg-blue-400" />
          <SensorRow icon="🌬️" label="CO₂"          value={s.co2}    unit=" ppm" min={300} max={1800} color="bg-purple-400" />
          <SensorRow icon="☀️" label="Işık"          value={s.isik}   unit=" lx"  min={0}   max={1000} color="bg-yellow-400" />
          <SensorRow icon="🌱" label="Toprak Nemi"  value={s.toprak} unit=""     min={0}   max={1000} color="bg-green-400" />
          <div className="flex gap-4 pt-1">
            <div className="flex-1 bg-slate-700/50 rounded-lg p-2 text-center">
              <p className="text-xs text-slate-400">pH</p>
              <p className="text-sm font-bold text-slate-100 tabular-nums">{s.ph?.toFixed(1) ?? '—'}</p>
            </div>
            <div className="flex-1 bg-slate-700/50 rounded-lg p-2 text-center">
              <p className="text-xs text-slate-400">EC</p>
              <p className="text-sm font-bold text-slate-100 tabular-nums">{s.ec?.toFixed(2) ?? '—'} mS/cm</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-6 text-slate-500 text-sm">Veri bekleniyor…</div>
      )}

      {s?.zaman && (
        <p className="text-xs text-slate-600 mt-3 text-right">
          {new Date(s.zaman).toLocaleTimeString('tr-TR')}
        </p>
      )}
    </div>
  )
}
