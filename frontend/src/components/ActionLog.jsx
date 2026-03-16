import React, { useEffect, useRef } from 'react'
import { Info, AlertTriangle, CheckCircle, XCircle, Brain } from 'lucide-react'
import ExplainableAction from './ExplainableAction.jsx'

const LEVEL_STYLES = {
  info:     { bg: 'transparent',        color: 'var(--text-secondary)', icon: <Info size={11} color="var(--info)" /> },
  success:  { bg: 'var(--success-bg)',  color: 'var(--success)',        icon: <CheckCircle size={11} color="var(--success)" /> },
  warning:  { bg: 'var(--warning-bg)',  color: 'var(--warning)',        icon: <AlertTriangle size={11} color="var(--warning)" /> },
  error:    { bg: 'var(--error-bg)',    color: 'var(--error)',          icon: <XCircle size={11} color="var(--error)" /> },
  analysis: { bg: 'transparent',        color: 'var(--text-muted)',     icon: <Brain size={11} color="var(--status-planning)" /> },
}

function LogEntry({ entry }) {
  // ── Explainable action card ──────────────────────────────────────────
  if (entry.type === 'action') {
    return <ExplainableAction data={entry.data} timestamp={entry.timestamp} />
  }

  // ── Log message ──────────────────────────────────────────────────────
  if (entry.type === 'log') {
    const { level, message } = entry.data
    const style = LEVEL_STYLES[level] || LEVEL_STYLES.info
    return (
      <div style={{ display: 'flex', gap: 8, padding: '5px 12px', background: style.bg, borderBottom: '1px solid var(--surface)', animation: 'slideIn 150ms ease' }}>
        <div style={{ paddingTop: 2, flexShrink: 0 }}>{style.icon}</div>
        <p style={{ fontSize: 12, color: style.color, lineHeight: 1.4, flex: 1 }}>{message}</p>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
          {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>
    )
  }

  // ── Status change ────────────────────────────────────────────────────
  if (entry.type === 'status') {
    const { status, message } = entry.data
    const color = {
      running: 'var(--accent)', completed: 'var(--success)',
      error: 'var(--error)', planning: 'var(--status-planning)',
    }[status] || 'var(--text-muted)'
    return (
      <div style={{ padding: '6px 12px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6, animation: 'slideIn 150ms ease' }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color, textTransform: 'capitalize' }}>{status}:</span>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{message}</span>
      </div>
    )
  }

  return null
}

export default function ActionLog({ entries }) {
  const bottomRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [entries.length])

  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      {entries.length === 0 ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 13, flexDirection: 'column', gap: 8, padding: 24 }}>
          <Brain size={24} color="var(--border-strong)" />
          <span>Agent activity will appear here</span>
        </div>
      ) : (
        <>
          {entries.map((entry, i) => <LogEntry key={i} entry={entry} />)}
          <div ref={bottomRef} />
        </>
      )}
    </div>
  )
}
