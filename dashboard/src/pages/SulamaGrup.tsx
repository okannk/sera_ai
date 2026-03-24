import { useState, useEffect } from 'react'
import { useData } from '../context/DataContext'

// ── Tipler ───────────────────────────────────────────────────────────────────

interface SulamaGrup {
  id: string
  ad: string
  bitki_turu: string
  ekilis_tarihi: string
  sera_idler: string[]
  faz: string
  faz_etiket: string
  faz_sira: number
  ekim_gunu: number
  ec_hedef: number | null
  ph_hedef: number | null
  sure_dakika: number | null
  gunluk_tekrar: number | null
  sulama_durum: string
  son_sulama: string | null
  aktif: number
  baslangic_saat?: string
}

// ── Sabitler ─────────────────────────────────────────────────────────────────

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }
const BITKI_SECENEKLER = ['Domates', 'Biber', 'Marul']

const FAZ_SIRA = ['fide', 'vejatatif', 'cicek', 'meyve', 'hasat']
const FAZ_ETIKET: Record<string, string> = {
  fide: 'FİDE', vejatatif: 'VEJETATİF', cicek: 'ÇİÇEK', meyve: 'MEYVE', hasat: 'HASAT',
}

const GRUP_RENKLER = [
  '#00d4aa', '#f59e0b', '#a855f7', '#3b82f6', '#f97316',
  '#22c55e', '#ec4899', '#06b6d4',
]

// ── API yardımcıları ─────────────────────────────────────────────────────────

function apiHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('access_token')
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function apiCall<T>(
  path: string,
  method = 'GET',
  body?: object,
): Promise<T | null> {
  try {
    const r = await fetch(path, {
      method,
      headers: apiHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!r.ok) return null
    const json = await r.json()
    return json.success ? json.data : null
  } catch {
    return null
  }
}

// ── Büyüme Fazı Çubuğu ───────────────────────────────────────────────────────

function FazBar({ aktifFaz, bitkiTuru }: { aktifFaz: string; bitkiTuru: string }) {
  const fazlar = bitkiTuru === 'Marul'
    ? ['fide', 'vejatatif', 'hasat']
    : FAZ_SIRA
  const aktifIdx = fazlar.indexOf(aktifFaz)

  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      {fazlar.map((faz, i) => {
        const isAktif  = i === aktifIdx
        const isGecmis = i < aktifIdx
        return (
          <div
            key={faz}
            title={FAZ_ETIKET[faz]}
            style={{
              flex: 1, height: 6, borderRadius: 3,
              background: isAktif
                ? 'var(--accent)'
                : isGecmis
                  ? 'rgba(0,212,170,0.3)'
                  : 'var(--border)',
              position: 'relative',
              boxShadow: isAktif ? '0 0 6px var(--accent)' : undefined,
              transition: 'background 0.3s',
            }}
          />
        )
      })}
      <span style={{
        fontSize: 9, color: 'var(--accent)', fontFamily: 'var(--mono)',
        fontWeight: 700, marginLeft: 6, whiteSpace: 'nowrap',
      }}>
        {FAZ_ETIKET[aktifFaz] ?? '?'}
      </span>
    </div>
  )
}

// ── Takvim Satırı ─────────────────────────────────────────────────────────────

