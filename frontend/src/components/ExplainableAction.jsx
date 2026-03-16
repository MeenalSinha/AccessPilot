/**
 * ExplainableAction — full-detail action card shown in the Action Log.
 *
 * Displays:
 *   Action type  |  Target element  |  Reason  |  Confidence bar  |  Grounding source
 *
 * This is what judges see — transparent AI reasoning at every step.
 */
import React, { useState } from 'react'
import {
  MousePointer, Type, ArrowDown, Keyboard, Clock, Globe,
  Target, Brain, ChevronDown, ChevronUp, Zap, Shield, Eye,
} from 'lucide-react'

const ACTION_COLORS = {
  CLICK:    '#2563eb',
  TYPE:     '#16a34a',
  SCROLL:   '#7c3aed',
  PRESS:    '#ea580c',
  WAIT:     '#8a8a84',
  NAVIGATE: '#0284c7',
  HOVER:    '#6366f1',
  SELECT:   '#0891b2',
  CLEAR:    '#dc2626',
}
const ACTION_ICONS = {
  CLICK:    MousePointer, TYPE:  Type,  SCROLL: ArrowDown,
  PRESS:    Keyboard,     WAIT:  Clock, NAVIGATE: Globe,
  HOVER:    MousePointer, SELECT: Target, CLEAR: Target,
}
const GROUNDING_ICONS = {
  cv:       { icon: Eye,   label: 'OpenCV',  color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
  gemini:   { icon: Brain, label: 'Gemini',  color: '#7c3aed', bg: '#f5f3ff', border: '#ddd6fe' },
  combined: { icon: Zap,   label: 'Combined', color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe' },
  none:     { icon: Clock, label: 'Fallback', color: '#8a8a84', bg: '#f5f5f5', border: '#e5e5e5' },
}

function ConfidenceBar({ value = 0 }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#ca8a04' : '#dc2626'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--surface-2)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 300ms ease' }} />
      </div>
      <span style={{ fontSize: 10, fontWeight: 700, color, fontFamily: 'var(--font-mono)', minWidth: 28 }}>
        {pct}%
      </span>
    </div>
  )
}

export default function ExplainableAction({ data, timestamp }) {
  const [expanded, setExpanded] = useState(false)
  const { action, step, target, reason, explanation, confidence, grounding_source, is_irreversible, reasoning } = data

  const actionType  = action?.action_type || 'WAIT'
  const color       = ACTION_COLORS[actionType] || '#8a8a84'
  const IconComp    = ACTION_ICONS[actionType] || MousePointer
  const grounding   = GROUNDING_ICONS[grounding_source] || GROUNDING_ICONS.none
  const GroundIcon  = grounding.icon

  return (
    <div style={{
      borderBottom: '1px solid var(--surface)',
      animation: 'slideIn 150ms ease',
      borderLeft: `3px solid ${color}`,
    }}>
      {/* ── Header row ─────────────────────────────────────────────── */}
      <div
        onClick={() => setExpanded(v => !v)}
        style={{ display: 'flex', gap: 8, padding: '8px 12px', cursor: 'pointer', alignItems: 'flex-start' }}
      >
        {/* Action type badge */}
        <div style={{
          width: 24, height: 24, borderRadius: 4, flexShrink: 0, marginTop: 1,
          background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color,
        }}>
          <IconComp size={12} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Action type + step + irreversible badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3, flexWrap: 'wrap' }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
              color, background: `${color}15`, padding: '1px 6px', borderRadius: 3,
            }}>
              {actionType}
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Step {step}
            </span>
            {is_irreversible && (
              <span style={{
                fontSize: 9, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 2,
                color: '#dc2626', background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: 99, padding: '1px 6px',
              }}>
                <Shield size={8} /> Irreversible
              </span>
            )}
            {action?.mock && (
              <span style={{ fontSize: 9, fontWeight: 600, color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 99, padding: '0 5px' }}>
                CV
              </span>
            )}
            {/* Grounding chip */}
            <span style={{
              fontSize: 9, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 2,
              color: grounding.color, background: grounding.bg,
              border: `1px solid ${grounding.border}`, borderRadius: 99, padding: '1px 6px',
            }}>
              <GroundIcon size={8} /> {grounding.label}
            </span>
          </div>

          {/* Target */}
          {target && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
              <Target size={10} color="var(--text-muted)" />
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                {target}
              </span>
            </div>
          )}

          {/* Explanation */}
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4, marginBottom: 4 }}>
            {explanation || reason}
          </p>

          {/* Confidence bar */}
          {confidence > 0 && <ConfidenceBar value={confidence} />}
        </div>

        {/* Timestamp + expand toggle */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </span>
        </div>
      </div>

      {/* ── Expanded detail ─────────────────────────────────────────── */}
      {expanded && (
        <div style={{ padding: '0 12px 10px 44px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {reason && reason !== explanation && (
            <div style={{ padding: '6px 10px', background: 'var(--accent-light)', borderRadius: 6, border: '1px solid var(--accent-mid)' }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', marginBottom: 2 }}>Reason</p>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{reason}</p>
            </div>
          )}
          {reasoning && (
            <div style={{ padding: '6px 10px', background: 'var(--surface)', borderRadius: 6 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Gemini Reasoning</p>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4, fontStyle: 'italic' }}>{reasoning}</p>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Detail label="Action"    value={actionType} />
            <Detail label="Target"    value={target || '—'} />
            <Detail label="Grounding" value={grounding.label} />
            <Detail label="Confidence" value={`${Math.round((confidence||0)*100)}%`} />
          </div>
        </div>
      )}
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div style={{ fontSize: 11, display: 'flex', gap: 4 }}>
      <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{label}:</span>
      <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{value}</span>
    </div>
  )
}
