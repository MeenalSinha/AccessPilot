import React from 'react'
import { CheckCircle, Circle, Loader, XCircle, ChevronRight } from 'lucide-react'

function StepIcon({ status }) {
  if (status === 'completed') return <CheckCircle size={14} color="var(--success)" />
  if (status === 'running') return (
    <div style={{ animation: 'spin 1s linear infinite', display: 'flex' }}>
      <Loader size={14} color="var(--accent)" />
    </div>
  )
  if (status === 'failed') return <XCircle size={14} color="var(--error)" />
  return <Circle size={14} color="var(--border-strong)" />
}

export default function TaskPlanPanel({ plan, currentStep }) {
  if (!plan) return (
    <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
      No active task plan
    </div>
  )

  return (
    <div>
      {/* Goal */}
      <div style={{ padding: '14px 16px', background: 'var(--accent-light)', borderBottom: '1px solid var(--accent-mid)' }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>Goal</p>
        <p style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.5 }}>{plan.goal}</p>
      </div>

      {/* Progress bar */}
      <div style={{ padding: '10px 16px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ flex: 1, height: 3, background: 'var(--surface-2)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${plan.steps?.length ? ((plan.current_step || 0) / plan.steps.length) * 100 : 0}%`,
            background: 'var(--accent)',
            borderRadius: 99,
            transition: 'width 400ms ease',
          }} />
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
          {plan.current_step || 0} / {plan.steps?.length || 0}
        </span>
      </div>

      {/* Steps */}
      <div style={{ padding: '10px 0 6px' }}>
        {(plan.steps || []).map((step, i) => {
          const isCurrent = i === (plan.current_step || 0)
          const isDone = i < (plan.current_step || 0)
          const stepStatus = isDone ? 'completed' : isCurrent ? 'running' : 'pending'

          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '7px 16px',
              background: isCurrent ? 'var(--accent-light)' : 'transparent',
              borderLeft: isCurrent ? '2px solid var(--accent)' : '2px solid transparent',
              transition: 'var(--transition)',
            }}>
              <div style={{ paddingTop: 1, flexShrink: 0 }}>
                <StepIcon status={stepStatus} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: isCurrent ? 'var(--accent)' : 'var(--text-muted)',
                    minWidth: 20,
                  }}>
                    {String(step.step_number).padStart(2, '0')}
                  </span>
                  <span style={{
                    fontSize: 13,
                    color: isCurrent ? 'var(--text-primary)' : isDone ? 'var(--text-muted)' : 'var(--text-secondary)',
                    fontWeight: isCurrent ? 500 : 400,
                    lineHeight: 1.4,
                  }}>
                    {step.description}
                  </span>
                </div>
                {isCurrent && step.reasoning && (
                  <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4, marginLeft: 26 }}>
                    {step.reasoning}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
