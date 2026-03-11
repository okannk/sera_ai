import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot, ReferenceArea,
} from 'recharts'
import type { CihazDetayFull, SensorDetay, Aktuator, SensorGecmis, SensorSaglikDurum } from '../types'
import { api } from '../api'

// ── Yardımcı ──────────────────────────────────────────────────

function sinyalBilgi(dbm: number) {
  if (dbm >= -60) return { dolu: 4, renk: '#22c55e', etiket: 'Mükemmel' }
  if (dbm >= -70) return { dolu: 3, renk: '#22c55e', etiket: 'İyi' }
  if (dbm >= -80) return { dolu: 2, renk: '#f59e0b', etiket: 'Orta' }
  return { dolu: 1, renk: '#ef4444', etiket: 'Zayıf' }
}

function uptimeFmt(sn: number): string {
  const g = Math.floor(sn / 86400)
  const s = Math.floor((sn % 86400) / 3600)
  const d = Math.floor((sn % 3600) / 60)
  if (g > 0) return `${g}g ${s}sa ${d}dk`
  if (s > 0) return `${s}sa ${d}dk`
  return `${d}dk`
}

function zamanFark(isoStr: string): string {
  const fark = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
  if (fark < 60) return `${fark}sn önce`
  if (fark < 3600) return `${Math.floor(fark / 60)}dk önce`
  return `${Math.floor(fark / 3600)}sa önce`
}

function saglikRenk(s: SensorSaglikDurum): string {
  return { normal: '#22c55e', uyari: '#f59e0b', arizali: '#ef4444', pik: '#f97316', donmus: '#3b82f6', kalibre_hatasi: '#8b5cf6' }[s] ?? '#6b7280'
}

function saglikEtiket(s: SensorSaglikDurum): string {
  return { normal: '● Normal', uyari: '⚠ Uyarı', arizali: '✕ Arızalı', pik: '↑ Pik', donmus: '❄ Donmuş', kalibre_hatasi: '✕ Kalibrasyon' }[s] ?? s
}

function sensorIkon(tip: string): string {
  if (tip.includes('SHT'))       return '🌡'
  if (tip.includes('MH'))        return '💨'
  if (tip.includes('BH'))        return '☀'
  if (tip.includes('Kapasitif')) return '💧'
  return '📡'
}

function aktuatorIkon(tip: string): string {
  return { sulama: '💧', isitici: '🔥', sogutma: '❄', fan: '💨' }[tip] ?? '⚙'
}

