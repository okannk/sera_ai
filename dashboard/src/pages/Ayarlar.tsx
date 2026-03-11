import { useState, useEffect } from 'react'
import { useData } from '../context/DataContext'
import { api } from '../api'
import type { SeraOzet, SeraEkleInput, SeraGuncelleInput, Cihaz, CihazDurum, CihazKayitSonuc, CihazKayitInput, ProvisioningTalep, OnaylamaYaniti } from '../types'
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
const BITKI_SECENEKLER = ['Domates', 'Biber', 'Marul', 'Salatalık', 'Diğer']

// ── Sera Form Modal ────────────────────────────────────────────
interface FormModal {
  mod: 'ekle' | 'duzenle'
  sera?: SeraOzet
}

function SeraFormModal({ mod, sera, onKapat, onKaydet }: FormModal & {
  onKapat: () => void
  onKaydet: () => void
}) {
  const [isim, setIsim]         = useState(sera?.isim ?? '')
  const [bitki, setBitki]       = useState(sera?.bitki ?? 'Domates')
  const [alan, setAlan]         = useState(String(sera?.alan ?? ''))
  const [ip, setIp]             = useState((sera as any)?.esp32_ip ?? '')
  const [bekliyor, setBekliyor] = useState(false)
  const [hata, setHata]         = useState<string | null>(null)

  async function kaydet() {
    if (!isim.trim()) { setHata('Sera adı zorunludur'); return }
    const alanSayi = parseFloat(alan)
    if (isNaN(alanSayi) || alanSayi <= 0) { setHata('Alan pozitif bir sayı olmalıdır'); return }
    setBekliyor(true); setHata(null)
    try {
      if (mod === 'ekle') {
        const veri: SeraEkleInput = { isim: isim.trim(), bitki, alan: alanSayi, esp32_ip: ip.trim() }
        await api.seraEkle(veri)
      } else if (sera) {
        const veri: SeraGuncelleInput = { isim: isim.trim(), bitki, alan: alanSayi, esp32_ip: ip.trim() }
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
        borderRadius: 16, padding: 24, width: '100%', maxWidth: 460,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
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
              {BITKI_SECENEKLER.map(b => (
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
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>ESP32 IP Adresi</label>
            <input
              className="input-field" style={{ width: '100%' }}
              placeholder="ör. 192.168.1.101"
              value={ip}
              onChange={e => setIp(e.target.value)}
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

function CihazEkleModal({ onKapat, onEklendi }: {
  onKapat: () => void
  onEklendi: (sonuc: CihazKayitSonuc) => void
}) {
  const [tesis, setTesis]       = useState('IST01')
  const [seraId, setSeraId]     = useState('s1')
  const [mac, setMac]           = useState('')
  const [tip, setTip]           = useState('WiFi')
  const [firmware, setFirmware] = useState('1.0.0')
  const [bekliyor, setBekliyor] = useState(false)
  const [hata, setHata]         = useState<string | null>(null)

  async function kaydet() {
    if (!tesis.trim() || !seraId.trim()) { setHata('Tesis kodu ve sera ID zorunludur'); return }
    setBekliyor(true); setHata(null)
    try {
      const veri: CihazKayitInput = {
        tesis_kodu: tesis.trim().toUpperCase(),
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Tesis Kodu *</label>
              <input className="input-field" style={{ width: '100%' }} placeholder="IST01"
                value={tesis} onChange={e => setTesis(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Sera ID *</label>
              <input className="input-field" style={{ width: '100%' }} placeholder="s1"
                value={seraId} onChange={e => setSeraId(e.target.value)} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>MAC Adresi</label>
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
              <label style={{ fontSize: 12, color: 'var(--t2)', display: 'block', marginBottom: 5 }}>Firmware</label>
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
export function Ayarlar() {
  const { seralar, saglik, hata, sonGuncelleme } = useData()

  const [formModal, setFormModal]   = useState<FormModal | null>(null)
  const [silModal, setSilModal]     = useState<SeraOzet | null>(null)
  const [yenilemeSayac, setYenilemeSayac] = useState(0)  // force UI refresh

  function yenile() {
    setFormModal(null); setSilModal(null)
    setYenilemeSayac(n => n + 1)  // DataContext 2sn içinde güncelleyecek
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
        <div className="card rounded-xl" style={{ gridColumn: '1 / -1' }}>
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
                          {s.esp32_ip && <span style={{ marginLeft: 8 }}>IP: {s.esp32_ip}</span>}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ textAlign: 'right', marginRight: 8 }}>
                        <div style={{ fontSize: 11, color: 'var(--t2)' }}>ID: {s.id}</div>
                        <div style={{ fontSize: 11, color: 'var(--t3)' }}>
                          {s.sensor ? `${s.sensor.T}°C · ${s.sensor.H}%` : 'Veri yok'}
                        </div>
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
        <div className="card rounded-xl" style={{ gridColumn: '1 / -1' }}>
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
