import { useState, useEffect } from 'react'
import { useData } from '../context/DataContext'

// ── Tipleri ─────────────────────────────────────────────────────────────────

interface SulamaGrup {
  id: string
  ad: string
  bitki_turu: string
  ekilis_tarihi: string
  sera_idler: string[]
  faz: string
  faz_etiket: string
  ekim_gunu: number
  ec_hedef: number | null
  ph_hedef: number | null
  sure_dakika: number | null
  gunluk_tekrar: number | null
  sulama_durum: string
  son_sulama: string | null
}

// ── Bitki profil (frontend kopyası — faz bazlı hedef değerler) ──────────────

const BITKI_EC_PH: Record<string, Record<string, { ec: number; ph: number; isi: number }>> = {
  Domates: {
    fide:      { ec: 1.5, ph: 6.3, isi: 20 },
    vejatatif: { ec: 2.0, ph: 6.2, isi: 20 },
    cicek:     { ec: 2.8, ph: 6.2, isi: 22 },
    meyve:     { ec: 3.2, ph: 6.0, isi: 22 },
    hasat:     { ec: 2.5, ph: 6.1, isi: 20 },
  },
  Biber: {
    fide:      { ec: 1.8, ph: 6.5, isi: 22 },
    vejatatif: { ec: 2.2, ph: 6.2, isi: 22 },
    cicek:     { ec: 3.0, ph: 6.0, isi: 24 },
    meyve:     { ec: 3.5, ph: 5.8, isi: 24 },
    hasat:     { ec: 3.0, ph: 6.0, isi: 22 },
  },
  Marul: {
    fide:      { ec: 1.2, ph: 6.5, isi: 18 },
    vejatatif: { ec: 1.8, ph: 6.5, isi: 18 },
    hasat:     { ec: 1.5, ph: 6.5, isi: 18 },
  },
}

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }

// ── API yardımcıları ─────────────────────────────────────────────────────────

function apiHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('access_token')
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function apiPost(path: string): Promise<boolean> {
  try {
    const r = await fetch(path, { method: 'POST', headers: apiHeaders() })
    return r.ok
  } catch {
    return false
  }
}

// ── Kazan SVG ────────────────────────────────────────────────────────────────

