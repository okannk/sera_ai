import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'

const AYLIK_TREND = [
  { ay: 'Oca', gelir: 5800, maliyet: 2100 },
  { ay: 'Şub', gelir: 6200, maliyet: 2300 },
  { ay: 'Mar', gelir: 6800, maliyet: 2450 },
  { ay: 'Nis', gelir: 7200, maliyet: 2500 },
  { ay: 'May', gelir: 7800, maliyet: 2550 },
  { ay: 'Haz', gelir: 8100, maliyet: 2700 },
  { ay: 'Tem', gelir: 7500, maliyet: 2650 },
  { ay: 'Ağu', gelir: 7200, maliyet: 2600 },
  { ay: 'Eyl', gelir: 7600, maliyet: 2500 },
  { ay: 'Eki', gelir: 7000, maliyet: 2400 },
  { ay: 'Kas', gelir: 6500, maliyet: 2350 },
  { ay: 'Ara', gelir: 6000, maliyet: 2200 },
]

const SERA_EKONOMI = [
  {
    id: 's1', isim: 'Sera A', bitki: 'Domates', emoji: '🍅',
    maliyet: { elektrik: 450, su: 200, gubre: 150, emek: 500 },
    gelir: 3750, verimlilik: 81,
  },
  {
    id: 's2', isim: 'Sera B', bitki: 'Biber', emoji: '🌶️',
    maliyet: { elektrik: 280, su: 120, gubre: 100, emek: 300 },
    gelir: 2400, verimlilik: 75,
  },
  {
    id: 's3', isim: 'Sera C', bitki: 'Marul', emoji: '🥬',
    maliyet: { elektrik: 180, su: 80, gubre: 60, emek: 200 },
    gelir: 1600, verimlilik: 88,
  },
]

const TOPLAM = SERA_EKONOMI.reduce(
  (acc, s) => {
    const mal = Object.values(s.maliyet).reduce((a, b) => a + b, 0)
    return { gelir: acc.gelir + s.gelir, maliyet: acc.maliyet + mal }
  },
  { gelir: 0, maliyet: 0 }
)

const MALIYET_DAGILIMI = [
  { isim: 'Elektrik', deger: SERA_EKONOMI.reduce((a, s) => a + s.maliyet.elektrik, 0), renk: '#f59e0b' },
  { isim: 'Su',       deger: SERA_EKONOMI.reduce((a, s) => a + s.maliyet.su, 0),       renk: '#3b82f6' },
  { isim: 'Gübre',    deger: SERA_EKONOMI.reduce((a, s) => a + s.maliyet.gubre, 0),    renk: '#22c55e' },
  { isim: 'Emek',     deger: SERA_EKONOMI.reduce((a, s) => a + s.maliyet.emek, 0),     renk: '#a855f7' },
]

const SERA_KARSILASTIRMA = SERA_EKONOMI.map(s => {
  const mal = Object.values(s.maliyet).reduce((a, b) => a + b, 0)
  return { isim: s.isim, gelir: s.gelir, maliyet: mal, kar: s.gelir - mal }
})

function KPI({ icon, label, value, sub, color = 'var(--accent)' }: {
  icon: string; label: string; value: string; sub?: string; color?: string
}) {
  return (
    <div className="card rounded-xl p-5">
      <div className="flex items-center gap-2 mb-2">
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 12, color: 'var(--t3)' }}>{label}</span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function fmt(n: number) {
  return n.toLocaleString('tr-TR') + ' ₺'
}

