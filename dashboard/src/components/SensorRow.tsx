interface Props {
  icon: string
  label: string
  value: number | null | undefined
  unit: string
  min?: number
  max?: number
  opt?: number
  color?: string
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}

export function SensorRow({ icon, label, value, unit, min, max, color = 'bg-emerald-400' }: Props) {
  const hasRange = min !== undefined && max !== undefined && value !== null && value !== undefined

  let pct = 50
  let outOfRange = false
  if (hasRange && value !== null && value !== undefined) {
    pct = ((clamp(value, min!, max!) - min!) / (max! - min!)) * 100
    outOfRange = value < min! || value > max!
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-lg w-6 text-center">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-baseline mb-1">
          <span className="text-xs text-slate-400">{label}</span>
          <span className={`text-sm font-semibold tabular-nums ${outOfRange ? 'text-orange-400' : 'text-slate-100'}`}>
            {value !== null && value !== undefined ? `${value}${unit}` : '—'}
          </span>
        </div>
        {hasRange && (
          <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${outOfRange ? 'bg-orange-400' : color}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
