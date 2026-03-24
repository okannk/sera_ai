import { useState, useEffect } from 'react'
import { useData } from '../context/DataContext'
import { durumBadgeClass, durumLabel } from '../components/Sidebar'
import { SeraDetayPanel } from '../components/SeraDetayPanel'
import { GoruntuAnaliz } from '../components/GoruntuAnaliz'
import { useKomutGuvenlik } from '../context/KomutGuvenlik'
import type { KomutAdi, SeraOzet } from '../types'

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }

// ─── Bitki Profilleri ─────────────────────────────────────────────────────────

interface SinirDeger {
  min: number
  opt: [number, number]
  max: number
}

interface BitkiSinirlar {
  sicaklik: SinirDeger
  nem: SinirDeger
  co2: SinirDeger
  isik: SinirDeger
  toprakNem: SinirDeger
  toprakIsi: SinirDeger
  ph: SinirDeger
  ec: SinirDeger
}

const BITKI_PROFIL: Record<string, BitkiSinirlar> = {
  Domates: {
    sicaklik:  { min: 15,  opt: [20, 24],     max: 35    },
    nem:       { min: 40,  opt: [60, 80],     max: 95    },
    co2:       { min: 400, opt: [800, 1200],  max: 2000  },
    isik:      { min: 0,   opt: [15000, 25000], max: 50000 },
    toprakNem: { min: 0,   opt: [60, 75],     max: 100   },
    toprakIsi: { min: 10,  opt: [18, 24],     max: 35    },
    ph:        { min: 5.5, opt: [6.0, 7.0],   max: 8.0   },
    ec:        { min: 0,   opt: [2.0, 3.5],   max: 5.0   },
  },
  Biber: {
    sicaklik:  { min: 18,  opt: [22, 26],     max: 35    },
    nem:       { min: 40,  opt: [55, 75],     max: 90    },
    co2:       { min: 400, opt: [800, 1200],  max: 2000  },
    isik:      { min: 0,   opt: [10000, 20000], max: 50000 },
    toprakNem: { min: 0,   opt: [55, 70],     max: 100   },
    toprakIsi: { min: 12,  opt: [20, 26],     max: 35    },
    ph:        { min: 5.5, opt: [6.0, 6.8],   max: 8.0   },
    ec:        { min: 0,   opt: [2.0, 3.5],   max: 5.0   },
  },
  Marul: {
    sicaklik:  { min: 5,   opt: [15, 20],     max: 30    },
    nem:       { min: 40,  opt: [60, 80],     max: 95    },
    co2:       { min: 400, opt: [700, 1000],  max: 2000  },
    isik:      { min: 0,   opt: [8000, 15000], max: 30000 },
    toprakNem: { min: 0,   opt: [60, 75],     max: 100   },
    toprakIsi: { min: 8,   opt: [16, 22],     max: 30    },
    ph:        { min: 5.5, opt: [6.0, 7.0],   max: 8.0   },
    ec:        { min: 0,   opt: [1.5, 2.5],   max: 5.0   },
  },
}

const VARSAYILAN_PROFIL: BitkiSinirlar = BITKI_PROFIL.Domates

function gaugeRenk(deger: number | null | undefined, profil: SinirDeger): string {
  if (deger == null) return '#2a4055'
  if (deger >= profil.opt[0] && deger <= profil.opt[1]) return '#00d4aa'
  if (deger < profil.opt[0] && deger > profil.min + (profil.opt[0] - profil.min) * 0.3) return '#f59e0b'
  if (deger > profil.opt[1] && deger < profil.max - (profil.max - profil.opt[1]) * 0.3) return '#f59e0b'
  return '#ef4444'
}

function durumHex(durum: string): string {
  if (durum === 'ALARM' || durum === 'ACIL_DURDUR') return '#ef4444'
  if (durum === 'UYARI') return '#f59e0b'
  if (durum === 'BAKIM') return '#6b7280'
  return '#00d4aa'
}

// ─── Gauge ────────────────────────────────────────────────────────────────────

interface GaugeProps {
  label: string
  birim: string
  deger: number | null | undefined
  profil: SinirDeger
}

function fmtGaugeVal(deger: number | null | undefined, label: string): string {
  if (deger == null) return '—'
  if (label === 'CO₂' || label === 'Işık') {
    return deger >= 1000 ? `${(deger / 1000).toFixed(0)}k` : String(Math.round(deger))
  }
  if (label === 'PH' || label === 'EC') return deger.toFixed(1)
  return String(Math.round(deger * 10) / 10)
}

