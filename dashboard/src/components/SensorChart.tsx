import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid,
} from 'recharts'
import type { SensorGecmis } from '../types'

interface Props {
  data: SensorGecmis[]
  field: keyof Omit<SensorGecmis, 'zaman'>
  label: string
  unit: string
  color: string
  optLine?: number
}

export function SensorChart({ data, field, label, unit, color, optLine }: Props) {
  const values = data.map(d => d[field] as number).filter(v => v !== undefined)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 100
  const padding = (max - min) * 0.15 || 5

  return (
    <div className="bg-slate-800/60 rounded-xl p-4">
      <p className="text-sm font-medium text-slate-300 mb-3">
        {label}
        {values.length > 0 && (
          <span className="ml-2 text-xs text-slate-500">
            son: <span className="font-bold" style={{ color }}>{values[values.length - 1]}{unit}</span>
          </span>
        )}
      </p>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="zaman"
            tickFormatter={v => new Date(v).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            tick={{ fontSize: 10, fill: '#64748b' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[min - padding, max + padding]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            tickFormatter={v => `${Math.round(v)}`}
          />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
            labelFormatter={v => new Date(v).toLocaleTimeString('tr-TR')}
            formatter={(v) => [`${v}${unit}`, label]}
          />
          {optLine !== undefined && (
            <ReferenceLine y={optLine} stroke={color} strokeDasharray="4 4" opacity={0.5} />
          )}
          <Line
            type="monotone"
            dataKey={field}
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
