import { useState, useEffect, useCallback } from 'react'
import { useData } from '../context/DataContext'
import { useKomutGuvenlik } from '../context/KomutGuvenlik'
import { api } from '../api'
import type { SeraOzet, SeraEkleInput, SeraGuncelleInput, Cihaz, CihazDurum, CihazKayitSonuc, CihazKayitInput, ProvisioningTalep, OnaylamaYaniti, BitkiProfilDetay } from '../types'
import { CihazDetay } from './CihazDetay'

const SISTEM_BILGI = {
  versiyon:   'v1.0.0',
  backend:    'FastAPI + Uvicorn',
  optimizer:  'RLAjan (Q-Learning, 2430 durum)',
  donanim:    'Raspberry Pi 5 + ESP32-S3',
  python:     '3.14',
  veritabani: 'SQLite (WAL modu)',
}

function Toggle({ label, aciklama, aktif, onChange }: {
  label: string; aciklama?: string; aktif: boolean; onChange: (v: boolean) => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--t1)' }}>{label}</div>
        {aciklama && <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>{aciklama}</div>}
      </div>
      <button
        onClick={() => onChange(!aktif)}
        style={{
          width: 44, height: 24, borderRadius: 12, position: 'relative',
          background: aktif ? 'var(--accent)' : 'var(--border)',
          border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0,
        }}
      >
        <span style={{
          position: 'absolute', top: 3, width: 18, height: 18, borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
          left: aktif ? 23 : 3,
        }} />
      </button>
    </div>
  )
}

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬', Salatalık: '🥒', Diğer: '🌱' }
const VARSAYILAN_BITKILER = ['Domates', 'Biber', 'Marul', 'Salatalık', 'Diğer']

const SENSOR_TIPI_SECENEKLER = [
  { deger: 'mock',  etiket: 'Mock (Simülasyon)' },
  { deger: 'mqtt',  etiket: 'MQTT (ESP32-S3)' },
  { deger: 'rs485', etiket: 'RS485 (Modbus)' },
]

// ── Sera Form Modal ────────────────────────────────────────────
interface FormModal {
  mod: 'ekle' | 'duzenle'
  sera?: SeraOzet
}

