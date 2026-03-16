import React from 'react'
import { Loader } from 'lucide-react'

export default function StatusBar({ status, message, stepCount }) {
  const configs = {
    idle: { label: 'Idle', color: 'var(--text-muted)', bg: 'var(--surface)', spin: false },
    planning: { label: 'Planning', color: 'var(--status-planning)', bg: '#f5f3ff', spin: true },
    running: { label: 'Running', color: 'var(--status-running)', bg: 'var(--accent-light)', spin: true },
    completed: { label: 'Completed', color: 'var(--success)', bg: 'var(--success-bg)', spin: false },
    error: { label: 'Error', color: 'var(--error)', bg: 'var(--error-bg)', spin: false },
    stopped: { label: 'Stopped', color: 'var(--text-muted)', bg: 'var(--surface)', spin: false },
  }
  const cfg = configs[status] || configs.idle

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 14px',
      background: cfg.bg,
      border: '1px solid var(--border)',
      borderRadius: 8,
      fontSize: 12.5,
    }}>
      {cfg.spin ? (
        <div style={{ animation: 'spin 1s linear infinite', display: 'flex', color: cfg.color }}>
          <Loader size={13} />
        </div>
      ) : (
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
      )}
      <span style={{ fontWeight: 600, color: cfg.color }}>{cfg.label}</span>
      {message && <span style={{ color: 'var(--text-secondary)' }}>{message}</span>}
      {stepCount > 0 && (
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          {stepCount} actions
        </span>
      )}
    </div>
  )
}