export function Ekonomi() {
  const kar = TOPLAM.gelir - TOPLAM.maliyet
  const roi = ((kar / TOPLAM.maliyet) * 100).toFixed(1)

  const tooltipStyle = {
    contentStyle: {
      background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11,
    },
  }

  return (
    <div className="page-root">
      <div className="mb-6">
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Ekonomi</h1>
        <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Aylık maliyet · gelir · verim analizi (mock)</p>
      </div>

      {/* KPI satırı */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KPI icon="💸" label="Toplam Maliyet / Ay"   value={fmt(TOPLAM.maliyet)} color="var(--alarm)" />
        <KPI icon="💰" label="Toplam Gelir / Ay"     value={fmt(TOPLAM.gelir)}   color="var(--accent)" />
        <KPI icon="📈" label="Net Kâr / Ay"          value={fmt(kar)}            color="var(--warn)" sub={`Geçen ay +%8`} />
        <KPI icon="🎯" label="ROI"                   value={`%${roi}`}           color="var(--crit)" sub="Yatırım getirisi" />
      </div>

      {/* Aylık trend + Maliyet dağılımı */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        {/* Aylık trend (2/3 genişlik) */}
        <div className="card rounded-xl p-4 lg:col-span-2">
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)', marginBottom: 12 }}>
            📅 Aylık Trend (2026)
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={AYLIK_TREND} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="ay" tick={{ fontSize: 10, fill: 'var(--t3)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--t3)' }} tickFormatter={v => `${v / 1000}k`} />
              <Tooltip {...tooltipStyle} formatter={(v) => [fmt(Number(v)), '']} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="gelir"   name="Gelir"   fill="var(--accent)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="maliyet" name="Maliyet" fill="var(--alarm)"  radius={[3, 3, 0, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Maliyet dağılımı (1/3 genişlik) */}
        <div className="card rounded-xl p-4" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)', marginBottom: 12 }}>
            🥧 Maliyet Dağılımı
          </div>
          {/* Wrapper div — ResponsiveContainer'a explicit height verir (Recharts best practice) */}
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={MALIYET_DAGILIMI} dataKey="deger" nameKey="isim"
                  cx="50%" cy="45%" outerRadius={70} innerRadius={35}
                >
                  {MALIYET_DAGILIMI.map((d, i) => (
                    <Cell key={i} fill={d.renk} />
                  ))}
                </Pie>
                <Tooltip {...tooltipStyle} formatter={(v) => [fmt(Number(v)), '']} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Sera karşılaştırması */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Bar chart */}
        <div className="card rounded-xl p-4">
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)', marginBottom: 12 }}>
            🏠 Sera Karşılaştırması
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={SERA_KARSILASTIRMA} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="isim" tick={{ fontSize: 11, fill: 'var(--t3)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--t3)' }} tickFormatter={v => `${v / 1000}k`} />
              <Tooltip {...tooltipStyle} formatter={(v) => [fmt(Number(v)), '']} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="gelir"   name="Gelir"  fill="var(--accent)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="kar"     name="Kâr"    fill="var(--warn)"   radius={[3, 3, 0, 0]} />
              <Bar dataKey="maliyet" name="Maliyet" fill="var(--alarm)" radius={[3, 3, 0, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Sera detay tablosu */}
        <div className="card rounded-xl overflow-hidden">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
            📋 Sera Detay
          </div>
          <div>
            {SERA_EKONOMI.map(s => {
              const toplam = Object.values(s.maliyet).reduce((a, b) => a + b, 0)
              const kar = s.gelir - toplam
              return (
                <div key={s.id} className="table-row" style={{ padding: '12px 16px' }}>
                  <div className="flex items-center justify-between mb-1">
                    <span style={{ fontWeight: 600, color: 'var(--t1)' }}>
                      {s.emoji} {s.isim} — {s.bitki}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--accent)' }}>
                      Verim: %{s.verimlilik}
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ fontSize: 12, color: 'var(--t3)' }}>
                    <span>Maliyet: <span style={{ color: 'var(--alarm)' }}>{fmt(toplam)}</span></span>
                    <span>Gelir: <span style={{ color: 'var(--accent)' }}>{fmt(s.gelir)}</span></span>
                    <span>Kâr: <span style={{ color: kar > 0 ? 'var(--warn)' : 'var(--alarm)' }}>{fmt(kar)}</span></span>
                  </div>
                  {/* Verimlilik bar */}
                  <div style={{ marginTop: 6, height: 4, background: 'var(--border)', borderRadius: 2 }}>
                    <div style={{ height: '100%', width: `${s.verimlilik}%`, background: 'var(--accent)', borderRadius: 2 }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
