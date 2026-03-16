import React, { useState, useEffect } from 'react'
import { api } from '../utils/api.js'
import { Info, X, CheckCircle, AlertCircle } from 'lucide-react'

/**
 * DemoBanner — shown when the backend is in Demo Mode (no GCP credentials).
 * Fetched from /health on mount. Transparent to users about what's real vs mocked.
 */
export default function DemoBanner() {
  const [health, setHealth]   = useState(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  if (!health || dismissed) return null
  if (health.vertex_available) return null   // Live mode — no banner needed

  return (
    <div style={{
      background: '#fffbeb',
      borderBottom: '1px solid #fde68a',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
    }}>
      <Info size={15} color="#b45309" style={{ flexShrink: 0, marginTop: 1 }} />
      <div style={{ flex: 1, fontSize: 12.5, color: '#92400e', lineHeight: 1.5 }}>
        <strong style={{ color: '#78350f' }}>Demo Mode</strong>
        {' — '}
        Playwright browser and OpenCV are fully operational.
        Gemini AI is mocked using real computer vision on live screenshots.
        {' '}
        <span style={{ color: '#b45309' }}>
          To enable live Gemini: set <code style={{ background: '#fef3c7', padding: '1px 4px', borderRadius: 3 }}>GOOGLE_CLOUD_PROJECT</code> in <code style={{ background: '#fef3c7', padding: '1px 4px', borderRadius: 3 }}>backend/.env</code>.
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <Chip ok label="Browser" />
          <Chip ok label="OpenCV" />
          <Chip ok={false} label="Gemini" />
        </div>
        <button onClick={() => setDismissed(true)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#b45309', padding: 2, display: 'flex' }}>
          <X size={14} />
        </button>
      </div>
    </div>
  )
}

function Chip({ ok, label }) {
  return (
    <span style={{
      display: 'flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600,
      background: ok ? '#f0fdf4' : '#fff7ed',
      color: ok ? '#15803d' : '#c2410c',
      border: `1px solid ${ok ? '#bbf7d0' : '#fed7aa'}`,
      borderRadius: 99, padding: '2px 7px',
    }}>
      {ok
        ? <CheckCircle size={10} />
        : <AlertCircle size={10} />
      }
      {label}
    </span>
  )
}
