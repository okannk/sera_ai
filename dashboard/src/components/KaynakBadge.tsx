import type { KomutKaynak } from '../types'

interface Props {
  kaynak: KomutKaynak
  size?: 'sm' | 'md'
}

const KAYNAK_CONFIG: Record<KomutKaynak, { icon: string; label: string; bg: string; color: string; border: string }> = {
  sistem:       { icon: '🤖', label: 'Oto',       bg: 'rgba(59,130,246,0.12)',  color: '#3b82f6', border: 'rgba(59,130,246,0.3)' },
  kullanici:    { icon: '👤', label: 'Manuel',    bg: 'rgba(16,185,129,0.12)', color: '#10b981', border: 'rgba(16,185,129,0.3)' },
  alarm:        { icon: '🚨', label: 'Alarm',     bg: 'rgba(239,68,68,0.12)',  color: '#ef4444', border: 'rgba(239,68,68,0.3)'  },
  zamanlayici:  { icon: '⏰', label: 'Zamanlama', bg: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
}

export function KaynakBadge({ kaynak, size = 'sm' }: Props) {
  const c = KAYNAK_CONFIG[kaynak] ?? KAYNAK_CONFIG.sistem
  const fs = size === 'md' ? 11 : 10
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: size === 'md' ? '2px 8px' : '1px 6px',
      borderRadius: 10, fontSize: fs, fontWeight: 600,
      background: c.bg, color: c.color,
      border: `1px solid ${c.border}`,
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      {c.icon} {c.label}
    </span>
  )
}