function SeraFormModal({ mod, sera, bitkiProfilleri, onKapat, onKaydet }: FormModal & {
  bitkiProfilleri: BitkiProfilDetay[]
  onKapat: () => void
  onKaydet: () => void
}) {
  const [isim, setIsim]               = useState(sera?.isim ?? '')
  const [bitki, setBitki]             = useState(sera?.bitki ?? 'Domates')
  const [alan, setAlan]               = useState(String(sera?.alan ?? ''))
  const [sensorTipi, setSensorTipi]   = useState(sera?.sensor_tipi ?? 'mock')
  const [mqttTopic, setMqttTopic]     = useState(sera?.mqtt_topic ?? '')
  const [aciklama, setAciklama]       = useState(sera?.aciklama ?? '')
  const [bekliyor, setBekliyor]       = useState(false)
  const [hata, setHata]               = useState<string | null>(null)

  const bitkiListesi = bitkiProfilleri.length > 0
    ? bitkiProfilleri.map(p => p.isim)
    : VARSAYILAN_BITKILER

  async function kaydet() {
    if (!isim.trim()) { setHata('Sera adı zorunludur'); return }
    const alanSayi = parseFloat(alan)
    if (isNaN(alanSayi) || alanSayi <= 0) { setHata('Alan pozitif bir sayı olmalıdır'); return }
    setBekliyor(true); setHata(null)
    try {
      if (mod === 'ekle') {
        const veri: SeraEkleInput = {
          isim: isim.trim(), bitki, alan: alanSayi,
          sensor_tipi: sensorTipi,
          mqtt_topic: mqttTopic.trim() || undefined,
          aciklama: aciklama.trim() || undefined,
        }
        await api.seraEkle(veri)
      } else if (sera) {
        const veri: SeraGuncelleInput = {
          isim: isim.trim(), bitki, alan: alanSayi,
          sensor_tipi: sensorTipi,
          mqtt_topic: mqttTopic.trim() || undefined,
          aciklama: aciklama.trim() || undefined,
        }
        await api.seraGuncelle(sera.id, veri)
      }
      onKaydet()
    } catch (e) {
      setHata(e instanceof Error ? e.message : 'Sunucu hatası')
    } finally {
      setBekliyor(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onKapat() }}
    >
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, padding: 24, width: '100%', maxWidth: 480,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--t1)', marginBottom: 20 }}>
          {mod === 'ekle' ? '🌿 Yeni Sera Ekle' : '✏️ Sera Düzenle'}
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Sera Adı *</label>
            <input
              className="input-field" style={{ width: '100%' }}
              placeholder="ör. Sera A"
              value={isim}
              onChange={e => setIsim(e.target.value)}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Ürün Türü</label>
            <select
              className="input-field" style={{ width: '100%' }}
              value={bitki}
              onChange={e => setBitki(e.target.value)}
            >
              {bitkiListesi.map(b => (
                <option key={b} value={b}>{BITKI_EMOJI[b] ?? '🌱'} {b}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Alan (m²)</label>
            <input
              className="input-field" style={{ width: '100%' }}
              type="number" min="1" placeholder="ör. 500"
              value={alan}
              onChange={e => setAlan(e.target.value)}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Sensör Tipi</label>
            <select
              className="input-field" style={{ width: '100%' }}
              value={sensorTipi}
              onChange={e => setSensorTipi(e.target.value)}
            >
              {SENSOR_TIPI_SECENEKLER.map(s => (
                <option key={s.deger} value={s.deger}>{s.etiket}</option>
              ))}
            </select>
          </div>

          {sensorTipi === 'mqtt' && (
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>
              MQTT Topic
              <span style={{ color: 'var(--t3)', marginLeft: 6, fontSize: 11 }}>ör. sera/s{sera?.id ?? '{id}'}/sensor</span>
            </label>
            <input
              className="input-field" style={{ width: '100%' }}
              placeholder={`sera/s${sera?.id ?? '{id}'}/sensor`}
              value={mqttTopic}
              onChange={e => setMqttTopic(e.target.value)}
            />
          </div>
          )}

          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Açıklama (isteğe bağlı)</label>
            <input
              className="input-field" style={{ width: '100%' }}
              placeholder="ör. Kuzey blok, A-3 satırı"
              value={aciklama}
              onChange={e => setAciklama(e.target.value)}
            />
          </div>

          {hata && (
            <div style={{
              padding: '8px 12px', borderRadius: 8,
              background: 'var(--alarm-dim)', color: 'var(--alarm)',
              border: '1px solid rgba(239,68,68,0.3)', fontSize: 12,
            }}>
              {hata}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button
              className="btn-ghost"
              style={{ flex: 1, padding: '9px 0' }}
              onClick={onKapat}
              disabled={bekliyor}
            >
              İptal
            </button>
            <button
              className="btn-accent"
              style={{ flex: 1, padding: '9px 0' }}
              onClick={kaydet}
              disabled={bekliyor}
            >
              {bekliyor ? '…' : (mod === 'ekle' ? 'Ekle' : 'Kaydet')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Silme Onayı ────────────────────────────────────────────────
function SilOnayModal({ sera, onKapat, onSil }: {
  sera: SeraOzet; onKapat: () => void; onSil: () => void
}) {
  const [bekliyor, setBekliyor] = useState(false)

  async function sil() {
    setBekliyor(true)
    try {
      await api.seraSil(sera.id)
      onSil()
    } catch { /* sessiz */ } finally {
      setBekliyor(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onKapat() }}
    >
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, padding: 24, width: '100%', maxWidth: 380,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--alarm)', marginBottom: 10 }}>🗑️ Sera Sil</h3>
        <p style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 20 }}>
          <strong style={{ color: 'var(--t1)' }}>{sera.isim}</strong> serasını silmek istediğinizden emin misiniz?
          Bu işlem geri alınamaz.
        </p>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn-ghost" style={{ flex: 1, padding: '9px 0' }} onClick={onKapat} disabled={bekliyor}>İptal</button>
          <button
            onClick={sil}
            disabled={bekliyor}
            style={{
              flex: 1, padding: '9px 0', borderRadius: 8,
              background: 'var(--alarm-dim)', color: 'var(--alarm)',
              border: '1px solid rgba(239,68,68,0.4)', cursor: 'pointer', fontWeight: 600, fontSize: 13,
            }}
          >
            {bekliyor ? '…' : 'Evet, Sil'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Cihaz Bileşenleri ─────────────────────────────────────────

const DURUM_RENK: Record<CihazDurum, string> = {
  CEVRIMICI:  '#10b981',
  GECIKMELI:  '#f59e0b',
  KOPUK:      '#ef4444',
  BILINMIYOR: '#6b7280',
}

function CihazDurumBadge({ durum }: { durum: CihazDurum }) {
  const renk = DURUM_RENK[durum] ?? '#6b7280'
  const etiket = durum === 'CEVRIMICI' ? '🟢 Çevrimiçi'
               : durum === 'GECIKMELI' ? '🟡 Gecikmeli'
               : durum === 'KOPUK'     ? '🔴 Kopuk'
               :                        '⚫ Bilinmiyor'
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, color: renk,
      background: `${renk}18`, border: `1px solid ${renk}44`,
      borderRadius: 6, padding: '2px 8px',
    }}>
      {etiket}
    </span>
  )
}

function CihazEkleModal({ seralar: seraListesi, onKapat, onEklendi }: {
  seralar: SeraOzet[]
  onKapat: () => void
  onEklendi: (sonuc: CihazKayitSonuc) => void
}) {
  const [cihazId, setCihazId]   = useState('')
  const [seraId, setSeraId]     = useState(seraListesi[0]?.id ?? '')
  const [mac, setMac]           = useState('')
  const [tip, setTip]           = useState('WiFi')
  const [firmware, setFirmware] = useState('1.0.0')
  const [bekliyor, setBekliyor] = useState(false)
  const [hata, setHata]         = useState<string | null>(null)

  async function kaydet() {
    if (!seraId.trim()) { setHata('Sera seçimi zorunludur'); return }
    setBekliyor(true); setHata(null)
    try {
      const veri: CihazKayitInput = {
        tesis_kodu: cihazId.trim().toUpperCase() || 'IST01',
        sera_id: seraId.trim(),
        mac_adresi: mac.trim(),
        baglanti_tipi: tip,
        firmware_versiyon: firmware.trim() || '1.0.0',
      }
      const sonuc = await api.cihazKayit(veri)
      onEklendi(sonuc)
    } catch (e) {
      setHata(e instanceof Error ? e.message : 'Sunucu hatası')
    } finally {
      setBekliyor(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onKapat() }}
    >
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, padding: 24, width: '100%', maxWidth: 460,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--t1)', marginBottom: 20 }}>
          📡 Yeni Cihaz Ekle
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>
              Cihaz ID <span style={{ color: 'var(--t3)', fontSize: 11 }}>(isteğe bağlı — otomatik üretilir)</span>
            </label>
            <input className="input-field" style={{ width: '100%' }} placeholder="ör. IST01"
              value={cihazId} onChange={e => setCihazId(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Sera *</label>
            <select className="input-field" style={{ width: '100%' }}
              value={seraId} onChange={e => setSeraId(e.target.value)}>
              {seraListesi.map(s => (
                <option key={s.id} value={s.id}>{BITKI_EMOJI[s.bitki] ?? '🌱'} {s.isim} ({s.id})</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>MAC Adresi <span style={{ color: 'var(--t3)', fontSize: 11 }}>(isteğe bağlı)</span></label>
            <input className="input-field" style={{ width: '100%' }} placeholder="A4:CF:12:78:5B:01"
              value={mac} onChange={e => setMac(e.target.value)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Bağlantı Tipi</label>
              <select className="input-field" style={{ width: '100%' }} value={tip} onChange={e => setTip(e.target.value)}>
                <option>WiFi</option>
                <option>Ethernet</option>
                <option>RS485</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Firmware <span style={{ color: 'var(--t3)', fontSize: 11 }}>(isteğe bağlı)</span></label>
              <input className="input-field" style={{ width: '100%' }} placeholder="1.0.0"
                value={firmware} onChange={e => setFirmware(e.target.value)} />
            </div>
          </div>
          {hata && (
            <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--alarm-dim)', color: 'var(--alarm)', border: '1px solid rgba(239,68,68,0.3)', fontSize: 12 }}>
              {hata}
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button className="btn-ghost" style={{ flex: 1, padding: '9px 0' }} onClick={onKapat} disabled={bekliyor}>İptal</button>
            <button className="btn-accent" style={{ flex: 1, padding: '9px 0' }} onClick={kaydet} disabled={bekliyor}>
              {bekliyor ? '…' : 'Kaydet'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function KimlikGosterModal({ sonuc, onKapat }: { sonuc: CihazKayitSonuc; onKapat: () => void }) {
  const konfigJson = JSON.stringify(sonuc.firmware_konfig, null, 2)

  function indir() {
    const blob = new Blob([konfigJson], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `${sonuc.cihaz.cihaz_id}-config.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 70,
        background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, padding: 24, width: '100%', maxWidth: 520,
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)', marginBottom: 4 }}>
          ✅ Cihaz Başarıyla Eklendi
        </h3>
        <p style={{ fontSize: 12, color: 'var(--alarm)', marginBottom: 16, fontWeight: 600 }}>
          ⚠️ Şifre yalnızca bir kez gösterilir! Şimdi kopyalayın.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
          {[
            ['Cihaz ID', sonuc.cihaz.cihaz_id],
            ['Seri No',  sonuc.cihaz.seri_no],
            ['Sera ID',  sonuc.cihaz.sera_id],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--t3)' }}>{k}</span>
              <span style={{ color: 'var(--t2)', fontFamily: 'monospace' }}>{v}</span>
            </div>
          ))}
          <div style={{ padding: '10px 12px', borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)' }}>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 4 }}>MQTT Şifresi (tek seferlik)</div>
            <div style={{ fontFamily: 'monospace', fontSize: 14, color: 'var(--accent)', wordBreak: 'break-all' }}>{sonuc.sifre}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className="btn-ghost"
            style={{ flex: 1, padding: '9px 0' }}
            onClick={indir}
          >
            ⬇️ Firmware Config İndir
          </button>
          <button
            className="btn-accent"
            style={{ flex: 1, padding: '9px 0' }}
            onClick={onKapat}
          >
            Tamam
          </button>
        </div>
      </div>
    </div>
  )
}

function SifreSifirlaModal({ cihaz, onKapat }: { cihaz: Cihaz; onKapat: () => void }) {
  const [bekliyor, setBekliyor] = useState(false)
  const [yeniSifre, setYeniSifre] = useState<string | null>(null)

  async function sifirla() {
    setBekliyor(true)
    try {
      const sonuc = await api.cihazSifirla(cihaz.cihaz_id)
      setYeniSifre(sonuc.sifre)
    } catch { /* sessiz */ } finally {
      setBekliyor(false)
    }
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => { if (e.target === e.currentTarget && !yeniSifre) onKapat() }}
    >
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 16, padding: 24, width: '100%', maxWidth: 400, boxShadow: '0 24px 64px rgba(0,0,0,0.5)' }}>
        {yeniSifre ? (
          <>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', marginBottom: 8 }}>✅ Şifre Sıfırlandı</h3>
            <p style={{ fontSize: 12, color: 'var(--alarm)', fontWeight: 600, marginBottom: 12 }}>⚠️ Bu şifre yalnızca bir kez gösterilir!</p>
            <div style={{ padding: '10px 12px', borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)', fontFamily: 'monospace', fontSize: 14, color: 'var(--accent)', marginBottom: 16, wordBreak: 'break-all' }}>
              {yeniSifre}
            </div>
            <button className="btn-accent" style={{ width: '100%', padding: '9px 0' }} onClick={onKapat}>Tamam</button>
          </>
        ) : (
          <>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--t1)', marginBottom: 8 }}>🔑 Şifre Sıfırla</h3>
            <p style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 20 }}>
              <strong style={{ color: 'var(--t1)' }}>{cihaz.cihaz_id}</strong> cihazının MQTT şifresini sıfırlamak istiyor musunuz?
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn-ghost" style={{ flex: 1, padding: '9px 0' }} onClick={onKapat} disabled={bekliyor}>İptal</button>
              <button className="btn-accent" style={{ flex: 1, padding: '9px 0' }} onClick={sifirla} disabled={bekliyor}>
                {bekliyor ? '…' : 'Sıfırla'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function CihazSilModal({ cihaz, onKapat, onSilindi }: { cihaz: Cihaz; onKapat: () => void; onSilindi: () => void }) {
  const [bekliyor, setBekliyor] = useState(false)

  async function sil() {
    setBekliyor(true)
    try {
      await api.cihazSil(cihaz.cihaz_id)
      onSilindi()
    } catch { /* sessiz */ } finally {
      setBekliyor(false)
    }
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => { if (e.target === e.currentTarget) onKapat() }}
    >
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 16, padding: 24, width: '100%', maxWidth: 380, boxShadow: '0 24px 64px rgba(0,0,0,0.5)' }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--alarm)', marginBottom: 10 }}>🗑️ Cihaz Sil</h3>
        <p style={{ fontSize: 13, color: 'var(--t2)', marginBottom: 20 }}>
          <strong style={{ color: 'var(--t1)' }}>{cihaz.cihaz_id}</strong> cihazını sistemden kaldırmak istediğinizden emin misiniz?
        </p>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn-ghost" style={{ flex: 1, padding: '9px 0' }} onClick={onKapat} disabled={bekliyor}>İptal</button>
          <button
            onClick={sil} disabled={bekliyor}
            style={{ flex: 1, padding: '9px 0', borderRadius: 8, background: 'var(--alarm-dim)', color: 'var(--alarm)', border: '1px solid rgba(239,68,68,0.4)', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
          >
            {bekliyor ? '…' : 'Evet, Sil'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Ana Sayfa ──────────────────────────────────────────────────
// ─── Şifre Değiştir ──────────────────────────────────────────────────────────

function SifreDegistir() {
  const { kilitli } = useKomutGuvenlik()
  const [mevcut, setMevcut]     = useState('')
  const [yeni, setYeni]         = useState('')
  const [yeniTekrar, setYeniTekrar] = useState('')
  const [hata, setHata]         = useState<string | null>(null)
  const [mesaj, setMesaj]       = useState<string | null>(null)
  const [yukleniyor, setYuk]    = useState(false)

  async function gonder(e: React.FormEvent) {
    e.preventDefault()
    setHata(null); setMesaj(null)
    if (yeni !== yeniTekrar) { setHata('Yeni şifreler eşleşmiyor'); return }
    if (yeni.length < 3)     { setHata('Şifre en az 3 karakter olmalı'); return }
    setYuk(true)
    try {
      const token = localStorage.getItem('access_token') ?? ''
      const r = await fetch('/api/v1/auth/sifre-degistir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ mevcut_sifre: mevcut, yeni_sifre: yeni }),
      })
      const d = await r.json()
      if (!r.ok) { setHata(d.detail ?? 'Hata'); return }
      setMesaj('Şifre güncellendi ✅')
      setMevcut(''); setYeni(''); setYeniTekrar('')
    } catch { setHata('Bağlantı hatası') }
    finally   { setYuk(false) }
  }

  const inputStyle: React.CSSProperties = {
    padding: '7px 10px', background: 'var(--bg)',
    border: '1px solid var(--border)', borderRadius: 4,
    color: 'var(--t1)', fontFamily: 'var(--mono)', fontSize: 12,
    outline: 'none', width: '100%', boxSizing: 'border-box',
  }

  return (
    <div className="card rounded-xl">
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>🔑 Şifre Değiştir</span>
        {kilitli && <span style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>Komut kilidini açın</span>}
      </div>
      <div style={{ padding: 20 }}>
        {kilitli ? (
          <div className="lbl">Bu bölüme erişmek için önce komut kilidini açın (şifre doğrulama).</div>
        ) : (
          <form onSubmit={gonder} style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 320 }}>
            <div>
              <label className="lbl" style={{ display: 'block', marginBottom: 4 }}>MEVCUT ŞİFRE</label>
              <input type="password" value={mevcut} onChange={e => setMevcut(e.target.value)} required style={inputStyle} />
            </div>
            <div>
              <label className="lbl" style={{ display: 'block', marginBottom: 4 }}>YENİ ŞİFRE</label>
              <input type="password" value={yeni} onChange={e => setYeni(e.target.value)} required style={inputStyle} />
            </div>
            <div>
              <label className="lbl" style={{ display: 'block', marginBottom: 4 }}>YENİ ŞİFRE (TEKRAR)</label>
              <input type="password" value={yeniTekrar} onChange={e => setYeniTekrar(e.target.value)} required style={inputStyle} />
            </div>
            {hata  && <div style={{ color: 'var(--alarm)', fontSize: 11 }}>⚠ {hata}</div>}
            {mesaj && <div style={{ color: 'var(--accent)', fontSize: 11 }}>{mesaj}</div>}
            <button
              type="submit" disabled={yukleniyor}
              style={{ padding: '8px 16px', background: yukleniyor ? 'var(--border)' : 'var(--accent)', color: '#000', border: 'none', borderRadius: 4, fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 11, cursor: yukleniyor ? 'not-allowed' : 'pointer', alignSelf: 'flex-start' }}
            >
              {yukleniyor ? 'DEĞİŞTİRİLİYOR…' : 'DEĞİŞTİR'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─── Kullanıcı Yönetimi ───────────────────────────────────────────────────────

interface Kullanici { id: number; kullanici_adi: string; rol: string; olusturulma: string }

function KullaniciYonetimi() {
  // ── Giriş state ─────────────────────────────────────────────
  const [girdi, setGirdi]         = useState('')
  const [loginYuk, setLoginYuk]   = useState(false)
  const [loginHata, setLoginHata] = useState<string | null>(null)

  // ── Mod state ───────────────────────────────────────────────
  const [adminMod, setAdminMod]   = useState(false)
  const [masterMod, setMasterMod] = useState(false)
  const [adminToken, setAdminToken] = useState('')
  const [masterKey, setMasterKey]   = useState('')

  // ── Kullanıcı listesi ────────────────────────────────────────
  const [kullanicilar, setKullanicilar] = useState<Kullanici[]>([])
  const [listHata, setListHata]         = useState<string | null>(null)

  // ── Yeni kullanıcı ───────────────────────────────────────────
  const [yeniAdi, setYeniAdi]     = useState('')
  const [yeniSifre, setYeniSifre] = useState('')
  const [yeniRol, setYeniRol]     = useState('operator')
  const [ekleHata, setEkleHata]   = useState<string | null>(null)
  const [ekleMesaj, setEkleMesaj] = useState<string | null>(null)

  // ── Inline şifre sıfırlama ───────────────────────────────────
  const [sifirlaAcikId, setSifirlaAcikId] = useState<number | null>(null)
  const [sifirlaYeni, setSifirlaYeni]     = useState('')
  const [sifirlaHata, setSifirlaHata]     = useState<string | null>(null)
  const [sifirlaYuk, setSifirlaYuk]       = useState(false)
  const [sifirlaOk, setSifirlaOk]         = useState<number | null>(null)  // başarı göstergesi

  const listele = useCallback(async (token: string, master: string, isAdmin: boolean) => {
    setListHata(null)
    try {
      const headers: HeadersInit = isAdmin
        ? { Authorization: `Bearer ${token}` }
        : { 'X-Master-Key': master }
      const r = await fetch('/api/v1/auth/kullanicilar', { headers })
      if (!r.ok) { setListHata('Liste alınamadı'); return }
      setKullanicilar(await r.json())
    } catch { setListHata('Bağlantı hatası') }
  }, [])

  async function girisYap(e: React.FormEvent) {
    e.preventDefault()
    setLoginYuk(true); setLoginHata(null)

    // Önce admin girişi dene
    try {
      const r = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kullanici_adi: 'admin', sifre: girdi }),
      })
      if (r.ok) {
        const d = await r.json()
        const token = d.access_token
        setAdminToken(token)
        setAdminMod(true)
        await listele(token, '', true)
        setLoginYuk(false)
        return
      }
    } catch { /* devam */ }

    // Admin başarısızsa master key dene
    try {
      const r = await fetch('/api/v1/auth/kullanicilar', {
        headers: { 'X-Master-Key': girdi },
      })
      if (r.ok) {
        setMasterKey(girdi)
        setMasterMod(true)
        setKullanicilar(await r.json())
        setLoginYuk(false)
        return
      }
    } catch { /* devam */ }

    setLoginHata('Geçersiz şifre')
    setLoginYuk(false)
  }

  async function sil(id: number) {
    if (!confirm('Kullanıcı silinsin mi?')) return
    const headers: HeadersInit = adminMod
      ? { Authorization: `Bearer ${adminToken}` }
      : { 'X-Master-Key': masterKey }
    const r = await fetch(`/api/v1/auth/kullanici/${id}`, { method: 'DELETE', headers })
    if (r.ok) listele(adminToken, masterKey, adminMod)
    else { const d = await r.json(); setListHata(d.detail ?? 'Silinemedi') }
  }

  function sifirlaAc(id: number) {
    setSifirlaAcikId(prev => prev === id ? null : id)
    setSifirlaYeni(''); setSifirlaHata(null); setSifirlaOk(null)
  }

  async function sifirlaGonder(kullanici_adi: string, id: number) {
    setSifirlaHata(null); setSifirlaYuk(true)
    const r = await fetch('/api/v1/auth/sifre-sifirla', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(adminMod ? { Authorization: `Bearer ${adminToken}` } : {}),
      },
      body: JSON.stringify({
        kullanici_adi,
        yeni_sifre: sifirlaYeni,
        master_sifre: masterMod ? masterKey : '',
      }),
    })
    setSifirlaYuk(false)
    const d = await r.json()
    if (!r.ok) { setSifirlaHata(d.detail ?? 'Hata'); return }
    setSifirlaOk(id)
    setSifirlaAcikId(null)
    setSifirlaYeni('')
  }

  async function ekle(e: React.FormEvent) {
    e.preventDefault(); setEkleHata(null); setEkleMesaj(null)
    const r = await fetch('/api/v1/auth/kullanici-ekle', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(adminMod ? { Authorization: `Bearer ${adminToken}` } : { 'X-Master-Key': masterKey }),
      },
      body: JSON.stringify({ kullanici_adi: yeniAdi, sifre: yeniSifre, rol: yeniRol }),
    })
    const d = await r.json()
    if (!r.ok) { setEkleHata(d.detail ?? 'Hata'); return }
    setEkleMesaj(d.mesaj); setYeniAdi(''); setYeniSifre('')
    listele(adminToken, masterKey, adminMod)
  }

  const inputStyle: React.CSSProperties = {
    padding: '7px 10px', background: 'var(--bg)',
    border: '1px solid var(--border)', borderRadius: 4,
    color: 'var(--t1)', fontFamily: 'var(--mono)', fontSize: 12,
    outline: 'none', width: '100%', boxSizing: 'border-box',
  }
  const btnStyle: React.CSSProperties = {
    padding: '7px 14px', background: 'var(--accent)', color: '#000',
    border: 'none', borderRadius: 4, fontFamily: 'var(--mono)',
    fontWeight: 700, fontSize: 11, cursor: 'pointer',
  }
  const sectionTitle = (t: string) => (
    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t2)', fontFamily: 'var(--mono)', letterSpacing: '1px', marginBottom: 10 }}>
      {t}
    </div>
  )

  const girisYapildi = adminMod || masterMod

  return (
    <div className="card rounded-xl">
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>👥 Kullanıcı Yönetimi</span>
        {girisYapildi && (
          <span style={{
            fontSize: 10, padding: '3px 8px', borderRadius: 3, fontFamily: 'var(--mono)', fontWeight: 700,
            background: adminMod ? 'rgba(239,68,68,.15)' : 'rgba(0,212,170,.12)',
            color: adminMod ? 'var(--alarm)' : 'var(--accent)',
          }}>
            {adminMod ? 'ADMIN MOD' : 'MASTER MOD'}
          </span>
        )}
      </div>

      {!girisYapildi ? (
        /* ── Giriş ekranı ── */
        <div style={{ padding: 20 }}>
          <div className="lbl" style={{ marginBottom: 12 }}>
            Bu bölüme erişmek için Admin şifre girin.
          </div>
          <form onSubmit={girisYap} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <div style={{ flex: 1 }}>
              <input
                type="password" value={girdi} onChange={e => setGirdi(e.target.value)}
                placeholder="Admin şifre" required style={inputStyle}
              />
            </div>
            <button type="submit" disabled={loginYuk} style={btnStyle}>
              {loginYuk ? '…' : 'GİRİŞ'}
            </button>
          </form>
          {loginHata && <div style={{ color: 'var(--alarm)', fontSize: 11, marginTop: 8 }}>⚠ {loginHata}</div>}
        </div>
      ) : (
        /* ── Yönetim paneli ── */
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Kullanıcı listesi */}
          <div>
            {sectionTitle('MEVCUT KULLANICILAR')}
            {listHata && <div style={{ color: 'var(--alarm)', fontSize: 11, marginBottom: 8 }}>⚠ {listHata}</div>}
            <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: 'rgba(0,0,0,0.3)' }}>
                    {['ID', 'Kullanıcı Adı', 'Rol', 'Oluşturulma', 'İşlemler'].map(h => (
                      <th key={h} style={{ padding: '7px 10px', textAlign: 'left', color: 'var(--t3)', fontWeight: 600, fontFamily: 'var(--mono)', fontSize: 10 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {kullanicilar.map(k => (
                    <>
                      <tr key={k.id} style={{ borderTop: '1px solid var(--border)' }}>
                        <td style={{ padding: '7px 10px', color: 'var(--t3)' }}>{k.id}</td>
                        <td style={{ padding: '7px 10px', color: 'var(--t1)', fontWeight: 500 }}>{k.kullanici_adi}</td>
                        <td style={{ padding: '7px 10px' }}>
                          <span style={{
                            fontSize: 10, padding: '2px 7px', borderRadius: 3,
                            background: k.rol === 'admin' ? 'rgba(239,68,68,.15)' : 'var(--accent-dim)',
                            color: k.rol === 'admin' ? 'var(--alarm)' : 'var(--accent)',
                            fontFamily: 'var(--mono)', fontWeight: 700,
                          }}>{k.rol}</span>
                        </td>
                        <td style={{ padding: '7px 10px', color: 'var(--t3)', fontSize: 11 }}>
                          {k.olusturulma?.slice(0, 16).replace('T', ' ')}
                        </td>
                        <td style={{ padding: '7px 8px', display: 'flex', gap: 4 }}>
                          <button
                            onClick={() => sifirlaAc(k.id)}
                            title="Şifre Sıfırla"
                            style={{
                              fontSize: 10, padding: '3px 8px', borderRadius: 3, cursor: 'pointer',
                              fontFamily: 'var(--mono)', border: '1px solid var(--border)',
                              background: sifirlaAcikId === k.id ? 'var(--accent-dim)' : 'var(--bg)',
                              color: sifirlaAcikId === k.id ? 'var(--accent)' : 'var(--t2)',
                            }}
                          >🔑 Sıfırla</button>
                          <button
                            onClick={() => sil(k.id)}
                            title="Kullanıcı Sil"
                            style={{ fontSize: 10, padding: '3px 8px', background: 'rgba(239,68,68,.15)', color: 'var(--alarm)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 3, cursor: 'pointer', fontFamily: 'var(--mono)' }}
                          >🗑 Sil</button>
                          {sifirlaOk === k.id && (
                            <span style={{ fontSize: 10, color: 'var(--accent)', alignSelf: 'center' }}>✓</span>
                          )}
                        </td>
                      </tr>
                      {/* Inline şifre sıfırlama formu */}
                      {sifirlaAcikId === k.id && (
                        <tr style={{ background: 'rgba(0,212,170,0.04)', borderTop: '1px solid var(--border)' }}>
                          <td colSpan={5} style={{ padding: '10px 12px' }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 11, color: 'var(--t2)', fontFamily: 'var(--mono)' }}>
                                {k.kullanici_adi} için yeni şifre:
                              </span>
                              <input
                                type="password"
                                value={sifirlaYeni}
                                onChange={e => setSifirlaYeni(e.target.value)}
                                placeholder="Yeni şifre"
                                style={{ ...inputStyle, width: 180 }}
                                autoFocus
                              />
                              <button
                                onClick={() => sifirlaGonder(k.kullanici_adi, k.id)}
                                disabled={sifirlaYuk || !sifirlaYeni}
                                style={{ ...btnStyle, opacity: sifirlaYuk || !sifirlaYeni ? 0.5 : 1 }}
                              >{sifirlaYuk ? '…' : 'Onayla'}</button>
                              <button
                                onClick={() => { setSifirlaAcikId(null); setSifirlaHata(null) }}
                                style={{ fontSize: 11, padding: '6px 12px', background: 'var(--bg)', color: 'var(--t2)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer' }}
                              >İptal</button>
                              {sifirlaHata && <span style={{ fontSize: 11, color: 'var(--alarm)' }}>⚠ {sifirlaHata}</span>}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Yeni kullanıcı ekle */}
          <div>
            {sectionTitle('➕ YENİ KULLANICI EKLE')}
            <form onSubmit={ekle} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 8, alignItems: 'end' }}>
              <input value={yeniAdi} onChange={e => setYeniAdi(e.target.value)} placeholder="Kullanıcı adı" required style={inputStyle} />
              <input type="password" value={yeniSifre} onChange={e => setYeniSifre(e.target.value)} placeholder="Şifre" required style={inputStyle} />
              <select value={yeniRol} onChange={e => setYeniRol(e.target.value)} style={{ ...inputStyle, width: 'auto' }}>
                <option value="operator">operator</option>
                <option value="viewer">viewer</option>
                <option value="admin">admin</option>
              </select>
              <button type="submit" style={btnStyle}>EKLE</button>
            </form>
            {ekleHata  && <div style={{ color: 'var(--alarm)', fontSize: 11, marginTop: 6 }}>⚠ {ekleHata}</div>}
            {ekleMesaj && <div style={{ color: 'var(--accent)', fontSize: 11, marginTop: 6 }}>✓ {ekleMesaj}</div>}
          </div>

        </div>
      )}
    </div>
  )
}

export function Ayarlar() {
  const { seralar, saglik, hata, sonGuncelleme } = useData()

  const [formModal, setFormModal]   = useState<FormModal | null>(null)
  const [silModal, setSilModal]     = useState<SeraOzet | null>(null)
  const [yenilemeSayac, setYenilemeSayac] = useState(0)  // force UI refresh

  // ── Bitki profilleri (DB'den) ──────────────────────────────────
  const [bitkiProfilleri, setBitkiProfilleri] = useState<BitkiProfilDetay[]>([])
  useEffect(() => {
    api.bitkiProfilleri().then(setBitkiProfilleri).catch(() => {})
  }, [])

  function yenile() {
    setFormModal(null); setSilModal(null)
    setYenilemeSayac(n => n + 1)
    window.dispatchEvent(new Event('sera-listesi-guncellendi'))
  }

  // ── Cihaz state ─────────────────────────────────────────────
  const [cihazlar, setCihazlar]             = useState<Cihaz[]>([])
  const [cihazEkleAcik, setCihazEkleAcik]   = useState(false)
  const [kayitSonuc, setKayitSonuc]          = useState<CihazKayitSonuc | null>(null)
  const [sifirlaModal, setSifirlaModal]      = useState<Cihaz | null>(null)
  const [cihazSilModal, setCihazSilModal]    = useState<Cihaz | null>(null)
  const [detayPanelCid, setDetayPanelCid]   = useState<string | null>(null)

  useEffect(() => {
    api.cihazlar().then(setCihazlar).catch(() => {})
    const t = setInterval(() => {
      api.cihazlar().then(setCihazlar).catch(() => {})
    }, 5000)
    return () => clearInterval(t)
  }, [])

  function cihazYenile() {
    setCihazEkleAcik(false)
    setCihazSilModal(null)
    api.cihazlar().then(setCihazlar).catch(() => {})
  }

  // ── Provisioning state ────────────────────────────────────
  const [bekleyenTalepler, setBekleyenTalepler] = useState<ProvisioningTalep[]>([])
  const [onaylamaYaniti, setOnaylamaYaniti]     = useState<OnaylamaYaniti | null>(null)
  const [toastMesaj, setToastMesaj]             = useState<string | null>(null)
  const [oncekiTalepSayisi, setOncekiTalepSayisi] = useState(0)

  useEffect(() => {
    function yenile() {
      api.bekleyenTalepler().then(talepler => {
        setBekleyenTalepler(talepler)
        if (talepler.length > oncekiTalepSayisi && oncekiTalepSayisi > 0) {
          const yeni = talepler[talepler.length - 1]
          const seraIsim = seralar.find(s => s.id === yeni.sera_id)?.isim ?? yeni.sera_id
          setToastMesaj(`🔔 Yeni cihaz eşleştirme talebi — ${seraIsim}`)
          setTimeout(() => setToastMesaj(null), 5000)
        }
        setOncekiTalepSayisi(talepler.length)
      }).catch(() => {})
    }
    yenile()
    const t = setInterval(yenile, 5000)
    return () => clearInterval(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oncekiTalepSayisi])

  async function talipOnayla(talep_id: string) {
    try {
      const yanit = await api.provisioningOnayla(talep_id)
      setOnaylamaYaniti(yanit)
      setBekleyenTalepler(prev => prev.filter(t => t.talep_id !== talep_id))
    } catch { /* sessiz */ }
  }

  async function talipReddet(talep_id: string) {
    try {
      await api.provisioningReddet(talep_id)
      setBekleyenTalepler(prev => prev.filter(t => t.talep_id !== talep_id))
    } catch { /* sessiz */ }
  }

  const [bildirimler, setBildirimler] = useState({
    alarmEmail:    true,
    uyariPush:     false,
    telegramBot:   true,
    gunlukRapor:   true,
    kritikSes:     false,
  })
  function toggle(k: keyof typeof bildirimler) {
    setBildirimler(prev => ({ ...prev, [k]: !prev[k] }))
  }

  const apiDurum = hata ? 'HATA' : saglik ? 'CANLΙ' : 'BAĞLANIYOR'
  const apiRenk  = hata ? 'var(--alarm)' : saglik ? 'var(--accent)' : 'var(--warn)'

  return (
    <>
    <div className="page-root">
      {formModal && (
        <SeraFormModal
          mod={formModal.mod}
          sera={formModal.sera}
          bitkiProfilleri={bitkiProfilleri}
          onKapat={() => setFormModal(null)}
          onKaydet={yenile}
        />
      )}
      {silModal && (
        <SilOnayModal
          sera={silModal}
          onKapat={() => setSilModal(null)}
          onSil={yenile}
        />
      )}
      {cihazEkleAcik && (
        <CihazEkleModal
          seralar={seralar}
          onKapat={() => setCihazEkleAcik(false)}
          onEklendi={sonuc => { setCihazEkleAcik(false); setKayitSonuc(sonuc); cihazYenile() }}
        />
      )}
      {kayitSonuc && (
        <KimlikGosterModal sonuc={kayitSonuc} onKapat={() => setKayitSonuc(null)} />
      )}
      {sifirlaModal && (
        <SifreSifirlaModal cihaz={sifirlaModal} onKapat={() => setSifirlaModal(null)} />
      )}
      {cihazSilModal && (
        <CihazSilModal
          cihaz={cihazSilModal}
          onKapat={() => setCihazSilModal(null)}
          onSilindi={cihazYenile}
        />
      )}

      {/* Onaylama sonucu modal */}
      {onaylamaYaniti && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 16, padding: 24, width: '100%', maxWidth: 480, boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)', marginBottom: 4 }}>✅ Cihaz Onaylandı</h3>
            <p style={{ fontSize: 12, color: 'var(--alarm)', fontWeight: 600, marginBottom: 16 }}>⚠️ Token yalnızca bir kez gösterilir! Kopyalayın.</p>
            {[['Cihaz ID', onaylamaYaniti.cihaz_id], ['Talep ID', onaylamaYaniti.talep_id]].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--t3)' }}>{k}</span>
                <span style={{ color: 'var(--t2)', fontFamily: 'monospace' }}>{v}</span>
              </div>
            ))}
            <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)' }}>
              <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 4 }}>JWT Token (ESP32'ye kopyalanacak)</div>
              <div style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent)', wordBreak: 'break-all', lineHeight: 1.6 }}>{onaylamaYaniti.token}</div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button className="btn-ghost" style={{ flex: 1, padding: '9px 0' }}
                onClick={() => navigator.clipboard?.writeText(onaylamaYaniti.token)}>
                📋 Kopyala
              </button>
              <button className="btn-accent" style={{ flex: 1, padding: '9px 0' }} onClick={() => setOnaylamaYaniti(null)}>
                Tamam
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast bildirimi */}
      {toastMesaj && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 80,
          background: 'var(--card)', border: '1px solid var(--accent)',
          borderRadius: 12, padding: '12px 20px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          fontSize: 13, color: 'var(--t1)', fontWeight: 500,
          animation: 'fadeIn 0.3s ease',
        }}>
          {toastMesaj}
        </div>
      )}

      <div className="mb-6">
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Ayarlar</h1>
        <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Sistem yapılandırması ve bildirimler</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Sera Yönetimi */}
        <div className="card rounded-xl">
          <div style={{
            padding: '14px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>🏠 Sera Yönetimi</span>
            <button
              className="btn-accent"
              style={{ padding: '6px 16px', fontSize: 12 }}
              onClick={() => setFormModal({ mod: 'ekle' })}
            >
              + Sera Ekle
            </button>
          </div>
          {seralar.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--t3)' }}>
              {yenilemeSayac >= 0 && 'Henüz sera yok veya veri yükleniyor…'}
            </div>
          ) : (
            <div>
              {seralar.map(s => (
                <div key={s.id} className="table-row" style={{ padding: '13px 16px' }}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span style={{ fontSize: 22 }}>{BITKI_EMOJI[s.bitki] ?? '🌱'}</span>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>{s.isim}</div>
                        <div style={{ fontSize: 11, color: 'var(--t3)' }}>
                          {s.bitki} · {s.alan} m²
                          {s.sensor_tipi && <span style={{ marginLeft: 8, color: s.sensor_tipi === 'mock' ? 'var(--t3)' : 'var(--accent)' }}>{s.sensor_tipi}</span>}
                          {s.mqtt_topic && <span style={{ marginLeft: 8, fontFamily: 'monospace' }}>{s.mqtt_topic}</span>}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ textAlign: 'right', marginRight: 8 }}>
                        <div style={{ fontSize: 11, color: 'var(--t2)' }}>ID: {s.id}</div>
                      </div>
                      <button
                        title="Düzenle"
                        onClick={() => setFormModal({ mod: 'duzenle', sera: s })}
                        style={{
                          background: 'none', border: '1px solid var(--border)',
                          borderRadius: 7, padding: '5px 9px', cursor: 'pointer',
                          color: 'var(--t2)', fontSize: 13, transition: 'background 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--border)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                      >
                        ✏️
                      </button>
                      <button
                        title="Sil"
                        onClick={() => setSilModal(s)}
                        style={{
                          background: 'none', border: '1px solid rgba(239,68,68,0.25)',
                          borderRadius: 7, padding: '5px 9px', cursor: 'pointer',
                          color: 'var(--alarm)', fontSize: 13, transition: 'background 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--alarm-dim)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bekleyen Provisioning Talepleri */}
        {bekleyenTalepler.length > 0 && (
          <div className="card rounded-xl" style={{ gridColumn: '1 / -1', border: '1px solid rgba(239,68,68,0.3)' }}>
            <div style={{
              padding: '14px 16px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--alarm)' }}>📡 Bekleyen Eşleştirme Talepleri</span>
              <span style={{
                fontSize: 11, fontWeight: 700, color: '#fff',
                background: 'var(--alarm)', borderRadius: '50%',
                width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {bekleyenTalepler.length}
              </span>
            </div>
            <div>
              {bekleyenTalepler.map(t => {
                const seraIsim = seralar.find(s => s.id === t.sera_id)?.isim ?? t.sera_id
                const sure = Math.round((Date.now() - new Date(t.talep_zamani).getTime()) / 60000)
                return (
                  <div key={t.talep_id} style={{
                    padding: '13px 16px', borderBottom: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
                  }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <div style={{ fontSize: 13, color: 'var(--t1)', fontWeight: 500 }}>
                        MAC: <span style={{ fontFamily: 'monospace' }}>{t.mac_adresi}</span>
                        <span style={{ marginLeft: 12, color: 'var(--t2)' }}>Sera: {seraIsim}</span>
                        <span style={{ marginLeft: 12, color: 'var(--t2)' }}>{t.baglanti_tipi}</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--t3)' }}>
                        Firmware: v{t.firmware_versiyon} · {sure > 0 ? `${sure}dk önce` : 'Az önce'}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => talipOnayla(t.talep_id)}
                        style={{
                          padding: '7px 16px', borderRadius: 8, cursor: 'pointer',
                          background: 'rgba(16,185,129,0.12)', color: 'var(--accent)',
                          border: '1px solid rgba(16,185,129,0.4)', fontWeight: 600, fontSize: 13,
                        }}
                      >
                        ✓ Onayla
                      </button>
                      <button
                        onClick={() => talipReddet(t.talep_id)}
                        style={{
                          padding: '7px 16px', borderRadius: 8, cursor: 'pointer',
                          background: 'var(--alarm-dim)', color: 'var(--alarm)',
                          border: '1px solid rgba(239,68,68,0.4)', fontWeight: 600, fontSize: 13,
                        }}
                      >
                        ✗ Reddet
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Cihaz Yönetimi */}
        <div className="card rounded-xl">
          <div style={{
            padding: '14px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>📡 Cihaz Yönetimi</span>
            <button
              className="btn-accent"
              style={{ padding: '6px 16px', fontSize: 12 }}
              onClick={() => setCihazEkleAcik(true)}
            >
              + Yeni Cihaz
            </button>
          </div>
          {cihazlar.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
              Kayıtlı cihaz yok
            </div>
          ) : (
            <div>
              {/* Tablo başlığı */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.8fr 0.8fr 1fr 0.8fr auto', gap: 8, padding: '8px 16px', borderBottom: '1px solid var(--border)', fontSize: 11, color: 'var(--t3)', fontWeight: 600 }}>
                <span>Cihaz ID</span><span>Sera</span><span>Bağlantı</span><span>Firmware</span><span>Durum</span><span></span>
              </div>
              {cihazlar.map(c => (
                <div key={c.cihaz_id} className="table-row" style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.8fr 0.8fr 1fr 0.8fr auto', gap: 8, padding: '11px 16px', alignItems: 'center' }}>
                  <div
                    style={{ cursor: 'pointer' }}
                    onClick={() => setDetayPanelCid(c.cihaz_id)}
                    title="Detay paneli aç"
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--accent)', fontFamily: 'monospace' }}>{c.cihaz_id}</div>
                    <div style={{ fontSize: 11, color: 'var(--t3)' }}>{c.seri_no}</div>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--t2)' }}>{c.sera_id}</span>
                  <span style={{ fontSize: 12, color: 'var(--t2)' }}>{c.baglanti_tipi}</span>
                  <span style={{ fontSize: 12, color: 'var(--t2)', fontFamily: 'monospace' }}>v{c.firmware_versiyon}</span>
                  <CihazDurumBadge durum={c.durum} />
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      title="Token Yenile"
                      onClick={() => setSifirlaModal(c)}
                      style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', color: 'var(--t2)', fontSize: 12 }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--border)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                    >
                      🔑
                    </button>
                    <button
                      title="Sil"
                      onClick={() => setCihazSilModal(c)}
                      style={{ background: 'none', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', color: 'var(--alarm)', fontSize: 12 }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--alarm-dim)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bildirim ayarları */}
        <div className="card rounded-xl">
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
            🔔 Bildirim Ayarları
          </div>
          <div style={{ padding: '0 16px' }}>
            {[
              { key: 'alarmEmail',  label: 'E-posta (Alarm)',        aciklama: 'Alarm durumlarında e-posta gönder' },
              { key: 'uyariPush',   label: 'Push Bildirimi (Uyarı)', aciklama: 'Uyarı seviyesi için tarayıcı bildirimi' },
              { key: 'telegramBot', label: 'Telegram Bot',           aciklama: 'Kritik alarmları Telegram\'a ilet' },
              { key: 'gunlukRapor', label: 'Günlük Rapor',           aciklama: 'Her gün 08:00\'de özet e-posta' },
              { key: 'kritikSes',   label: 'Sesli Uyarı',            aciklama: 'ACİL_DURDUR durumunda ses çal' },
            ].map(({ key, label, aciklama }) => (
              <div key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                <Toggle
                  label={label}
                  aciklama={aciklama}
                  aktif={bildirimler[key as keyof typeof bildirimler]}
                  onChange={() => toggle(key as keyof typeof bildirimler)}
                />
              </div>
            ))}
            <div style={{ padding: '10px 0' }} />
          </div>
        </div>

        {/* API bağlantı durumu */}
        <div className="card rounded-xl">
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
            🔌 API Bağlantı Durumu
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span
                style={{
                  width: 12, height: 12, borderRadius: '50%', background: apiRenk,
                  boxShadow: `0 0 8px ${apiRenk}`,
                  animation: apiDurum === 'CANLΙ' ? 'pulse 2s infinite' : undefined,
                }}
              />
              <span style={{ fontWeight: 700, fontSize: 16, color: apiRenk }}>{apiDurum}</span>
              {sonGuncelleme && (
                <span style={{ fontSize: 12, color: 'var(--t3)', marginLeft: 'auto' }}>
                  Son: {sonGuncelleme.toLocaleTimeString('tr-TR')}
                </span>
              )}
            </div>

            {[
              ['Endpoint',     'http://localhost:5000'],
              ['API Versiyonu', '/api/v1/'],
              ['Auth',         'X-API-Key (devre dışı)'],
              ['Rate Limit',   '60 istek/dakika'],
              ['Docs',         'http://localhost:5000/docs'],
              ['Uptime',       saglik?.uptime_fmt ?? '—'],
              ['Alarm',        `${saglik?.alarm_sayisi ?? 0} aktif`],
            ].map(([k, v]) => (
              <div
                key={k}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--t3)' }}>{k}</span>
                <span style={{ color: 'var(--t2)', fontFamily: 'monospace' }}>{v}</span>
              </div>
            ))}

            {hata && (
              <div
                className="rounded-lg"
                style={{
                  marginTop: 12, padding: '8px 12px',
                  background: 'var(--alarm-dim)', border: '1px solid rgba(239,68,68,0.3)',
                  fontSize: 12, color: 'var(--alarm)',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Bağlantı Hatası</div>
                <div>{hata}</div>
                <div style={{ color: 'var(--t3)', marginTop: 6, fontSize: 11 }}>
                  Backend:{' '}
                  <code style={{ color: 'var(--t2)' }}>python -m sera_ai --demo --api</code>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Şifre Değiştir */}
        <SifreDegistir />

        {/* Kullanıcı Yönetimi */}
        <KullaniciYonetimi />

        {/* Sistem bilgisi */}
        <div className="card rounded-xl">
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
            ℹ️ Sistem Bilgisi
          </div>
          <div style={{ padding: 16 }}>
            {Object.entries(SISTEM_BILGI).map(([k, v]) => (
              <div
                key={k}
                style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--t3)', textTransform: 'capitalize' }}>{k}</span>
                <span style={{ color: 'var(--t2)' }}>{v}</span>
              </div>
            ))}
            <div style={{
              marginTop: 16, textAlign: 'center', fontSize: 11, color: 'var(--t3)',
              borderTop: '1px solid var(--border)', paddingTop: 12,
            }}>
              Sera AI Dashboard · Built with React + FastAPI
            </div>
          </div>
        </div>

      </div>
    </div>

    {detayPanelCid && (
      <CihazDetay cid={detayPanelCid} onKapat={() => setDetayPanelCid(null)} />
    )}
  </>
  )
}