function KazanSvg({ doluluk, sulaniyor }: { doluluk: number; sulaniyor: boolean }) {
  const dol = Math.max(0, Math.min(1, doluluk))
  const tankH   = 160
  const tankY   = 28
  const tankX   = 18
  const tankW   = 84
  const fillH   = tankH * dol
  const fillY   = tankY + tankH - fillH
  const renk    = sulaniyor ? '#00d4aa' : '#1a6060'
  const renkDim = sulaniyor ? 'rgba(0,212,170,0.18)' : 'rgba(0,80,80,0.18)'

  return (
    <svg viewBox="0 0 120 220" width="120" height="220">
      {/* Giriş borusu (üst-sol, mavi) */}
      <rect x="2" y="44" width="16" height="7" rx="2"
        fill="none" stroke="#3b82f6" strokeWidth="2" />
      <text x="0" y="42" fontSize="7" fill="#3b82f6" fontFamily="var(--mono)">GİR</text>

      {/* Çıkış borusu (alt-sağ, yeşil) */}
      <rect x="102" y="162" width="16" height="7" rx="2"
        fill="none" stroke={renk} strokeWidth="2" />
      <text x="100" y="180" fontSize="7" fill={renk} fontFamily="var(--mono)">ÇIK</text>

      {/* Tank gövdesi */}
      <rect x={tankX} y={tankY} width={tankW} height={tankH} rx="5"
        fill="#0a1520" stroke="#1e3048" strokeWidth="1.5" />

      {/* Su dolgusu (clipPath ile) */}
      <clipPath id="kazan-clip">
        <rect x={tankX + 1} y={tankY + 1} width={tankW - 2} height={tankH - 2} rx="4" />
      </clipPath>
      <rect
        x={tankX + 1} y={fillY} width={tankW - 2} height={fillH}
        fill={renkDim} clipPath="url(#kazan-clip)"
        style={{ transition: 'y 1s ease, height 1s ease' }}
      />

      {/* Su yüzeyi dalgası */}
      {dol > 0.05 && (
        <path
          d={`M ${tankX + 1} ${fillY}
              Q ${tankX + tankW * 0.25} ${fillY - 3} ${tankX + tankW * 0.5} ${fillY}
              Q ${tankX + tankW * 0.75} ${fillY + 3} ${tankX + tankW - 1} ${fillY}
              L ${tankX + tankW - 1} ${fillY + 6}
              Q ${tankX + tankW * 0.75} ${fillY + 9} ${tankX + tankW * 0.5} ${fillY + 6}
              Q ${tankX + tankW * 0.25} ${fillY + 3} ${tankX + 1} ${fillY + 6} Z`}
          fill={renk} opacity="0.35"
          clipPath="url(#kazan-clip)"
        />
      )}

      {/* Doluluk % yazısı */}
      <text x="60" y={tankY + tankH / 2 + 4} textAnchor="middle"
        fontSize="18" fontWeight="700" fill={renk} fontFamily="var(--mono)"
        opacity="0.85">
        {Math.round(dol * 100)}%
      </text>

      {/* Durum etiketi */}
      <text x="60" y={tankY + tankH / 2 + 18} textAnchor="middle"
        fontSize="8" fill={sulaniyor ? '#00d4aa' : 'var(--t3)'} fontFamily="var(--mono)">
        {sulaniyor ? 'SULANIYOR' : 'BEKLEMEDE'}
      </text>

      {/* Kazan çerçevesi (üst üst) */}
      <rect x={tankX} y={tankY} width={tankW} height={tankH} rx="5"
        fill="none" stroke="#2a4055" strokeWidth="1.5" />

      {/* Seviye çizgileri */}
      {[0.25, 0.5, 0.75].map(s => (
        <line key={s}
          x1={tankX + 4} y1={tankY + tankH * (1 - s)}
          x2={tankX + 12} y2={tankY + tankH * (1 - s)}
          stroke="#2a4055" strokeWidth="1" />
      ))}

      {/* Kazan kapağı */}
      <rect x={tankX + 10} y={tankY - 8} width={tankW - 20} height="8" rx="3"
        fill="#1a2535" stroke="#2a4055" strokeWidth="1" />
    </svg>
  )
}

// ── Mini Tank SVG ─────────────────────────────────────────────────────────────

function MiniTank({ etiket, doluluk, renk }: { etiket: string; doluluk: number; renk: string }) {
  const dol = Math.max(0, Math.min(1, doluluk))
  const h = 60, w = 32, fillH = h * dol
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg viewBox="0 0 36 72" width="36" height="72">
        <rect x="2" y="4" width={w} height={h} rx="4" fill="#0a1520" stroke="#1e3048" strokeWidth="1.5" />
        <clipPath id={`mt-clip-${etiket}`}>
          <rect x="3" y="5" width={w - 2} height={h - 2} rx="3" />
        </clipPath>
        <rect x="3" y={4 + h - fillH} width={w - 2} height={fillH}
          fill={`${renk}28`} clipPath={`url(#mt-clip-${etiket})`}
          style={{ transition: 'y 0.8s ease, height 0.8s ease' }} />
        {dol > 0.05 && (
          <rect x="3" y={4 + h - fillH} width={w - 2} height="3"
            fill={renk} opacity="0.5" clipPath={`url(#mt-clip-${etiket})`} />
        )}
        <rect x="2" y="4" width={w} height={h} rx="4" fill="none" stroke="#2a4055" strokeWidth="1.5" />
        <text x="18" y={4 + h / 2 + 4} textAnchor="middle"
          fontSize="9" fontWeight="700" fill={renk} fontFamily="var(--mono)">
          {Math.round(dol * 100)}%
        </text>
      </svg>
      <div style={{ fontSize: 10, fontWeight: 700, color: renk, fontFamily: 'var(--mono)' }}>{etiket}</div>
    </div>
  )
}

