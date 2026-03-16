import React from 'react'
import { Activity, Cpu } from 'lucide-react'

export default function Header({ status, connected, sessionId }) {
  const statusColors = {
    idle: '#8a8a84',
    planning: '#7c3aed',
    running: '#2563eb',
    completed: '#16a34a',
    error: '#dc2626',
    stopped: '#8a8a84',
  }
  const color = statusColors[status] || statusColors.idle

  return (
    <header style={{
      height: 'var(--header-height)',
      background: 'var(--white)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 28, height: 28,
          background: 'var(--text-primary)',
          borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Cpu size={15} color="white" />
        </div>
        <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.02em' }}>AccessPilot</span>
        <span style={{
          fontSize: 11, fontWeight: 500, color: 'var(--text-muted)',
          background: 'var(--surface)', padding: '2px 7px', borderRadius: 99,
          border: '1px solid var(--border)', letterSpacing: '0.02em',
        }}>Universal UI Agent</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {sessionId && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {sessionId.slice(0, 8)}
          </span>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: color,
            boxShadow: status === 'running' ? `0 0 0 3px ${color}22` : 'none',
            animation: status === 'running' ? 'pulse 1.5s infinite' : 'none',
          }} />
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
            {status}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Activity size={13} color={connected ? '#16a34a' : '#dc2626'} />
          <span style={{ fontSize: 11, color: connected ? '#16a34a' : '#dc2626' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
    </header>
  )
}
