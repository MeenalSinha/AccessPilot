/**
 * ConfirmDialog — confirmation modal for:
 *   1. Irreversible actions (payment, delete, send, purchase)
 *   2. Low-confidence actions (AI confidence < 70%)
 *
 * Auto-denies when countdown expires.
 */
import React, { useEffect, useState } from 'react'
import { Shield, AlertTriangle, CheckCircle, XCircle, Clock, Brain } from 'lucide-react'

export default function ConfirmDialog({ request, onApprove, onDeny }) {
  const timeout   = request?.timeout ?? 30
  const [countdown, setCountdown] = useState(Math.round(timeout))
  const isLowConf = request?.low_confidence === true
  const confPct   = request?.confidence != null ? Math.round(request.confidence * 100) : null

  useEffect(() => {
    if (!request) return
    setCountdown(Math.round(timeout))
    const id = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { clearInterval(id); onDeny(); return 0 }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [request, timeout, onDeny])

  if (!request) return null

  const accentColor = isLowConf ? '#ca8a04' : '#dc2626'
  const lightBg     = isLowConf ? '#fffbeb' : '#fef2f2'
  const borderColor = isLowConf ? '#fde68a' : '#fecaca'
  const darkText    = isLowConf ? '#92400e' : '#991b1b'
  const Icon        = isLowConf ? Brain : Shield

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, animation: 'fadeIn 150ms ease',
    }}>
      <div style={{
        background: 'var(--white)', borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-lg)', maxWidth: 440, width: '100%',
        border: '1px solid var(--border)', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', background: lightBg, borderBottom: `1px solid ${borderColor}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: borderColor, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Icon size={16} color={accentColor} />
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: darkText }}>
              {isLowConf ? 'Low Confidence — Confirm Action' : 'Irreversible Action Detected'}
            </p>
            <p style={{ fontSize: 11, color: accentColor }}>
              {isLowConf
                ? `Agent is only ${confPct}% confident — please verify`
                : 'This action cannot be undone'}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: accentColor }}>
            <Clock size={12} />
            <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{countdown}s</span>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 20px 16px' }}>
          {/* Confidence indicator for low-confidence case */}
          {isLowConf && confPct != null && (
            <div style={{ marginBottom: 14, padding: '10px 12px', background: '#fffbeb', borderRadius: 8, border: '1px solid #fde68a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#92400e' }}>Agent Confidence</span>
                <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: confPct >= 70 ? '#16a34a' : '#ca8a04' }}>{confPct}%</span>
              </div>
              <div style={{ height: 6, background: '#fef3c7', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{ width: `${confPct}%`, height: '100%', background: confPct >= 70 ? '#16a34a' : '#ca8a04', borderRadius: 99 }} />
              </div>
            </div>
          )}

          {/* Action detail */}
          <div style={{ marginBottom: 14 }}>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Proposed Action
            </p>
            <div style={{ padding: '10px 12px', background: 'var(--surface)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', background: lightBg, color: accentColor, padding: '1px 6px', borderRadius: 3 }}>
                  {request.action_type}
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {request.target}
                </span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {request.reason}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: lightBg, borderRadius: 8, border: `1px solid ${borderColor}` }}>
            <AlertTriangle size={14} color={accentColor} style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 12, color: darkText, lineHeight: 1.4 }}>{request.message}</p>
          </div>
        </div>

        {/* Countdown bar */}
        <div style={{ height: 3, background: 'var(--surface-2)', margin: '0 20px 16px' }}>
          <div style={{ height: '100%', width: `${(countdown / timeout) * 100}%`, background: accentColor, borderRadius: 99, transition: 'width 1s linear' }} />
        </div>

        {/* Buttons */}
        <div style={{ padding: '0 20px 20px', display: 'flex', gap: 10 }}>
          <button onClick={onDeny} style={{ flex: 1, padding: '10px 0', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <XCircle size={14} /> Deny
          </button>
          <button onClick={onApprove} style={{ flex: 1, padding: '10px 0', background: accentColor, border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <CheckCircle size={14} /> Approve
          </button>
        </div>
      </div>
    </div>
  )
}