// ── Akış Diyagramı ────────────────────────────────────────────────────────────

function AkisDiyagrami({ aktif }: { aktif: boolean }) {
  const renk = aktif ? '#00d4aa' : '#2a4055'
  const steps = [
    { label: 'Arıtılmış\nSu', color: '#3b82f6' },
    { label: 'Gübre\nA+B',   color: '#f59e0b' },
    { label: 'PH\nAyar',    color: '#a855f7' },
    { label: 'Kazan',        color: '#00d4aa' },
    { label: 'Sera\nVanaları', color: '#22c55e' },
  ]
  return (
    <svg viewBox="0 0 480 56" width="100%" height="56">
      {steps.map((s, i) => {
        const x = i * 96 + 8
        return (
          <g key={i}>
            <rect x={x} y="8" width="72" height="40" rx="6"
              fill={`${s.color}14`} stroke={aktif ? s.color : '#1e3048'} strokeWidth="1.5" />
            {s.label.split('\n').map((line, li) => (
              <text key={li} x={x + 36} y={li === 0 ? 24 : 38}
                textAnchor="middle" fontSize="9" fontWeight="600"
                fill={aktif ? s.color : '#4a6070'} fontFamily="var(--mono)">
                {line}
              </text>
            ))}
            {i < steps.length - 1 && (
              <path d={`M ${x + 74} 28 L ${x + 92} 28`}
                stroke={renk} strokeWidth={aktif ? 2 : 1}
                markerEnd={aktif ? 'url(#arr)' : undefined} />
            )}
          </g>
        )
      })}
      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M 0 0 L 6 3 L 0 6 z" fill={renk} />
        </marker>
      </defs>
    </svg>
  )
}

// ── Pompa Chip ────────────────────────────────────────────────────────────────

function PompaChip({ ad, acik }: { ad: string; acik: boolean }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 10px', borderRadius: 20,
      background: acik ? 'rgba(0,212,170,0.12)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${acik ? 'rgba(0,212,170,0.4)' : 'var(--border)'}`,
      fontSize: 11, fontFamily: 'var(--mono)', color: acik ? 'var(--accent)' : 'var(--t3)',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', display: 'inline-block',
        background: acik ? 'var(--accent)' : 'var(--border)',
        boxShadow: acik ? '0 0 5px var(--accent)' : undefined,
      }} />
      {ad}
    </div>
  )
}

// ── Sayısal değer kutusu ──────────────────────────────────────────────────────

function StatKutu({
  label, deger, birim, renk = 'var(--t1)',
}: { label: string; deger: string | number | null; birim?: string; renk?: string }) {
  return (
    <div style={{
      background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
      borderRadius: 6, padding: '8px 12px', minWidth: 72,
    }}>
      <div style={{ fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: renk, fontFamily: 'var(--mono)', lineHeight: 1 }}>
        {deger ?? '—'}
      </div>
      {birim && <div style={{ fontSize: 9, color: 'var(--t3)', marginTop: 2 }}>{birim}</div>}
    </div>
  )
}

// ── Ana Sayfa ─────────────────────────────────────────────────────────────────