function TakvimSatiri({
  grup, renk, seraIsimler,
}: { grup: SulamaGrup; renk: string; seraIsimler: string[] }) {
  const saat = grup.baslangic_saat ?? '—'
  const durum = grup.sulama_durum === 'devam_ediyor' ? 'SULANIYOR' : 'PLANLI'
  const durumRenk = durum === 'SULANIYOR' ? '#00d4aa' : 'var(--t3)'

  return (
    <div className="table-row" style={{
      display: 'grid', gridTemplateColumns: '52px 6px 1fr 1fr 80px',
      alignItems: 'center', gap: 8, padding: '8px 12px',
    }}>
      <div style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: 'var(--t2)', fontSize: 13 }}>
        {saat}
      </div>
      <div style={{ width: 6, height: 32, borderRadius: 3, background: renk, flexShrink: 0 }} />
      <div>
        <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--t1)' }}>{grup.ad}</div>
        <div style={{ fontSize: 10, color: 'var(--t3)' }}>
          {BITKI_EMOJI[grup.bitki_turu]} {grup.bitki_turu} · Gün {grup.ekim_gunu}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {seraIsimler.slice(0, 3).map(isim => (
          <span key={isim} style={{
            fontSize: 9, padding: '1px 6px', borderRadius: 10,
            background: `${renk}18`, border: `1px solid ${renk}40`,
            color: renk, fontFamily: 'var(--mono)',
          }}>{isim}</span>
        ))}
        {seraIsimler.length > 3 && (
          <span style={{ fontSize: 9, color: 'var(--t3)' }}>+{seraIsimler.length - 3}</span>
        )}
      </div>
      <span style={{
        fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
        color: durumRenk,
        padding: '2px 8px', borderRadius: 10,
        background: `${durumRenk}18`, border: `1px solid ${durumRenk}40`,
        textAlign: 'center',
      }}>
        {durum}
      </span>
    </div>
  )
}

// ── Grup Kartı ────────────────────────────────────────────────────────────────

function GrupKart({
  grup, renk, seraIsimler, onBaslat, onDurdur, onDuzenle, onSil, islem,
}: {
  grup: SulamaGrup
  renk: string
  seraIsimler: string[]
  onBaslat: () => void
  onDurdur: () => void
  onDuzenle: () => void
  onSil: () => void
  islem: boolean
}) {
  const sulaniyor = grup.sulama_durum === 'devam_ediyor'

  return (
    <div
      className="card"
      style={{
        borderLeft: `3px solid ${renk}`,
        padding: '12px 14px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}
    >
      {/* Başlık */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ fontSize: 18 }}>{BITKI_EMOJI[grup.bitki_turu] ?? '🌱'}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--t1)', fontFamily: 'var(--mono)' }}>
              {grup.ad}
            </div>
            <div style={{ fontSize: 10, color: 'var(--t3)' }}>
              Ekim: {grup.ekilis_tarihi} · Gün {grup.ekim_gunu}
            </div>
          </div>
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
          color: sulaniyor ? '#00d4aa' : 'var(--t3)',
          padding: '2px 7px', borderRadius: 10,
          background: sulaniyor ? 'rgba(0,212,170,0.12)' : 'rgba(255,255,255,0.04)',
          border: `1px solid ${sulaniyor ? 'rgba(0,212,170,0.4)' : 'var(--border)'}`,
        }}>
          {sulaniyor ? '● SULANIYOR' : 'BEKLİYOR'}
        </span>
      </div>

      {/* Faz çubuğu */}
      <FazBar aktifFaz={grup.faz} bitkiTuru={grup.bitki_turu} />

      {/* Hedef değerler */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4 }}>
        {[
          { l: 'EC',     v: grup.ec_hedef?.toFixed(1) ?? '—',    unit: 'mS/cm', c: '#00d4aa' },
          { l: 'PH',     v: grup.ph_hedef?.toFixed(1) ?? '—',    unit: 'pH',    c: '#a855f7' },
          { l: 'SÜRE',   v: grup.sure_dakika ?? '—',              unit: 'dk',    c: '#f59e0b' },
          { l: 'GÜNLÜK', v: `${grup.gunluk_tekrar ?? '—'}×`,     unit: '/gün',  c: '#3b82f6' },
        ].map(({ l, v, unit, c }) => (
          <div key={l} style={{
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
            borderRadius: 5, padding: '5px 7px',
          }}>
            <div style={{ fontSize: 8, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{l}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: c, fontFamily: 'var(--mono)', lineHeight: 1.2 }}>{v}</div>
            <div style={{ fontSize: 8, color: 'var(--t3)' }}>{unit}</div>
          </div>
        ))}
      </div>

      {/* Sera chip'leri */}
      {seraIsimler.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {seraIsimler.map(isim => (
            <span key={isim} style={{
              fontSize: 9, padding: '2px 7px', borderRadius: 10,
              background: `${renk}14`, border: `1px solid ${renk}38`,
              color: renk, fontFamily: 'var(--mono)',
            }}>
              {isim}
            </span>
          ))}
        </div>
      )}

      {/* Son sulama */}
      {grup.son_sulama && (
        <div style={{ fontSize: 10, color: 'var(--t3)' }}>
          Son sulama: {new Date(grup.son_sulama).toLocaleString('tr-TR')}
        </div>
      )}

      {/* Butonlar */}
      <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
        <button
          onClick={sulaniyor ? onDurdur : onBaslat}
          disabled={islem}
          style={{
            flex: 1, padding: '5px 0', borderRadius: 4, fontSize: 11,
            fontFamily: 'var(--mono)', cursor: 'pointer', fontWeight: 600,
            background: sulaniyor ? 'rgba(239,68,68,0.12)' : 'var(--accent-dim)',
            border: `1px solid ${sulaniyor ? 'rgba(239,68,68,0.4)' : 'rgba(0,212,170,0.4)'}`,
            color: sulaniyor ? '#f87171' : 'var(--accent)',
            opacity: islem ? 0.5 : 1,
          }}
        >
          {islem ? '…' : sulaniyor ? '■ Durdur' : '▶ Başlat'}
        </button>
        <button
          onClick={onDuzenle}
          style={{
            padding: '5px 10px', borderRadius: 4, fontSize: 11,
            fontFamily: 'var(--mono)', cursor: 'pointer',
            background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
            color: 'var(--t2)',
          }}
        >
          ✎
        </button>
        <button
          onClick={onSil}
          style={{
            padding: '5px 10px', borderRadius: 4, fontSize: 11,
            fontFamily: 'var(--mono)', cursor: 'pointer',
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
            color: '#f87171',
          }}
        >
          ✕
        </button>
      </div>
    </div>
  )
}