function optDurum(deger: number | null | undefined, profil: SinirDeger): { text: string; color: string } | null {
  if (deger == null) return null
  const renk = gaugeRenk(deger, profil)
  if (deger >= profil.opt[0] && deger <= profil.opt[1]) return { text: '✓ optimal', color: renk }
  if (deger < profil.min || deger > profil.max)          return { text: '✗ kritik',  color: renk }
  return { text: '⚠ sınırda', color: renk }
}

function Gauge({ label, birim, deger, profil }: GaugeProps) {
  const renk   = gaugeRenk(deger, profil)
  const offset = deger == null
    ? 130
    : 130 - (Math.min(Math.max(deger, profil.min), profil.max) / profil.max * 130)
  const d      = 'M 10 42 A 26 26 0 1 1 54 42'
  const durum  = optDurum(deger, profil)
  const valStr = fmtGaugeVal(deger, label)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <svg viewBox="0 0 64 48" width="66" height="50" style={{ overflow: 'visible' }}>
        {/* Track */}
        <path d={d} fill="none" stroke="#1a2535" strokeWidth="5" strokeLinecap="round" />
        {/* Fill */}
        {deger != null && (
          <path
            d={d}
            fill="none"
            stroke={renk}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray="130"
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.45s ease, stroke 0.3s ease' }}
          />
        )}
        {/* Value */}
        <text
          x="32" y="40"
          textAnchor="middle"
          fill={deger == null ? '#4a6070' : renk}
          fontSize="9.5" fontWeight="700" fontFamily="var(--mono)"
        >
          {valStr}
        </text>
      </svg>
      <div style={{ fontSize: 8, color: 'var(--t3)', fontFamily: 'var(--mono)', marginTop: -1 }}>{birim}</div>
      <div style={{ fontSize: 9, color: 'var(--t2)', fontWeight: 600, textAlign: 'center' }}>{label}</div>
      <div style={{ fontSize: 8, color: durum?.color ?? 'transparent', minHeight: 10, textAlign: 'center' }}>
        {durum?.text ?? ''}
      </div>
    </div>
  )
}

// ─── SeraKart ─────────────────────────────────────────────────────────────────

interface SulamaEcPh { ec: number | null; ph: number | null }