export function Sulama() {
  const { seralar } = useData()

  const [gruplar, setGruplar]       = useState<SulamaGrup[]>([])
  const [yukleniyor, setYukleniyor] = useState(true)
  const [islem, setIslem]           = useState<string | null>(null)

  // Kazan simülasyon state
  const [kazanDoluluk] = useState(0.68)
  const [tankA]        = useState(0.82)
  const [tankB]        = useState(0.74)
  const [tankPh]       = useState(0.55)

  // Mock giriş suyu değerleri (arıtılmış su)
  const girisEc  = 0.12
  const girisph  = 7.1
  const girisIsi = 18.4
  const girisDebi = 4.2

  const sulaniyor = gruplar.some(g => g.sulama_durum === 'devam_ediyor')

  function gruplarYukle() {
    return fetch('/api/v1/sulama/gruplar', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(json => {
        if (json?.success) setGruplar(json.data)
        setYukleniyor(false)
      })
      .catch(() => setYukleniyor(false))
  }

  useEffect(() => {
    gruplarYukle()
    const t = setInterval(() => { gruplarYukle() }, 5000)
    return () => clearInterval(t)
  }, [])

  async function baslatDurdur(grup: SulamaGrup) {
    const aktif = grup.sulama_durum === 'devam_ediyor'
    setIslem(grup.id)
    const endpoint = aktif
      ? `/api/v1/sulama/gruplar/${grup.id}/durdur`
      : `/api/v1/sulama/gruplar/${grup.id}/baslat`
    await apiPost(endpoint)
    await gruplarYukle()
    setIslem(null)
  }

  // Sera bazlı sulama sırası oluştur
  function seraIcinHedef(sera_id: string) {
    const sera = seralar.find(s => s.id === sera_id)
    if (!sera) return null
    const profil = BITKI_EC_PH[sera.bitki]
    const grup = gruplar.find(g => g.sera_idler.includes(sera_id))
    if (!profil || !grup) return null
    return profil[grup.faz] ?? Object.values(profil)[0]
  }

  // Her sera için sulama sırası
  const siraTablo = seralar.map((sera, idx) => {
    const hedef = seraIcinHedef(sera.id)
    const grup  = gruplar.find(g => g.sera_idler.includes(sera.id))
    const status = !grup
      ? 'BEKLIYOR'
      : grup.sulama_durum === 'devam_ediyor'
        ? 'SULANIYOR'
        : idx === 0
          ? 'HAZIR'
          : 'HAZIRLANACAK'
    return { sera, hedef, grup, status, sira: idx + 1 }
  })

  const statusRenk = (s: string) => {
    if (s === 'SULANIYOR') return '#00d4aa'
    if (s === 'HAZIR')     return '#f59e0b'
    return 'var(--t3)'
  }
  const statusBg = (s: string) => {
    if (s === 'SULANIYOR') return 'rgba(0,212,170,0.12)'
    if (s === 'HAZIR')     return 'rgba(245,158,11,0.12)'
    return 'rgba(255,255,255,0.04)'
  }

  return (
    <div className="page-root">
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', fontFamily: 'var(--mono)', letterSpacing: '2px' }}>
          SULAMA SİSTEMİ
        </h1>
        <p className="lbl" style={{ marginTop: 3 }}>
          Kazan durumu · gübre tankları · sera sulama sırası
        </p>
      </div>

      {/* Ana bölüm: Sol (kazan) + Sağ (tablo) */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, marginBottom: 16 }}>

        {/* ─── Sol: Kazan + Tanklar ───────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Kazan kartı */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 10 }}>
              KARIŞIM KAZANI
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <KazanSvg doluluk={kazanDoluluk} sulaniyor={sulaniyor} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                <StatKutu label="EC"   deger={2.4}  birim="mS/cm" renk="#00d4aa" />
                <StatKutu label="PH"   deger={6.1}  birim="pH"    renk="#a855f7" />
                <StatKutu label="ISI"  deger={21.2} birim="°C"    renk="#f97316" />
              </div>
            </div>
          </div>

          {/* Mini Tanklar */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 10 }}>
              GÜBRE TANKLARI
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'flex-end' }}>
              <MiniTank etiket="A"    doluluk={tankA}   renk="#f59e0b" />
              <MiniTank etiket="B"    doluluk={tankB}   renk="#3b82f6" />
              <MiniTank etiket="PH-" doluluk={tankPh}  renk="#a855f7" />
            </div>
          </div>
        </div>

        {/* ─── Sağ: Arıtılmış su + Tablo ─────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Arıtılmış Su Girişi */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 10 }}>
              ARITILMIŞ SU GİRİŞİ
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <StatKutu label="EC"    deger={girisEc}   birim="mS/cm" renk="#3b82f6" />
              <StatKutu label="PH"    deger={girisph}   birim="pH"    renk="#a855f7" />
              <StatKutu label="ISI"   deger={girisIsi}  birim="°C"    renk="#f97316" />
              <StatKutu label="DEBİ" deger={girisDebi} birim="L/dk"  renk="#00d4aa" />
            </div>
          </div>

          {/* Sera Sulama Sırası Tablosu */}
          <div className="card flex flex-col" style={{ flex: 1 }}>
            <div className="ph">
              <span className="ph-title">Sera Sulama Sırası</span>
              {yukleniyor && <span style={{ fontSize: 11, color: 'var(--t3)' }}>yükleniyor…</span>}
            </div>

            {siraTablo.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)', fontSize: 12 }}>
                Sera bulunamadı
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {['#', 'Sera / Bitki', 'Hedef EC', 'Hedef PH', 'Isı', 'Süre', 'Durum', 'Aksiyon'].map(h => (
                        <th key={h} style={{
                          padding: '6px 10px', textAlign: 'left',
                          fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)',
                          letterSpacing: '0.5px', fontWeight: 600, whiteSpace: 'nowrap',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {siraTablo.map(({ sera, hedef, grup, status, sira }) => (
                      <tr key={sera.id} className="table-row">
                        <td style={{ padding: '8px 10px', color: 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 11 }}>
                          {sira}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 14 }}>{BITKI_EMOJI[sera.bitki] ?? '🌱'}</span>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--t1)', fontSize: 12 }}>{sera.isim}</div>
                              <div style={{ fontSize: 10, color: 'var(--t3)' }}>{sera.bitki}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--mono)', color: '#00d4aa', fontWeight: 600 }}>
                          {hedef?.ec.toFixed(1) ?? '—'}
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--mono)', color: '#a855f7', fontWeight: 600 }}>
                          {hedef?.ph.toFixed(1) ?? '—'}
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--mono)', color: '#f97316', fontWeight: 600 }}>
                          {hedef?.isi ?? '—'}°C
                        </td>
                        <td style={{ padding: '8px 10px', fontFamily: 'var(--mono)', color: 'var(--t2)', fontSize: 11 }}>
                          {grup?.sure_dakika ? `${grup.sure_dakika} dk` : '—'}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{
                            display: 'inline-block', padding: '2px 8px', borderRadius: 10,
                            fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
                            color: statusRenk(status), background: statusBg(status),
                            border: `1px solid ${statusRenk(status)}40`,
                          }}>
                            {status}
                          </span>
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          {grup && (
                            <button
                              onClick={() => baslatDurdur(grup)}
                              disabled={islem === grup.id}
                              style={{
                                padding: '4px 12px', borderRadius: 4, fontSize: 11,
                                fontFamily: 'var(--mono)', cursor: 'pointer',
                                background: grup.sulama_durum === 'devam_ediyor'
                                  ? 'rgba(239,68,68,0.12)' : 'var(--accent-dim)',
                                border: `1px solid ${grup.sulama_durum === 'devam_ediyor'
                                  ? 'rgba(239,68,68,0.4)' : 'rgba(0,212,170,0.4)'}`,
                                color: grup.sulama_durum === 'devam_ediyor' ? '#f87171' : 'var(--accent)',
                                opacity: islem === grup.id ? 0.5 : 1,
                              }}
                            >
                              {islem === grup.id ? '…' : grup.sulama_durum === 'devam_ediyor' ? 'Durdur' : 'Başlat'}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Alt: Akış Diyagramı + Pompa Durumları */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 10 }}>
          AKIŞ DİYAGRAMI
        </div>
        <AkisDiyagrami aktif={sulaniyor} />

        <div style={{
          marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)',
          display: 'flex', gap: 8, flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', alignSelf: 'center', marginRight: 4 }}>
            POMPALAR:
          </span>
          <PompaChip ad="Gübre-A Pompası" acik={sulaniyor} />
          <PompaChip ad="Gübre-B Pompası" acik={sulaniyor} />
          <PompaChip ad="PH- Pompası"     acik={false}     />
          <PompaChip ad="Ana Pompa"        acik={sulaniyor} />
          <PompaChip ad="Sirkülayon"       acik={true}      />
        </div>
      </div>
    </div>
  )
}
