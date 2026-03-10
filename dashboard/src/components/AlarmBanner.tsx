import type { Alarm } from '../types'
import { StatusBadge } from './StatusBadge'

export function AlarmBanner({ alarmlar }: { alarmlar: Alarm[] }) {
  if (alarmlar.length === 0) return null

  return (
    <div className="bg-red-950/60 border border-red-800/50 rounded-xl p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg animate-pulse">🚨</span>
        <h2 className="font-bold text-red-400 text-sm uppercase tracking-wider">
          {alarmlar.length} Aktif Alarm
        </h2>
      </div>
      <div className="flex flex-wrap gap-3">
        {alarmlar.map(a => (
          <div key={a.sera_id} className="flex items-center gap-2 bg-red-900/30 rounded-lg px-3 py-1.5">
            <span className="text-sm font-medium text-red-200">{a.isim}</span>
            <StatusBadge durum={a.durum} size="sm" />
            {a.sensor && (
              <span className="text-xs text-red-300 tabular-nums">
                {a.sensor.T}°C / {a.sensor.H}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
