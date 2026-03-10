import { useState } from 'react'
import { useData } from '../context/DataContext'

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

const BITKI_EMOJI: Record<string, string> = { Domates: '🍅', Biber: '🌶️', Marul: '🥬' }

export function Ayarlar() {
  const { seralar, saglik, hata, sonGuncelleme } = useData()

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
    <div className="page-root">
      <div className="mb-6">
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Ayarlar</h1>
        <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Sistem yapılandırması ve bildirimler</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Sera listesi */}
        <div className="card rounded-xl">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
            🏠 Sera Listesi
          </div>
          {seralar.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)' }}>Veri yükleniyor…</div>
          ) : seralar.map(s => (
            <div key={s.id} className="table-row" style={{ padding: '12px 16px' }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span style={{ fontSize: 22 }}>{BITKI_EMOJI[s.bitki] ?? '🌱'}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>{s.isim}</div>
                    <div style={{ fontSize: 12, color: 'var(--t3)' }}>{s.bitki} · {s.alan} m²</div>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 12, color: 'var(--t2)' }}>ID: {s.id}</div>
                  <div style={{ fontSize: 11, color: 'var(--t3)' }}>
                    {s.sensor
                      ? `${s.sensor.T}°C · ${s.sensor.H}%`
                      : 'Veri yok'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bildirim ayarları */}
        <div className="card rounded-xl">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
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
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
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
              ['Endpoint',  'http://localhost:5000'],
              ['API Versiyonu', '/api/v1/'],
              ['Auth',      'X-API-Key (devre dışı)'],
              ['Rate Limit', '60 istek/dakika'],
              ['Docs',      'http://localhost:5000/docs'],
              ['Uptime',    saglik?.uptime_fmt ?? '—'],
              ['Alarm',     `${saglik?.alarm_sayisi ?? 0} aktif`],
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
                  Backend başlatma:{' '}
                  <code style={{ color: 'var(--t2)' }}>python -m sera_ai --demo --api</code>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sistem bilgisi */}
        <div className="card rounded-xl">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>
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
  )
}
