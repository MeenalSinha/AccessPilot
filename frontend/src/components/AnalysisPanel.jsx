import React, { useState } from 'react'
import { MousePointer, Type, Link, Menu, Table, Image, AlignLeft, ChevronDown, ChevronUp, BarChart2 } from 'lucide-react'

const TYPE_ICONS = {
  button: <MousePointer size={11} />,
  input: <Type size={11} />,
  link: <Link size={11} />,
  menu: <Menu size={11} />,
  table: <Table size={11} />,
  icon: <Image size={11} />,
  text: <AlignLeft size={11} />,
  dropdown: <ChevronDown size={11} />,
}

const TYPE_COLORS = {
  button: '#2563eb',
  input: '#16a34a',
  link: '#dc2626',
  menu: '#7c3aed',
  table: '#ca8a04',
  icon: '#0284c7',
  text: '#8a8a84',
  dropdown: '#ea580c',
}

export default function AnalysisPanel({ analysis, cvRegions }) {
  const [expanded, setExpanded] = useState(true)

  if (!analysis) return (
    <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 13, textAlign: 'center' }}>
      <BarChart2 size={24} color="var(--border-strong)" style={{ display: 'block', margin: '0 auto 8px' }} />
      No analysis yet
    </div>
  )

  const elements = analysis.ui_elements || []
  const byType = elements.reduce((acc, el) => {
    const t = el.element_type || 'other'
    acc[t] = (acc[t] || 0) + 1
    return acc
  }, {})

  return (
    <div>
      {/* Page state */}
      <div style={{ padding: '10px 14px', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>Page State</p>
        <p style={{ fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.4 }}>{analysis.page_description || 'Unknown'}</p>
        {analysis.current_state && (
          <span style={{ display: 'inline-block', marginTop: 5, fontSize: 11, fontWeight: 500, background: 'var(--accent-light)', color: 'var(--accent)', padding: '2px 7px', borderRadius: 99, border: '1px solid var(--accent-mid)' }}>
            {analysis.current_state}
          </span>
        )}
      </div>

      {/* Element type summary */}
      {Object.keys(byType).length > 0 && (
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
            Detected Elements ({elements.length})
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {Object.entries(byType).map(([type, count]) => (
              <span key={type} style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontSize: 11, padding: '3px 8px', borderRadius: 99,
                background: `${TYPE_COLORS[type] || '#8a8a84'}15`,
                color: TYPE_COLORS[type] || '#8a8a84',
                border: `1px solid ${TYPE_COLORS[type] || '#8a8a84'}30`,
                fontWeight: 500,
              }}>
                {TYPE_ICONS[type] || <MousePointer size={11} />}
                {type} &times;{count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* CV detection */}
      {cvRegions > 0 && (
        <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }} />
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            CV engine found <strong style={{ color: 'var(--text-primary)' }}>{cvRegions}</strong> additional interactive regions
          </p>
        </div>
      )}

      {/* Element list */}
      <div>
        <button
          onClick={() => setExpanded(v => !v)}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}
        >
          Element Details
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {expanded && elements.slice(0, 12).map((el, i) => (
          <div key={i} style={{ padding: '6px 14px', borderTop: '1px solid var(--surface)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <div style={{ color: TYPE_COLORS[el.element_type] || 'var(--text-muted)', paddingTop: 1, flexShrink: 0 }}>
              {TYPE_ICONS[el.element_type] || <MousePointer size={11} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {el.label || el.element_type}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0, fontFamily: 'var(--font-mono)' }}>
                  {Math.round((el.confidence || 1) * 100)}%
                </span>
              </div>
              {el.description && (
                <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.3 }}>{el.description}</p>
              )}
            </div>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', flexShrink: 0 }}>
              {el.x?.toFixed(0)}%,{el.y?.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
