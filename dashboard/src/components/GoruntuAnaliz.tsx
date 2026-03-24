import { useState, useRef } from 'react'

interface AnalizSonuc {
  saglik_skoru: number
  genel_durum: string
  bulgular: string[]
  oneriler: string[]
  acil_mudahale: boolean
  ozet: string
}

interface Props {
  seraId: string
  seraIsim: string
}

export function GoruntuAnaliz({ seraId, seraIsim }: Props) {
  const [sonuc, setSonuc]         = useState<AnalizSonuc | null>(null)
  const [yukleniyor, setYukleniyor] = useState(false)
  const [hata, setHata]           = useState<string | null>(null)
  const [onizleme, setOnizleme]   = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function analiz(dosya: File) {
    setYukleniyor(true)
    setHata(null)
    setSonuc(null)

    const reader = new FileReader()
    reader.onload = e => setOnizleme(e.target?.result as string)
    reader.readAsDataURL(dosya)

    const form = new FormData()
    form.append('sera_id', seraId)
    form.append('sera_isim', seraIsim)
    form.append('goruntu', dosya)

    try {
      const token = localStorage.getItem('access_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      const r = await fetch('/api/v1/goruntu/analiz', {
        method: 'POST',
        body: form,
        headers,
      })

      const json = await r.json()
      if (!r.ok) {
        throw new Error(json.hata ?? json.detail ?? `HTTP ${r.status}`)
      }
      setSonuc(json.data ?? json)
    } catch (e: unknown) {
      setHata(e instanceof Error ? e.message : String(e))
    } finally {
      setYukleniyor(false)
    }
  }

  const skorRenk = (skor: number) =>
    skor >= 70 ? 'var(--accent)' : skor >= 40 ? 'var(--warn, #f59e0b)' : 'var(--alarm)'

  return (
    <div style={{ marginTop: 8 }}>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={e => {
          const f = e.target.files?.[0]
          if (f) analiz(f)
          e.target.value = ''        // aynı dosya tekrar seçilebilsin
        }}
      />

      {!sonuc && !yukleniyor && (
        <button
          className="btn-ghost"
          style={{ width: '100%', padding: '6px', fontSize: 11 }}
          onClick={() => inputRef.current?.click()}
        >
          📷 Fotoğraf ile Bitki Analizi
        </button>
      )}

      {yukleniyor && (
        <div style={{ textAlign: 'center', padding: '12px', color: 'var(--t2)' }}>
          {onizleme && (
            <img
              src={onizleme}
              style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 4, marginBottom: 8, opacity: 0.6 }}
            />
          )}
          <div className="lbl" style={{ animation: 'pulse 1.5s infinite' }}>
            Claude Vision analiz ediyor…
          </div>
        </div>
      )}

      {hata && (
        <div style={{ borderRadius: 4, padding: '8px 10px', fontSize: 11, color: 'var(--alarm)', background: 'rgba(239,68,68,.08)' }}>
          ⚠ {hata}
          <button
            className="btn-ghost"
            style={{ fontSize: 10, padding: '2px 6px', marginLeft: 8 }}
            onClick={() => { setHata(null); inputRef.current?.click() }}
          >
            Tekrar dene
          </button>
        </div>
      )}

      {sonuc && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {onizleme && (
            <img
              src={onizleme}
              style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 4 }}
            />
          )}

          {/* Skor çubuğu */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1, height: 4, background: 'var(--border2, var(--border))', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                width: `${sonuc.saglik_skoru}%`, height: '100%',
                background: skorRenk(sonuc.saglik_skoru),
                borderRadius: 2, transition: 'width .6s ease',
              }} />
            </div>
            <span className="val" style={{ fontSize: 13, color: skorRenk(sonuc.saglik_skoru) }}>
              {sonuc.saglik_skoru}
            </span>
            <span className="lbl">{sonuc.genel_durum}</span>
          </div>

          {/* Özet */}
          <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.4 }}>{sonuc.ozet}</div>

          {/* Bulgular */}
          {sonuc.bulgular.length > 0 && (
            <div>
              <div className="lbl" style={{ marginBottom: 3 }}>Bulgular</div>
              {sonuc.bulgular.map((b, i) => (
                <div key={i} style={{ fontSize: 10, color: 'var(--t2)', padding: '2px 0' }}>· {b}</div>
              ))}
            </div>
          )}

          {/* Öneriler */}
          {sonuc.oneriler.length > 0 && (
            <div>
              <div className="lbl" style={{ marginBottom: 3 }}>Öneriler</div>
              {sonuc.oneriler.map((o, i) => (
                <div key={i} style={{ fontSize: 10, color: 'var(--accent)', padding: '2px 0' }}>→ {o}</div>
              ))}
            </div>
          )}

          {sonuc.acil_mudahale && (
            <div style={{ borderRadius: 4, padding: '6px 10px', fontSize: 11, color: 'var(--alarm)', fontWeight: 600, background: 'rgba(239,68,68,.08)' }}>
              🚨 Acil müdahale gerekiyor!
            </div>
          )}

          <button
            className="btn-ghost"
            style={{ fontSize: 10, padding: '3px' }}
            onClick={() => { setSonuc(null); setOnizleme(null); inputRef.current?.click() }}
          >
            ↺ Yeni analiz
          </button>
        </div>
      )}
    </div>
  )
}
