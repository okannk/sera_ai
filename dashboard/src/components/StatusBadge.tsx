import type { Durum } from '../types'

const CONFIG: Record<string, { bg: string; text: string; label: string; dot: string }> = {
  NORMAL:      { bg: 'bg-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400', label: 'Normal' },
  UYARI:       { bg: 'bg-yellow-500/20',  text: 'text-yellow-400',  dot: 'bg-yellow-400',  label: 'Uyarı' },
  ALARM:       { bg: 'bg-orange-500/20',  text: 'text-orange-400',  dot: 'bg-orange-400',  label: 'Alarm' },
  ACIL_DURDUR: { bg: 'bg-red-500/20',     text: 'text-red-400',     dot: 'bg-red-400',     label: 'Acil Dur!' },
  BAKIM:       { bg: 'bg-blue-500/20',    text: 'text-blue-400',    dot: 'bg-blue-400',    label: 'Bakım' },
  BILINMIYOR:  { bg: 'bg-slate-500/20',   text: 'text-slate-400',   dot: 'bg-slate-400',   label: '?' },
}

export function StatusBadge({ durum, size = 'md' }: { durum: Durum; size?: 'sm' | 'md' | 'lg' }) {
  const c = CONFIG[durum] ?? CONFIG['BILINMIYOR']
  const pulse = durum === 'ALARM' || durum === 'ACIL_DURDUR'
  const textSize = size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base' : 'text-sm'
  const px = size === 'sm' ? 'px-2 py-0.5' : 'px-3 py-1'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${c.bg} ${c.text} ${textSize} ${px}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot} ${pulse ? 'animate-pulse' : ''}`} />
      {c.label}
    </span>
  )
}