function SeraKart({ sera, onDetay, sulamaEcPh }: { sera: SeraOzet; onDetay: (id: string) => void; sulamaEcPh?: SulamaEcPh }) {
  const { komutLog, komutGonder } = useData()
  const [komutYuklenen, setKomutYuklenen] = useState<string | null>(null)
  const [komutSonuc, setKomutSonuc]       = useState<{ ok: boolean; mesaj: string } | null>(null)
  const { komutOnayIste, timerSifirla } = useKomutGuvenlik()

  const s      = sera.sensor
  const profil = BITKI_PROFIL[sera.bitki] ?? VARSAYILAN_PROFIL
  const border  = durumHex(sera.durum)

  function isAcik(ac: KomutAdi, kapat: KomutAdi): boolean {
    const son = komutLog
      .filter(k => k.sera_id === sera.id && (k.komut === ac || k.komut === kapat))
      .sort((a, b) => new Date(b.zaman).getTime() - new Date(a.zaman).getTime())[0]
    return son?.komut === ac
  }

  async function gonder(komut: KomutAdi) {
    const impl = async () => {
      setKomutYuklenen(komut); setKomutSonuc(null)
      const r = await komutGonder(sera.id, komut, sera.isim)
      setKomutSonuc(r); setKomutYuklenen(null)
      setTimeout(() => setKomutSonuc(null), 2500)
      timerSifirla()
    }
    komutOnayIste(impl)
  }

  const AKTUATORLER: { ac: KomutAdi; kapat: KomutAdi; ico: string }[] = [
    { ac: 'SULAMA_AC',  kapat: 'SULAMA_KAPAT',  ico: '💧' },
    { ac: 'SOGUTMA_AC', kapat: 'SOGUTMA_KAPAT', ico: '❄️' },
    { ac: 'FAN_AC',     kapat: 'FAN_KAPAT',     ico: '🌀' },
    { ac: 'ISITICI_AC', kapat: 'ISITICI_KAPAT', ico: '🔥' },
  ]

  return (
    <div
      className="card card-hover flex flex-col"
      style={{ borderLeft: `3px solid ${border}`, borderTop: `1px solid ${border}22`, cursor: 'pointer' }}
      onClick={e => { if ((e.target as HTMLElement).closest('button')) return; onDetay(sera.id) }}
    >
      {/* Header — Tünel SVG silüeti + Sera bilgisi */}
      <div style={{ position: 'relative', padding: '10px 12px 8px' }}>
        {/* Tünel sera silüeti */}
        <svg
          viewBox="0 0 320 76"
          preserveAspectRatio="none"
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: 46,
            opacity: 0.15, pointerEvents: 'none',
          }}
        >
          <path
            d="M 25 68 Q 25 8 160 8 Q 295 8 295 68"
            fill="none"
            stroke={border}
            strokeWidth="3"
          />
        </svg>

        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 22 }}>{BITKI_EMOJI[sera.bitki] ?? '🌱'}</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--t1)', fontFamily: 'var(--mono)' }}>
                {sera.isim}
              </div>
              <div className="lbl">{sera.bitki} · {sera.alan} m²</div>
            </div>
          </div>
          <span className={`${durumBadgeClass(sera.durum)} rounded-full px-2 py-0.5 text-xs font-semibold flex items-center gap-1`}>
            {(sera.durum === 'ALARM' || sera.durum === 'ACIL_DURDUR') && (
              <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'currentColor', display: 'inline-block', animation: 'pulse 1.5s infinite' }} />
            )}
            {durumLabel(sera.durum)}
          </span>
        </div>
      </div>

      {/* Gauge Grid */}
      {s ? (
        <div style={{ padding: '2px 10px 8px' }}>
          {/* İç Ortam */}
          <div style={{ fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 2, paddingLeft: 2 }}>
            İÇ ORTAM
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, marginBottom: 6 }}>
            <Gauge label="Sıcaklık" birim="°C"    deger={s.T}      profil={profil.sicaklik} />
            <Gauge label="Nem"      birim="%"      deger={s.H}      profil={profil.nem}      />
            <Gauge label="CO₂"      birim="ppm"    deger={s.co2}    profil={profil.co2}      />
            <Gauge label="Işık"     birim="lx"     deger={s.isik}   profil={profil.isik}     />
          </div>

          {/* Toprak */}
          <div style={{ fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 2, paddingLeft: 2 }}>
            TOPRAK
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2 }}>
            <Gauge label="T.Nem"  birim="%"     deger={s.toprak}            profil={profil.toprakNem} />
            <Gauge label="T.Isı"  birim="°C"    deger={null}                profil={profil.toprakIsi} />
            <Gauge label="PH"     birim="pH"    deger={sulamaEcPh?.ph ?? null} profil={profil.ph}     />
            <Gauge label="EC"     birim="mS/cm" deger={sulamaEcPh?.ec ?? null} profil={profil.ec}     />
          </div>
        </div>
      ) : (
        <div style={{ padding: '20px', color: 'var(--t3)', fontSize: 12, textAlign: 'center' }}>
          Veri bekleniyor…
        </div>
      )}

      {/* Aktüatörler + Fotoğraf analizi */}
      <div style={{ padding: '0 10px 10px', marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
        {AKTUATORLER.map(({ ac, kapat, ico }) => {
          const acik = isAcik(ac, kapat)
          return (
            <button
              key={ac}
              onClick={() => gonder(acik ? kapat : ac)}
              disabled={komutYuklenen !== null}
              title={`${ac.replace('_AC', '')} — ${acik ? 'Kapat' : 'Aç'}`}
              style={{
                width: 32, height: 28, fontSize: 13, borderRadius: 4, cursor: 'pointer',
                background: acik ? 'var(--accent-dim)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${acik ? 'rgba(0,212,170,0.4)' : 'var(--border)'}`,
                opacity: komutYuklenen !== null ? 0.5 : 1,
                transition: 'background 0.15s, border-color 0.15s',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {komutYuklenen === ac || komutYuklenen === kapat ? '·' : ico}
            </button>
          )
        })}
        <div style={{ marginLeft: 'auto' }}>
          <GoruntuAnaliz seraId={sera.id} seraIsim={sera.isim} />
        </div>
      </div>

      {/* Komut geri bildirim */}
      {komutSonuc && (
        <div style={{ padding: '0 10px 8px' }}>
          <div style={{ fontSize: 11, color: komutSonuc.ok ? 'var(--accent)' : 'var(--alarm)' }}>
            {komutSonuc.ok ? '✓' : '✗'} {komutSonuc.mesaj}
          </div>
        </div>
      )}
    </div>
  )
}


// ─── GenelBakis ───────────────────────────────────────────────────────────────

// ─── KazanPanel ───────────────────────────────────────────────────────────────

interface KazanVeri {
  seviye_yuzde: number
  ec: number; ph: number; isi: number
  tank_a: number; tank_b: number; tank_ph: number
  giris_ec: number; giris_ph: number
  sulaniyor: boolean
}

function TankBar({ etiket, yuzde, renk }: { etiket: string; yuzde: number; renk: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', fontWeight: 700, color: renk, width: 24, flexShrink: 0 }}>
        {etiket}
      </div>
      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${yuzde}%`, height: '100%',
          background: renk, borderRadius: 3,
          transition: 'width 0.8s ease',
        }} />
      </div>
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: renk, width: 28, textAlign: 'right', flexShrink: 0 }}>
        {yuzde}%
      </div>
    </div>
  )
}

function MiniKazanSvg({ yuzde, sulaniyor }: { yuzde: number; sulaniyor: boolean }) {
  const tankH = 72; const tankY = 12; const tankX = 10; const tankW = 52
  const fillH = tankH * (yuzde / 100)
  const fillY = tankY + tankH - fillH
  const renk  = sulaniyor ? '#00d4aa' : '#1a6060'
  return (
    <svg viewBox="0 0 72 96" width="72" height="96">
      {/* Giriş boru */}
      <rect x="0" y="20" width="10" height="5" rx="2" fill="none" stroke="#3b82f6" strokeWidth="1.5" />
      {/* Çıkış boru */}
      <rect x="62" y="72" width="10" height="5" rx="2" fill="none" stroke={renk} strokeWidth="1.5" />
      {/* Tank */}
      <rect x={tankX} y={tankY} width={tankW} height={tankH} rx="4"
        fill="#0a1520" stroke="#1e3048" strokeWidth="1.5" />
      <clipPath id="kp-clip">
        <rect x={tankX + 1} y={tankY + 1} width={tankW - 2} height={tankH - 2} rx="3" />
      </clipPath>
      <rect x={tankX + 1} y={fillY} width={tankW - 2} height={fillH}
        fill={`${renk}22`} clipPath="url(#kp-clip)"
        style={{ transition: 'y 1s ease, height 1s ease' }} />
      {fillH > 4 && (
        <rect x={tankX + 1} y={fillY} width={tankW - 2} height="3"
          fill={renk} opacity="0.5" clipPath="url(#kp-clip)" />
      )}
      <rect x={tankX} y={tankY} width={tankW} height={tankH} rx="4"
        fill="none" stroke="#2a4055" strokeWidth="1.5" />
      <text x={tankX + tankW / 2} y={tankY + tankH / 2 + 4}
        textAnchor="middle" fontSize="12" fontWeight="700"
        fill={renk} fontFamily="var(--mono)" opacity="0.9">
        {yuzde}%
      </text>
      {/* Kapak */}
      <rect x={tankX + 8} y={tankY - 5} width={tankW - 16} height={5} rx="2"
        fill="#1a2535" stroke="#2a4055" strokeWidth="1" />
    </svg>
  )
}

function KazanPanel() {
  const [veri, setVeri] = useState<KazanVeri | null>(null)

  useEffect(() => {
    function yukle() {
      fetch('/api/v1/sulama/kazan', {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(json => { if (json?.success) setVeri(json.data) })
        .catch(() => {})
    }
    yukle()
    const t = setInterval(yukle, 5000)
    return () => clearInterval(t)
  }, [])

  function gotoSulama() {
    window.dispatchEvent(new CustomEvent('goto-sayfa', { detail: 'sulama' }))
  }

  const v = veri ?? { seviye_yuzde: 0, ec: 0, ph: 0, isi: 0, tank_a: 0, tank_b: 0, tank_ph: 0, giris_ec: 0, giris_ph: 0, sulaniyor: false }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>

      {/* Kazan */}
      <div className="card" style={{ padding: '12px 14px' }}>
        <div style={{
          fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)',
          letterSpacing: '1px', marginBottom: 8,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>KAZAN</span>
          {v.sulaniyor && (
            <span style={{ color: 'var(--accent)', fontWeight: 700 }}>● AKTIF</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <MiniKazanSvg yuzde={v.seviye_yuzde} sulaniyor={v.sulaniyor} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
            {[
              { l: 'EC',  v: v.ec.toFixed(1),  u: 'mS/cm', c: '#00d4aa' },
              { l: 'PH',  v: v.ph.toFixed(1),  u: 'pH',    c: '#a855f7' },
              { l: 'ISI', v: v.isi.toFixed(1), u: '°C',    c: '#f97316' },
            ].map(({ l, v: val, u, c }) => (
              <div key={l} style={{
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                borderRadius: 5, padding: '4px 8px',
              }}>
                <div style={{ fontSize: 8, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{l}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: c, fontFamily: 'var(--mono)', lineHeight: 1.1 }}>
                  {veri ? val : '—'}
                </div>
                <div style={{ fontSize: 8, color: 'var(--t3)' }}>{u}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Gübre Tankları */}
      <div className="card" style={{ padding: '12px 14px' }}>
        <div style={{ fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 8 }}>
          GÜBRE TANKLARI
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <TankBar etiket="A"   yuzde={veri ? v.tank_a  : 0} renk="#f59e0b" />
          <TankBar etiket="B"   yuzde={veri ? v.tank_b  : 0} renk="#3b82f6" />
          <TankBar etiket="PH-" yuzde={veri ? v.tank_ph : 0} renk="#a855f7" />
        </div>
      </div>

      {/* Arıtılmış Su */}
      <div className="card" style={{ padding: '12px 14px' }}>
        <div style={{ fontSize: 9, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 8 }}>
          ARITILMIŞ SU GİRİŞİ
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {[
            { l: 'EC',  val: veri ? v.giris_ec.toFixed(2) : '—', c: '#3b82f6' },
            { l: 'PH',  val: veri ? v.giris_ph.toFixed(1) : '—', c: '#a855f7' },
          ].map(({ l, val, c }) => (
            <div key={l} style={{
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
              borderRadius: 5, padding: '5px 8px',
            }}>
              <div style={{ fontSize: 8, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{l}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: c, fontFamily: 'var(--mono)' }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Link */}
      <button
        onClick={gotoSulama}
        style={{
          padding: '7px 0', borderRadius: 5, fontSize: 11,
          fontFamily: 'var(--mono)', cursor: 'pointer', fontWeight: 600,
          background: 'var(--accent-dim)', border: '1px solid rgba(0,212,170,0.4)',
          color: 'var(--accent)', width: '100%',
        }}
      >
        💧 Sulama Sayfası →
      </button>
    </div>
  )
}

// ─── GenelBakis ───────────────────────────────────────────────────────────────

// sera_id → { ec, ph } son sulamadan
function useSulamaEcPh(): Record<string, SulamaEcPh> {
  const [map, setMap] = useState<Record<string, SulamaEcPh>>({})
  useEffect(() => {
    function yukle() {
      fetch('/api/v1/sulama/gruplar', {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(json => {
          if (!json?.success) return
          const yeni: Record<string, SulamaEcPh> = {}
          for (const grup of json.data as { sera_idler: string[]; ec_hedef: number | null; ph_hedef: number | null }[]) {
            for (const sid of grup.sera_idler) {
              // Daha önce atanmadıysa ya da bu grubun verisi daha güncel ise ata
              if (!yeni[sid]) yeni[sid] = { ec: grup.ec_hedef, ph: grup.ph_hedef }
            }
          }
          setMap(yeni)
        })
        .catch(() => {})
    }
    yukle()
    const t = setInterval(yukle, 10000)
    return () => clearInterval(t)
  }, [])
  return map
}

export function GenelBakis() {
  const { seralar } = useData()
  const [secilenSera, setSecilenSera] = useState<string | null>(null)
  const sulamaAktif = localStorage.getItem('sera_sulama_aktif') !== 'false'
  const sulamaEcPhMap = useSulamaEcPh()

  const icerik = (
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* Başlık */}
      <div style={{ marginBottom: 14 }}>
        <h1 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', fontFamily: 'var(--mono)', letterSpacing: '2px' }}>
          GENEL BAKIŞ
        </h1>
        <p className="lbl" style={{ marginTop: 3 }}>
          Tüm seraların anlık durumu · karta tıkla → detay
        </p>
      </div>

      {/* Sera kartları */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {seralar.map(sera => (
          <SeraKart
            key={sera.id}
            sera={sera}
            onDetay={setSecilenSera}
            sulamaEcPh={sulamaEcPhMap[sera.id]}
          />
        ))}
        {seralar.length === 0 && (
          <div className="col-span-3 text-center" style={{ padding: 48, color: 'var(--t3)' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🌿</div>
            <div className="lbl">Backend bağlantısı bekleniyor…</div>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="page-root">
      {secilenSera && (
        <SeraDetayPanel seraId={secilenSera} onKapat={() => setSecilenSera(null)} />
      )}

      {sulamaAktif ? (
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 14, alignItems: 'start' }}>
          <div style={{ position: 'sticky', top: 0 }}>
            <KazanPanel />
          </div>
          {icerik}
        </div>
      ) : icerik}
    </div>
  )
}
