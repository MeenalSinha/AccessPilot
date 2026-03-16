import React, { useEffect, useState } from 'react'
import { Play, Globe, FileText, Download, Settings, ChevronRight, Loader } from 'lucide-react'
import { api } from '../utils/api'

const CATEGORY_ICONS = {
  Navigation: <Globe size={13} />,
  'Form Filling': <FileText size={13} />,
  Dashboard: <Download size={13} />,
}

const FALLBACK_SCENARIOS = [
  { id: 'flight', title: 'Flight Search', command: 'Find the cheapest flight from Delhi to Mumbai tomorrow', target_url: 'https://www.google.com/travel/flights', description: 'Searches for flights and identifies cheapest option', steps: 6, category: 'Navigation' },
  { id: 'form', title: 'Form Automation', command: 'Fill this registration form with my details', target_url: 'https://httpbin.org/forms/post', description: 'Automatically fills all form fields', steps: 5, category: 'Form Filling' },
  { id: 'invoice', title: 'Invoice Download', command: 'Download all invoices from last month', target_url: 'https://app.netlify.com', description: 'Applies filters and downloads invoices', steps: 7, category: 'Dashboard' },
  { id: 'darkmode', title: 'Settings Navigation', command: 'Navigate to settings and enable dark mode', target_url: 'https://github.com/settings/appearance', description: 'Navigates to appearance settings', steps: 4, category: 'Navigation' },
]

export default function DemoScenarios({ onSelect }) {
  const [scenarios, setScenarios] = useState(FALLBACK_SCENARIOS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getDemoScenarios()
      .then(d => setScenarios(d.scenarios || FALLBACK_SCENARIOS))
      .catch(() => setScenarios(FALLBACK_SCENARIOS))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
      <div style={{ animation: 'spin 1s linear infinite', display: 'flex' }}><Loader size={13} /></div>
      Loading scenarios...
    </div>
  )

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, padding: 2 }}>
      {scenarios.map(s => (
        <ScenarioCard key={s.id} scenario={s} onSelect={onSelect} />
      ))}
    </div>
  )
}

function ScenarioCard({ scenario, onSelect }) {
  const [hover, setHover] = useState(false)
  return (
    <button
      onClick={() => onSelect(scenario)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        textAlign: 'left', background: hover ? 'var(--accent-light)' : 'var(--white)',
        border: `1px solid ${hover ? 'var(--accent-mid)' : 'var(--border)'}`,
        borderRadius: 8, padding: '12px 13px', cursor: 'pointer',
        transition: 'var(--transition)', display: 'flex', flexDirection: 'column', gap: 6,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: hover ? 'var(--accent)' : 'var(--text-muted)' }}>
          {CATEGORY_ICONS[scenario.category] || <Settings size={13} />}
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            {scenario.category}
          </span>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{scenario.steps} steps</span>
      </div>
      <div>
        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 3 }}>{scenario.title}</p>
        <p style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.4 }}>{scenario.description}</p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: hover ? 'var(--accent)' : 'var(--text-muted)', fontSize: 11, fontWeight: 500, marginTop: 2 }}>
        <Play size={10} fill="currentColor" />
        Run this scenario
        <ChevronRight size={10} />
      </div>
    </button>
  )
}