function byteFmt(b: number): string {
  return b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`
}

// ── Sinyal Çubuğu ─────────────────────────────────────────────

function SinyalCubugu({ dbm }: { dbm: number }) {
  const { dolu, renk, etiket } = sinyalBilgi(dbm)
  return (
    <span className="flex items-end gap-0.5" title={`${dbm} dBm — ${etiket}`}>
      {[1, 2, 3, 4].map(i => (
        <span key={i} style={{
          display: 'inline-block', width: 4, height: 4 + i * 3, borderRadius: 1,
          background: i <= dolu ? renk : 'var(--border)',
        }} />
      ))}
      <span style={{ fontSize: 10, color: renk, marginLeft: 4, fontWeight: 600 }}>
        {dbm} dBm
      </span>
    </span>
  )
}

// ── Sensör Kartı ───────────────────────────────────────────────

function SensorKarti({ sensor, onClick }: { sensor: SensorDetay; onClick: () => void }) {
  const renk    = saglikRenk(sensor.saglik)
  const arizali = sensor.saglik === 'arizali'

  let degerStr = '--'
  if (sensor.son_deger && !arizali) {
    degerStr = Object.entries(sensor.son_deger).map(([k, v]) => {
      if (k === 'sicaklik')   return `${v}°C`
      if (k === 'nem')        return `${v}%`
      if (k === 'co2')        return `${v} ppm`
      if (k === 'isik')       return `${v} lux`
      if (k === 'toprak_nem') return `${v}%`
      return `${v}`
    }).join('  ')
  }

  const borderColor = { arizali: 'rgba(239,68,68,0.4)', donmus: 'rgba(59,130,246,0.4)', pik: 'rgba(249,115,22,0.4)' }[sensor.saglik] ?? 'var(--border)'

  return (
    <div onClick={onClick} style={{
      background: 'var(--card)', border: `1px solid ${borderColor}`,
      borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
    }}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 18 }}>{sensorIkon(sensor.tip)}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>{sensor.tip}</div>
            <div style={{ fontSize: 10, color: 'var(--t3)' }}>{sensor.baglanti} · {sensor.adres}</div>
          </div>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
          background: `${renk}18`, color: renk,
        }}>
          {arizali ? 'ARIZALI' : `${(sensor.saglik_skoru * 100).toFixed(0)}%`}
        </span>
      </div>

      {arizali ? (
        <div style={{ margin: '8px 0', fontSize: 12, color: 'var(--t3)' }}>
          <div style={{ color: '#ef4444', fontWeight: 600, marginBottom: 3 }}>Okuma yok</div>
          <div>{sensor.ardisik_hata} ardışık hata</div>
          <div>Son geçerli: {zamanFark(sensor.son_gecerli_okuma)}</div>
        </div>
      ) : (
        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--t1)', margin: '6px 0 8px' }}>
          {degerStr}
        </div>
      )}

      <div className="flex items-center justify-between">
        <span style={{ fontSize: 11, color: renk, fontWeight: 600 }}>{saglikEtiket(sensor.saglik)}</span>
        {sensor.pik_sayisi_son_1saat > 0 && (
          <span style={{ fontSize: 10, color: '#f97316' }}>Pik (1sa): {sensor.pik_sayisi_son_1saat}</span>
        )}
      </div>
      <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>{sensor.aciklama}</div>
      <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 1 }}>
        Son okuma: {zamanFark(sensor.son_gecerli_okuma)}
      </div>
    </div>
  )
}

// ── Aktüatör Satırı ────────────────────────────────────────────

function AktuatorSatir({ ak }: { ak: Aktuator }) {
  const acik = ak.durum === 'acik'
  return (
    <div className="flex items-center gap-3 py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 18, width: 24, textAlign: 'center' }}>{aktuatorIkon(ak.tip)}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)', textTransform: 'capitalize' }}>{ak.tip}</div>
        <div style={{ fontSize: 10, color: 'var(--t3)' }}>GPIO{ak.gpio}</div>
      </div>
      <div style={{
        width: 44, height: 22, borderRadius: 99,
        background: acik ? 'var(--accent)' : 'var(--border)',
        position: 'relative', transition: 'background 0.3s', flexShrink: 0,
      }}>
        <div style={{
          position: 'absolute', top: 3, borderRadius: '50%',
          width: 16, height: 16, background: 'white',
          left: acik ? 25 : 3, transition: 'left 0.3s',
        }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, minWidth: 55, textAlign: 'right', color: acik ? 'var(--accent)' : 'var(--t3)' }}>
        {acik ? '● Açık' : 'Kapalı'}
      </span>
      <span style={{ fontSize: 10, color: 'var(--t3)', minWidth: 64, textAlign: 'right' }}>
        {uptimeFmt(ak.toplam_acik_sure)}
      </span>
    </div>
  )
}

// ── Sensör Geçmiş Grafiği ──────────────────────────────────────

function SensorGecmisGrafik({ cid, sensorTip }: { cid: string; sensorTip: string }) {
  const [veri, setVeri]             = useState<SensorGecmis | null>(null)
  const [yukleniyor, setYukleniyor] = useState(true)

  useEffect(() => {
    setYukleniyor(true)
    api.cihazSensorGecmis(cid, sensorTip)
      .then(setVeri)
      .catch(console.error)
      .finally(() => setYukleniyor(false))
  }, [cid, sensorTip])

  if (yukleniyor) return (
    <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t3)' }}>
      Yükleniyor…
    </div>
  )
  if (!veri) return (
    <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t3)' }}>
      Veri yok
    </div>
  )

  const chartData = veri.olcumler.map(o => ({
    zaman: new Date(o.zaman).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }),
    deger: o.deger,
    pik:   o.pik,
  }))

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>
          {sensorTip} — Son 1 Saat
        </div>
        <div style={{ fontSize: 11, color: 'var(--t3)' }}>
          Birim: {veri.birim} · Normal: {veri.normal_aralik.min}–{veri.normal_aralik.max}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="zaman" tick={{ fontSize: 10, fill: 'var(--t3)' }} interval={9} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--t3)' }} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11 }}
            formatter={(val: number) => [`${val} ${veri.birim}`, 'Değer']}
          />
          {/* Normal aralık bandı */}
          <ReferenceArea
            y1={veri.normal_aralik.min} y2={veri.normal_aralik.max}
            fill="rgba(34,197,94,0.06)" stroke="rgba(34,197,94,0.2)" strokeDasharray="3 3"
          />
          <Line type="monotone" dataKey="deger" stroke="var(--accent)" strokeWidth={2} dot={false} />
          {/* Pik noktaları kırmızı nokta */}
          {veri.olcumler.map((o, i) =>
            o.pik ? (
              <ReferenceDot key={i} x={chartData[i].zaman} y={o.deger} r={5} fill="#ef4444" stroke="white" strokeWidth={1.5} />
            ) : null
          )}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-2" style={{ fontSize: 10, color: 'var(--t3)' }}>
        <span className="flex items-center gap-1.5">
          <span style={{ width: 20, height: 2, background: 'var(--accent)', display: 'inline-block' }} />
          Ölçüm
        </span>
        <span className="flex items-center gap-1.5">
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
          Pik
        </span>
        <span className="flex items-center gap-1.5">
          <span style={{ width: 16, height: 8, background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)', display: 'inline-block', borderRadius: 2 }} />
          Normal aralık
        </span>
      </div>
    </div>
  )
}

// ── Ana Panel ──────────────────────────────────────────────────

interface Props {
  cid: string
  onKapat: () => void
}

type Sekme = 'genel' | 'gecmis'

export function CihazDetay({ cid, onKapat }: Props) {
  const [cihaz, setCihaz]                 = useState<CihazDetayFull | null>(null)
  const [yukleniyor, setYukleniyor]       = useState(true)
  const [hata, setHata]                   = useState<string | null>(null)
  const [sekme, setSekme]                 = useState<Sekme>('genel')
  const [secilenSensor, setSecilenSensor] = useState<string | null>(null)

  const yukle = useCallback(() => {
    setYukleniyor(true)
    setHata(null)
    api.cihazDetayFull(cid)
      .then(d => {
        setCihaz(d)
        if (d.sensorler.length > 0) {
          const s = d.sensorler[0]
          const alan = Object.keys(s.son_deger ?? {})[0] ?? 'deger'
          setSecilenSensor(`${s.tip}_${alan}`)
        }
      })
      .catch(e => setHata(e.message))
      .finally(() => setYukleniyor(false))
  }, [cid])

  useEffect(() => { yukle() }, [yukle])

  // ESC → kapat
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onKapat() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onKapat])

  const durumRenk = (d: string) =>
    ({ CEVRIMICI: '#22c55e', GECIKMELI: '#f59e0b', KOPUK: '#ef4444' }[d] ?? '#6b7280')

  const durumIkon = (d: string) =>
    ({ CEVRIMICI: '🟢', GECIKMELI: '🟡', KOPUK: '🔴' }[d] ?? '⚫')

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex' }}>
      {/* Backdrop */}
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)' }}
        onClick={onKapat}
      />

      {/* Panel */}
      <div style={{
        position: 'relative', marginLeft: 'auto',
        width: '100%', maxWidth: 880,
        background: 'var(--bg)', overflowY: 'auto', display: 'flex', flexDirection: 'column',
      }}>
        {yukleniyor && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t3)', fontSize: 14 }}>
            Yükleniyor…
          </div>
        )}

        {hata && !yukleniyor && (
          <div style={{ padding: 24 }}>
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 10, padding: 16, color: '#ef4444', fontSize: 13 }}>
              ⚠ {hata}
            </div>
          </div>
        )}

        {cihaz && !yukleniyor && (
          <>
            {/* ── Üst Bar ──────────────────────────────────── */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '14px 20px',
              borderBottom: '1px solid var(--border)',
              background: 'var(--card)',
              position: 'sticky', top: 0, zIndex: 10,
            }}>
              <button onClick={onKapat} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--t2)', fontSize: 20, padding: '0 4px', lineHeight: 1,
              }}>←</button>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--t1)' }}>{cihaz.cihaz_id}</div>
                <div style={{ fontSize: 11, color: 'var(--t3)' }}>
                  Sera {cihaz.sera_id.toUpperCase()} · {cihaz.baglanti_tipi} · {cihaz.mac_adresi}
                </div>
              </div>
              <span style={{
                fontSize: 12, fontWeight: 700, padding: '3px 12px', borderRadius: 99,
                background: `${durumRenk(cihaz.durum)}22`, color: durumRenk(cihaz.durum),
                border: `1px solid ${durumRenk(cihaz.durum)}44`,
              }}>
                {durumIkon(cihaz.durum)} {cihaz.durum}
              </span>
            </div>

            {/* ── Kimlik Kartları ───────────────────────────── */}
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
              <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))' }}>
                {([
                  { e: 'WiFi Sinyal',       d: <SinyalCubugu dbm={cihaz.sinyal_gucu} /> },
                  { e: 'Uptime',             d: uptimeFmt(cihaz.uptime_saniye) },
                  { e: 'Firmware',           d: `v${cihaz.firmware_versiyon}` },
                  { e: 'Yeniden Başlama',    d: `${cihaz.yeniden_baslama_sayisi}×` },
                  { e: 'Boş Bellek',         d: byteFmt(cihaz.bellek_bos) },
                  { e: 'CPU Sıcaklık',       d: `${cihaz.cpu_sicakligi}°C` },
                  { e: 'Son Görülme',        d: zamanFark(cihaz.son_gorulen) },
                ] as { e: string; d: React.ReactNode }[]).map(({ e, d }) => (
                  <div key={e} style={{ background: 'var(--card)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 4 }}>{e}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)' }}>{d}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Sekmeler ─────────────────────────────────── */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 20px', background: 'var(--card)' }}>
              {(['genel', 'gecmis'] as Sekme[]).map(s => (
                <button key={s} onClick={() => setSekme(s)} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '10px 18px',
                  borderBottom: sekme === s ? '2px solid var(--accent)' : '2px solid transparent',
                  color: sekme === s ? 'var(--accent)' : 'var(--t3)',
                  fontSize: 13, fontWeight: sekme === s ? 600 : 400,
                }}>
                  {s === 'genel' ? '⚡ Genel Bakış' : '📈 Sensör Geçmişi'}
                </button>
              ))}
            </div>

            {/* ── Sekme İçerikleri ─────────────────────────── */}
            <div style={{ padding: 20, flex: 1 }}>

              {sekme === 'genel' && (
                <>
                  {/* Sensörler */}
                  <div style={{ marginBottom: 24 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', marginBottom: 12 }}>
                      Sensörler
                      <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--t3)', marginLeft: 8 }}>
                        (karta tıkla → geçmiş grafiği)
                      </span>
                    </h3>
                    <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))' }}>
                      {cihaz.sensorler.map(s => (
                        <SensorKarti
                          key={s.tip}
                          sensor={s}
                          onClick={() => {
                            const alan = Object.keys(s.son_deger ?? {})[0] ?? 'deger'
                            setSecilenSensor(`${s.tip}_${alan}`)
                            setSekme('gecmis')
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Aktüatörler */}
                  <div style={{ marginBottom: 24 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', marginBottom: 12 }}>Aktüatörler</h3>
                    <div style={{ background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)', padding: '0 16px' }}>
                      {cihaz.aktuatorler.map((ak, i) => (
                        <AktuatorSatir key={i} ak={ak} />
                      ))}
                    </div>
                  </div>

                  {/* Bağlantı Geçmişi */}
                  <div>
                    <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', marginBottom: 12 }}>Bağlantı Geçmişi</h3>
                    <div style={{ background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' }}>
                      {cihaz.baglanti_gecmisi.map((o, i) => (
                        <div key={i} className="flex items-start gap-3" style={{
                          padding: '10px 16px',
                          borderBottom: i < cihaz.baglanti_gecmisi.length - 1 ? '1px solid var(--border)' : 'none',
                        }}>
                          <span style={{
                            fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                            background: o.olay === 'BAGLANDI' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                            color: o.olay === 'BAGLANDI' ? '#22c55e' : '#ef4444',
                            whiteSpace: 'nowrap',
                          }}>
                            {o.olay === 'BAGLANDI' ? '⬆ Bağlandı' : '⬇ Koptu'}
                          </span>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 12, color: 'var(--t1)' }}>{o.detay}</div>
                            <div style={{ fontSize: 10, color: 'var(--t3)' }}>
                              {new Date(o.zaman).toLocaleString('tr-TR')}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {sekme === 'gecmis' && (
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', marginBottom: 10 }}>Sensör Seç</h3>
                  <div className="flex flex-wrap gap-2 mb-5">
                    {cihaz.sensorler.map(s => {
                      const alan = Object.keys(s.son_deger ?? {})[0] ?? 'deger'
                      const key  = `${s.tip}_${alan}`
                      const sec  = secilenSensor === key
                      return (
                        <button key={key} onClick={() => setSecilenSensor(key)} style={{
                          background: sec ? 'var(--accent)' : 'var(--card)',
                          color: sec ? 'white' : 'var(--t2)',
                          border: `1px solid ${sec ? 'var(--accent)' : 'var(--border)'}`,
                          borderRadius: 8, padding: '6px 14px', cursor: 'pointer',
                          fontSize: 12, fontWeight: sec ? 600 : 400,
                        }}>
                          {sensorIkon(s.tip)} {s.tip}
                          {s.saglik !== 'normal' && (
                            <span style={{ marginLeft: 6, fontSize: 10, color: sec ? 'rgba(255,255,255,0.8)' : saglikRenk(s.saglik) }}>
                              ({saglikEtiket(s.saglik)})
                            </span>
                          )}
                        </button>
                      )
                    })}
                  </div>

                  {secilenSensor && (
                    <div style={{ background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)', padding: 16 }}>
                      <SensorGecmisGrafik cid={cid} sensorTip={secilenSensor} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