// ── Grup Form ─────────────────────────────────────────────────────────────────

function GrupForm({
  mevcut, seraIdler, seraIsimMap, onKaydet, onIptal,
}: {
  mevcut?: SulamaGrup | null
  seraIdler: string[]
  seraIsimMap: Record<string, string>
  onKaydet: () => void
  onIptal: () => void
}) {
  const [ad, setAd]                   = useState(mevcut?.ad ?? '')
  const [bitki, setBitki]             = useState(mevcut?.bitki_turu ?? 'Domates')
  const [ekilis, setEkilis]           = useState(mevcut?.ekilis_tarihi ?? new Date().toISOString().slice(0, 10))
  const [secilenSera, setSecilenSera] = useState<string[]>(mevcut?.sera_idler ?? [])
  const [bekliyor, setBekliyor]       = useState(false)
  const [hata, setHata]               = useState<string | null>(null)

  function toggleSera(id: string) {
    setSecilenSera(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  async function kaydet() {
    if (!ad.trim()) { setHata('Grup adı zorunludur'); return }
    setBekliyor(true); setHata(null)
    const body = { ad: ad.trim(), bitki_turu: bitki, ekilis_tarihi: ekilis, sera_idler: secilenSera }
    let ok: unknown
    if (mevcut) {
      ok = await apiCall(`/api/v1/sulama/gruplar/${mevcut.id}`, 'PUT', body)
    } else {
      ok = await apiCall('/api/v1/sulama/gruplar', 'POST', body)
    }
    setBekliyor(false)
    if (ok) { onKaydet() } else { setHata('Kayıt başarısız') }
  }

  const inputStyle = {
    background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
    borderRadius: 5, padding: '7px 10px', fontSize: 12,
    color: 'var(--t1)', width: '100%', outline: 'none',
    fontFamily: 'var(--mono)',
  } as React.CSSProperties

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div>
        <div className="lbl" style={{ marginBottom: 4 }}>Grup Adı</div>
        <input
          value={ad} onChange={e => setAd(e.target.value)}
          placeholder="örn. Domates - Blok A"
          style={inputStyle}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <div className="lbl" style={{ marginBottom: 4 }}>Bitki Türü</div>
          <select value={bitki} onChange={e => setBitki(e.target.value)} style={inputStyle}>
            {BITKI_SECENEKLER.map(b => (
              <option key={b} value={b}>{BITKI_EMOJI[b] ?? ''} {b}</option>
            ))}
          </select>
        </div>
        <div>
          <div className="lbl" style={{ marginBottom: 4 }}>Ekiliş Tarihi</div>
          <input
            type="date" value={ekilis} onChange={e => setEkilis(e.target.value)}
            style={inputStyle}
          />
        </div>
      </div>
      {seraIdler.length > 0 && (
        <div>
          <div className="lbl" style={{ marginBottom: 6 }}>Seralar</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {seraIdler.map(id => {
              const secili = secilenSera.includes(id)
              return (
                <button
                  key={id}
                  onClick={() => toggleSera(id)}
                  style={{
                    padding: '4px 10px', borderRadius: 20, fontSize: 11,
                    fontFamily: 'var(--mono)', cursor: 'pointer',
                    background: secili ? 'var(--accent-dim)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${secili ? 'rgba(0,212,170,0.5)' : 'var(--border)'}`,
                    color: secili ? 'var(--accent)' : 'var(--t2)',
                  }}
                >
                  {seraIsimMap[id] ?? id}
                </button>
              )
            })}
          </div>
        </div>
      )}
      {hata && <div style={{ fontSize: 11, color: 'var(--alarm)' }}>{hata}</div>}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          onClick={kaydet}
          disabled={bekliyor}
          style={{
            flex: 1, padding: '8px 0', borderRadius: 5, fontSize: 12,
            fontFamily: 'var(--mono)', cursor: 'pointer', fontWeight: 700,
            background: 'var(--accent-dim)', border: '1px solid rgba(0,212,170,0.5)',
            color: 'var(--accent)', opacity: bekliyor ? 0.6 : 1,
          }}
        >
          {bekliyor ? 'Kaydediliyor…' : mevcut ? 'Güncelle' : 'Oluştur'}
        </button>
        <button
          onClick={onIptal}
          style={{
            padding: '8px 16px', borderRadius: 5, fontSize: 12,
            fontFamily: 'var(--mono)', cursor: 'pointer',
            background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
            color: 'var(--t2)',
          }}
        >
          İptal
        </button>
      </div>
    </div>
  )
}

// ── Ana Sayfa ─────────────────────────────────────────────────────────────────

export function SulamaGrup() {
  const { seralar } = useData()

  const [gruplar, setGruplar]           = useState<SulamaGrup[]>([])
  const [program, setProgram]           = useState<SulamaGrup[]>([])
  const [yukleniyor, setYukleniyor]     = useState(true)
  const [islem, setIslem]               = useState<string | null>(null)
  const [formAcik, setFormAcik]         = useState(false)
  const [duzenleGrup, setDuzenleGrup]   = useState<SulamaGrup | null>(null)
  const [otoYukleniyor, setOtoYukleniyor] = useState(false)
  const [otoMesaj, setOtoMesaj]         = useState<string | null>(null)

  const seraIsimMap: Record<string, string> = {}
  seralar.forEach(s => { seraIsimMap[s.id] = s.isim })
  const seraIdler = seralar.map(s => s.id)

  function yukle() {
    return Promise.all([
      apiCall<SulamaGrup[]>('/api/v1/sulama/gruplar'),
      apiCall<SulamaGrup[]>('/api/v1/sulama/program'),
    ]).then(([g, p]) => {
      if (g) setGruplar(g)
      if (p) setProgram(p)
      setYukleniyor(false)
    }).catch(() => setYukleniyor(false))
  }

  useEffect(() => {
    yukle()
    const t = setInterval(() => { yukle() }, 5000)
    return () => clearInterval(t)
  }, [])

  async function baslatDurdur(grup: SulamaGrup) {
    setIslem(grup.id)
    const aktif = grup.sulama_durum === 'devam_ediyor'
    await apiCall(
      `/api/v1/sulama/gruplar/${grup.id}/${aktif ? 'durdur' : 'baslat'}`,
      'POST',
    )
    await yukle()
    setIslem(null)
  }

  async function silGrup(grup: SulamaGrup) {
    if (!confirm(`"${grup.ad}" grubunu silmek istediğinizden emin misiniz?`)) return
    await fetch(`/api/v1/sulama/gruplar/${grup.id}`, {
      method: 'DELETE', headers: apiHeaders(),
    })
    await yukle()
  }

  async function otoGrupla() {
    setOtoYukleniyor(true); setOtoMesaj(null)
    const sonuc = await apiCall<{ olusturulan: { grup: string }[] }>(
      '/api/v1/sulama/gruplar/oto-grupla', 'POST',
    )
    setOtoYukleniyor(false)
    if (sonuc) {
      setOtoMesaj(`${sonuc.olusturulan.length} grup oluşturuldu`)
      await yukle()
    } else {
      setOtoMesaj('Hata oluştu')
    }
    setTimeout(() => setOtoMesaj(null), 3000)
  }

  function seraIsimBul(ids: string[]) {
    return ids.map(id => seraIsimMap[id] ?? id)
  }

  return (
    <div className="page-root">
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', fontFamily: 'var(--mono)', letterSpacing: '2px' }}>
          SULAMA GRUPLARI
        </h1>
        <p className="lbl" style={{ marginTop: 3 }}>
          Bitki fazı bazlı sulama programı · EC/PH hedefleri otomatik
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>

        {/* ─── Sol: Grup Listesi ───────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Başlık + Yeni Grup butonu */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: 11, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>
              {gruplar.length} GRUP
            </div>
            <button
              onClick={() => { setDuzenleGrup(null); setFormAcik(true) }}
              style={{
                padding: '5px 14px', borderRadius: 5, fontSize: 11,
                fontFamily: 'var(--mono)', cursor: 'pointer', fontWeight: 700,
                background: 'var(--accent-dim)', border: '1px solid rgba(0,212,170,0.5)',
                color: 'var(--accent)',
              }}
            >
              + Yeni Grup
            </button>
          </div>

          {/* Grup listesi */}
          {yukleniyor ? (
            <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--t3)', fontSize: 12 }}>
              Yükleniyor…
            </div>
          ) : gruplar.length === 0 ? (
            <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--t3)', fontSize: 12 }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>💧</div>
              Henüz sulama grubu yok.<br />
              <span style={{ fontSize: 11 }}>Yeni grup oluştur veya otomatik grupla.</span>
            </div>
          ) : (
            gruplar.map((grup, idx) => {
              const renk = GRUP_RENKLER[idx % GRUP_RENKLER.length]
              return (
                <div key={grup.id}>
                  <GrupKart
                    grup={grup}
                    renk={renk}
                    seraIsimler={seraIsimBul(grup.sera_idler)}
                    onBaslat={() => baslatDurdur(grup)}
                    onDurdur={() => baslatDurdur(grup)}
                    onDuzenle={() => { setDuzenleGrup(grup); setFormAcik(true) }}
                    onSil={() => silGrup(grup)}
                    islem={islem === grup.id}
                  />
                  {idx < gruplar.length - 1 && (
                    <div style={{
                      textAlign: 'center', padding: '4px 0',
                      fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)',
                      letterSpacing: '1px',
                    }}>
                      ↓ SIRA BEKLİYOR
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* ─── Sağ: Takvim + Otomatik Gruplama ────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Bugünün Takvimi */}
          <div className="card flex flex-col">
            <div className="ph">
              <span className="ph-title">Bugünün Takvimi</span>
              <span style={{ fontSize: 11, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>
                {new Date().toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' })}
              </span>
            </div>
            {program.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)', fontSize: 12 }}>
                Bugün için program yok
              </div>
            ) : (
              <div>
                {program.map((grup) => (
                  <TakvimSatiri
                    key={grup.id}
                    grup={grup}
                    renk={GRUP_RENKLER[gruplar.findIndex(g => g.id === grup.id) % GRUP_RENKLER.length] || GRUP_RENKLER[0]}
                    seraIsimler={seraIsimBul(grup.sera_idler)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Otomatik Gruplama */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', marginBottom: 8 }}>
              ⚡ Otomatik Gruplama
            </div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 12, lineHeight: 1.5 }}>
              Seraları bitki türü ve büyüme fazına göre otomatik olarak gruplar.
              Mevcut grupları etkilemez.
            </div>
            <button
              onClick={otoGrupla}
              disabled={otoYukleniyor}
              style={{
                width: '100%', padding: '8px 0', borderRadius: 5, fontSize: 12,
                fontFamily: 'var(--mono)', cursor: 'pointer', fontWeight: 600,
                background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.4)',
                color: '#f59e0b', opacity: otoYukleniyor ? 0.6 : 1,
              }}
            >
              {otoYukleniyor ? 'İşleniyor…' : '⚡ Otomatik Grupla'}
            </button>
            {otoMesaj && (
              <div style={{
                marginTop: 8, fontSize: 11, fontFamily: 'var(--mono)',
                color: otoMesaj.includes('Hata') ? 'var(--alarm)' : 'var(--accent)',
                textAlign: 'center',
              }}>
                {otoMesaj}
              </div>
            )}
          </div>

          {/* Manuel Grup Formu */}
          {formAcik && (
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', marginBottom: 12 }}>
                {duzenleGrup ? '✎ Grup Düzenle' : '+ Yeni Grup Oluştur'}
              </div>
              <GrupForm
                mevcut={duzenleGrup}
                seraIdler={seraIdler}
                seraIsimMap={seraIsimMap}
                onKaydet={() => { setFormAcik(false); setDuzenleGrup(null); yukle() }}
                onIptal={() => { setFormAcik(false); setDuzenleGrup(null) }}
              />
            </div>
          )}

          {/* Faz Açıklaması */}
          <div className="card" style={{ padding: '12px 14px' }}>
            <div style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 8 }}>
              BÜYÜME FAZLARI
            </div>
            {[
              { faz: 'fide',      label: 'FİDE',       aciklama: 'Çimlenme, kök gelişimi',         renk: '#22c55e' },
              { faz: 'vejatatif', label: 'VEJETATİF', aciklama: 'Gövde + yaprak büyümesi',         renk: '#3b82f6' },
              { faz: 'cicek',     label: 'ÇİÇEK',      aciklama: 'Çiçeklenme, pollunasyon',        renk: '#f59e0b' },
              { faz: 'meyve',     label: 'MEYVE',      aciklama: 'Meyve tutumu, büyüme',           renk: '#f97316' },
              { faz: 'hasat',     label: 'HASAT',      aciklama: 'Olgunlaşma, hasat dönemi',       renk: '#00d4aa' },
            ].map(({ label, aciklama, renk }) => (
              <div key={label} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 0', borderBottom: '1px solid var(--border)',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: renk,
                }} />
                <div style={{
                  fontSize: 10, fontWeight: 700, color: renk,
                  fontFamily: 'var(--mono)', width: 72, flexShrink: 0,
                }}>{label}</div>
                <div style={{ fontSize: 10, color: 'var(--t3)' }}>{aciklama}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
