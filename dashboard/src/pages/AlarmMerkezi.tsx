import { useState } from 'react'
import { useData } from '../context/DataContext'
import { durumBadgeClass, durumLabel } from '../components/Sidebar'
import type { Durum } from '../types'

type Filtre = 'hepsi' | 'UYARI' | 'ALARM' | 'ACIL_DURDUR'

function sure(baslangic: string, bitis?: string): string {
  const ms = new Date(bitis ?? Date.now()).getTime() - new Date(baslangic).getTime()
  const sn = Math.floor(ms / 1000)
  if (sn < 60) return `${sn}sn`
  const dk = Math.floor(sn / 60)
  if (dk < 60) return `${dk}dk`
  return `${Math.floor(dk / 60)}sa ${dk % 60}dk`
}

export function AlarmMerkezi() {
  const { alarmlar, alarmGecmis, alarmOnayla } = useData()
  const [filtre, setFiltre] = useState<Filtre>('hepsi')

  const filtreliGecmis = alarmGecmis.filter(a =>
    filtre === 'hepsi' || a.durum === filtre
  )

  const durumSayilari: Record<string, number> = {
    UYARI:       alarmGecmis.filter(a => a.durum === 'UYARI').length,
    ALARM:       alarmGecmis.filter(a => a.durum === 'ALARM').length,
    ACIL_DURDUR: alarmGecmis.filter(a => a.durum === 'ACIL_DURDUR').length,
  }

  return (
    <div className="page-root">
      <div className="mb-6">
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--t1)' }}>Alarm Merkezi</h1>
        <p style={{ fontSize: 13, color: 'var(--t3)', marginTop: 2 }}>Uyarı ve alarm geçmişi</p>
      </div>

      {/* Özet satırı */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {([
          { durum: 'UYARI' as Durum,       renk: 'var(--warn)',  icon: '⚠️' },
          { durum: 'ALARM' as Durum,       renk: 'var(--alarm)', icon: '🔴' },
          { durum: 'ACIL_DURDUR' as Durum, renk: 'var(--crit)',  icon: '🚨' },
        ]).map(({ durum, renk, icon }) => (
          <div key={durum} className="card rounded-xl p-4 flex items-center gap-3 metric-bar-top" style={{ borderTopColor: renk }}>
            <span style={{ fontSize: 24 }}>{icon}</span>
            <div>
              <div style={{ fontSize: 24, fontWeight: 700, color: renk }}>{durumSayilari[durum]}</div>
              <div style={{ fontSize: 12, color: 'var(--t3)' }}>{durumLabel(durum)}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Aktif alarmlar */}
      {alarmlar.length > 0 && (
        <div className="card rounded-xl mb-6">
          <div
            style={{
              padding: '12px 16px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <span style={{ color: 'var(--alarm)', fontSize: 14, fontWeight: 600, animation: 'pulse 2s infinite' }}>
              🚨 Aktif Alarmlar ({alarmlar.length})
            </span>
          </div>
          <div>
            {alarmlar.map(a => {
              const rowClass = a.durum === 'ACIL_DURDUR' ? 'alarm-row-acil' : a.durum === 'ALARM' ? 'alarm-row-alarm' : 'alarm-row-uyari'
              return (
              <div key={a.sera_id} className={`table-row ${rowClass}`} style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className={`${durumBadgeClass(a.durum)} rounded-full px-2 py-0.5 text-xs font-semibold`}>
                  {durumLabel(a.durum)}
                </span>
                <span style={{ fontWeight: 600, color: 'var(--t1)' }}>{a.isim}</span>
                {a.sensor && (
                  <span style={{ fontSize: 12, color: 'var(--t2)' }}>
                    T:{a.sensor.T}°C · H:{a.sensor.H}% · CO₂:{a.sensor.co2}ppm
                  </span>
                )}
                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--t3)' }}>ŞU AN</span>
              </div>
              )
            })}
          </div>
        </div>
      )}

      {alarmlar.length === 0 && (
        <div
          className="card rounded-xl mb-6 flex items-center gap-3"
          style={{ padding: '14px 20px' }}
        >
          <span style={{ fontSize: 18 }}>✅</span>
          <span style={{ color: 'var(--accent)', fontSize: 14 }}>Tüm seralar normal — aktif alarm yok</span>
        </div>
      )}

      {/* Alarm geçmişi */}
      <div className="card rounded-xl">
        <div
          style={{
            padding: '12px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}
        >
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--t1)' }}>Alarm Geçmişi</span>
          <div className="flex gap-1">
            {(['hepsi', 'UYARI', 'ALARM', 'ACIL_DURDUR'] as Filtre[]).map(f => (
              <button
                key={f}
                className={`btn-ghost ${filtre === f ? 'active' : ''}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => setFiltre(f)}
              >
                {f === 'hepsi' ? 'Hepsi' : durumLabel(f as Durum)}
              </button>
            ))}
          </div>
        </div>

        {filtreliGecmis.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--t3)' }}>
            {filtre === 'hepsi' ? 'Henüz alarm kaydı yok' : `${durumLabel(filtre as Durum)} kaydı yok`}
          </div>
        ) : (
          <div>
            {/* Tablo başlığı */}
            <div
              style={{
                display: 'grid', gridTemplateColumns: '100px 1fr 80px 80px 90px 80px',
                padding: '8px 16px', fontSize: 11, color: 'var(--t3)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span>SEVIYE</span>
              <span>SERA</span>
              <span>BAŞLANGIC</span>
              <span>SÜRE</span>
              <span>DURUM</span>
              <span>İŞLEM</span>
            </div>
            {filtreliGecmis.map(a => (
              <div
                key={a.id}
                className="table-row"
                style={{
                  display: 'grid', gridTemplateColumns: '100px 1fr 80px 80px 90px 80px',
                  padding: '10px 16px', alignItems: 'center',
                  opacity: a.bitis ? 0.6 : 1,
                }}
              >
                <span className={`${durumBadgeClass(a.durum)} rounded-full px-2 py-0.5 text-xs font-semibold inline-flex`} style={{ width: 'fit-content' }}>
                  {durumLabel(a.durum)}
                </span>
                <span style={{ fontWeight: 500, color: 'var(--t1)', fontSize: 13 }}>{a.sera_isim}</span>
                <span style={{ fontSize: 11, color: 'var(--t3)' }}>
                  {new Date(a.baslangic).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span style={{ fontSize: 11, color: 'var(--t2)' }}>{sure(a.baslangic, a.bitis)}</span>
                <span style={{ fontSize: 11, color: a.bitis ? 'var(--accent)' : 'var(--alarm)' }}>
                  {a.bitis ? '✓ Çözüldü' : '● Devam ediyor'}
                </span>
                <div>
                  {!a.onaylandi && (
                    <button
                      className="btn-ghost"
                      style={{ padding: '3px 8px', fontSize: 11 }}
                      onClick={() => alarmOnayla(a.id)}
                    >
                      Onayla
                    </button>
                  )}
                  {a.onaylandi && (
                    <span style={{ fontSize: 11, color: 'var(--t3)' }}>✓ Onaylandı</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
