import React, { useState, useCallback, useRef, useEffect } from 'react'
import { uuidv4 } from './utils/uuid.js'
import Header from './components/Header.jsx'
import CommandInput from './components/CommandInput.jsx'
import TaskPlanPanel from './components/TaskPlanPanel.jsx'
import ActionLog from './components/ActionLog.jsx'
import ScreenViewer from './components/ScreenViewer.jsx'
import AnalysisPanel from './components/AnalysisPanel.jsx'
import DemoScenarios from './components/DemoScenarios.jsx'
import StatusBar from './components/StatusBar.jsx'
import ReasoningTrail from './components/ReasoningTrail.jsx'
import { useAgentSocket } from './hooks/useAgentSocket.js'
import { api } from './utils/api.js'
import DemoBanner from './components/DemoBanner.jsx'
import ConfirmDialog from './components/ConfirmDialog.jsx'
import { LayoutGrid, ListOrdered, Brain, RefreshCw, BookOpen, AlertTriangle } from 'lucide-react'

// Stable session ID for the lifetime of this browser tab
const SESSION_ID = uuidv4()

// ── Error Boundary ────────────────────────────────────────────────────────────
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, color: 'var(--error)' }}>
          <AlertTriangle size={32} />
          <p style={{ fontWeight: 600, fontSize: 15 }}>Something went wrong</p>
          <pre style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 600, whiteSpace: 'pre-wrap' }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            style={{ padding: '8px 16px', background: 'var(--text-primary)', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
          >
            Dismiss
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [status, setStatus] = useState('idle')
  const [statusMessage, setStatusMessage] = useState('Ready')
  const [plan, setPlan] = useState(null)
  const [screenshot, setScreenshot] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [cvRegions, setCvRegions] = useState(0)
  const [logEntries, setLogEntries] = useState([])
  const [screenshotStep, setScreenshotStep] = useState(0)
  const [leftTab, setLeftTab] = useState('scenarios')
  const [rightTab, setRightTab] = useState('log')
  const [backendOk, setBackendOk] = useState(null)
  const [confirmRequest, setConfirmRequest] = useState(null)  // irreversible action confirmation

  // Use a ref for plan inside the WS event handler to avoid stale closures
  // that would cause the WebSocket to reconnect on every plan update.
  const planRef = useRef(plan)
  planRef.current = plan

  const addLog = useCallback((entry) => {
    setLogEntries(prev => [...prev.slice(-199), entry])
  }, [])

  // ── WebSocket event handler ─────────────────────────────────────────────
  // IMPORTANT: deps array must NOT include plan state — use planRef instead.
  const handleEvent = useCallback((msg) => {
    const { event_type, data, timestamp } = msg

    if (event_type === 'status') {
      setStatus(data.status)
      setStatusMessage(data.message)
      addLog({ type: 'status', data, timestamp })
    } else if (event_type === 'plan') {
      setPlan(data)
      addLog({ type: 'log', data: { level: 'info', message: `Task plan created: ${data.goal}` }, timestamp })
    } else if (event_type === 'screenshot') {
      setScreenshot(data.screenshot)
      setScreenshotStep(data.step)
    } else if (event_type === 'analysis') {
      setAnalysis(data.analysis)
      setCvRegions(data.cv_regions_count || 0)
    } else if (event_type === 'action') {
      addLog({ type: 'action', data, timestamp })
      // Update plan current_step using ref — no stale closure
      setPlan(prev => prev ? { ...prev, current_step: Math.max(0, (data.step || 1) - 1) } : prev)
    } else if (event_type === 'log') {
      addLog({ type: 'log', data, timestamp })
    } else if (event_type === 'error') {
      setStatus('error')
      addLog({ type: 'log', data: { level: 'error', message: data.error }, timestamp })
    } else if (event_type === 'connected') {
      addLog({ type: 'log', data: { level: 'info', message: 'WebSocket connected to agent' }, timestamp })
    } else if (event_type === 'healing_failed') {
      // Self-healing exhausted — agent could not find the element
      addLog({
        type: 'log',
        data: { level: 'error', message: `🔧 Self-heal failed: ${data.message}` },
        timestamp,
      })
    } else if (event_type === 'confirm_required') {
      // Agent wants to perform an irreversible action — show confirmation dialog
      setConfirmRequest(data)
    } else if (event_type === 'pong') {
      // heartbeat — no-op
    }
  }, [addLog]) // plan deliberately excluded — use planRef instead

  const { connected, send } = useAgentSocket(SESSION_ID, handleEvent)

  // Backend health check on mount
  useEffect(() => {
    api.health()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleStart = useCallback(async (command, targetUrl) => {
    if (status === 'running' || status === 'planning') return
    setLogEntries([])
    setPlan(null)
    setScreenshot(null)
    setAnalysis(null)
    setStatus('planning')
    setStatusMessage('Starting agent...')
    setLeftTab('plan')

    try {
      await api.startCommand(command, SESSION_ID, targetUrl, null)
    } catch (err) {
      setStatus('error')
      setStatusMessage(err.message)
      addLog({
        type: 'log',
        data: { level: 'error', message: `Failed to start: ${err.message}` },
        timestamp: new Date().toISOString(),
      })
    }
  }, [status, addLog])

  const handleStop = useCallback(async () => {
    send({ type: 'stop' })
    try { await api.stopAgent(SESSION_ID) } catch (_) {}
    setStatus('stopped')
    setStatusMessage('Agent stopped')
  }, [send])

  const handleDemoSelect = useCallback((scenario) => {
    handleStart(scenario.command, scenario.target_url)
  }, [handleStart])

  const handleClearLog = useCallback(() => setLogEntries([]), [])

  // ── Confirmation handlers for irreversible actions ───────────────────
  const handleConfirmApprove = useCallback(() => {
    send({ type: 'confirm', approved: true })
    setConfirmRequest(null)
  }, [send])

  const handleConfirmDeny = useCallback(() => {
    send({ type: 'confirm', approved: false })
    setConfirmRequest(null)
  }, [send])

  const isRunning = status === 'running' || status === 'planning'
  const actionCount = logEntries.filter(e => e.type === 'action').length

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--off-white)' }}>
        <Header status={status} connected={connected} sessionId={SESSION_ID} />

        {/* Irreversible action confirmation dialog */}
        {confirmRequest && (
          <ConfirmDialog
            request={confirmRequest}
            onApprove={handleConfirmApprove}
            onDeny={handleConfirmDeny}
          />
        )}

        {/* Demo Mode / Gemini status banner */}
        <DemoBanner />

        {/* Backend offline banner */}
        {backendOk === false && (
          <div style={{ background: '#fef9c3', borderBottom: '1px solid #fde047', padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
            <AlertTriangle size={13} color="#854d0e" />
            <span style={{ color: '#854d0e', fontWeight: 600 }}>Backend offline</span>
            <span style={{ color: '#92400e' }}>Start the FastAPI server on localhost:8000 to run the agent.</span>
            <button
              onClick={() => api.health().then(() => setBackendOk(true)).catch(() => {})}
              style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4, background: 'white', border: '1px solid #fde047', borderRadius: 5, padding: '3px 8px', cursor: 'pointer', fontSize: 11, color: '#854d0e' }}
            >
              <RefreshCw size={10} /> Retry
            </button>
          </div>
        )}

        {/* 3-column layout */}
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '300px 1fr 300px', overflow: 'hidden', minHeight: 0 }}>

          {/* LEFT — Command + Plan/Scenarios */}
          <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)', background: 'var(--white)', overflow: 'hidden' }}>
            <div style={{ padding: 12, borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <CommandInput
                onStart={handleStart}
                onStop={handleStop}
                isRunning={isRunning}
                disabled={backendOk === false}
              />
            </div>

            <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <TabBtn active={leftTab === 'scenarios'} onClick={() => setLeftTab('scenarios')} icon={<BookOpen size={12} />}>Scenarios</TabBtn>
              <TabBtn active={leftTab === 'plan'} onClick={() => setLeftTab('plan')} icon={<ListOrdered size={12} />}>
                Plan {plan && <Badge>{plan.steps?.length}</Badge>}
              </TabBtn>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              {leftTab === 'scenarios' && (
                <div style={{ padding: 10 }}>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 10 }}>
                    Demo Scenarios
                  </p>
                  <DemoScenarios onSelect={handleDemoSelect} />
                </div>
              )}
              {leftTab === 'plan' && <TaskPlanPanel plan={plan} />}
            </div>
          </div>

          {/* CENTER — Screen */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--surface)' }}>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <ScreenViewer screenshot={screenshot} analysis={analysis} step={screenshotStep} status={status} />
            </div>
            <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', background: 'var(--white)', flexShrink: 0 }}>
              <StatusBar status={status} message={statusMessage} stepCount={actionCount} />
            </div>
          </div>

          {/* RIGHT — Log + Analysis + Reasoning */}
          <div style={{ display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border)', background: 'var(--white)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <TabBtn active={rightTab === 'log'} onClick={() => setRightTab('log')} icon={<LayoutGrid size={12} />}>
                Log {logEntries.length > 0 && <Badge muted>{logEntries.length}</Badge>}
              </TabBtn>
              <TabBtn active={rightTab === 'reasoning'} onClick={() => setRightTab('reasoning')} icon={<Brain size={12} />}>
                Reasoning {logEntries.filter(e=>e.type==='action').length > 0 && <Badge>{logEntries.filter(e=>e.type==='action').length}</Badge>}
              </TabBtn>
              <TabBtn active={rightTab === 'analysis'} onClick={() => setRightTab('analysis')} icon={<LayoutGrid size={12} />}>CV</TabBtn>
              {rightTab === 'log' && logEntries.length > 0 && (
                <button onClick={handleClearLog} style={{ marginLeft: 'auto', marginRight: 8, fontSize: 10, color: 'var(--text-muted)', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <RefreshCw size={9} /> Clear
                </button>
              )}
            </div>

            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {rightTab === 'log' && <ActionLog entries={logEntries} />}
              {rightTab === 'reasoning' && <ReasoningTrail entries={logEntries} status={status} />}
              {rightTab === 'analysis' && (
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  <AnalysisPanel analysis={analysis} cvRegions={cvRegions} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}

function TabBtn({ active, onClick, children, icon }) {
  return (
    <button onClick={onClick} style={{
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
      padding: '9px 8px', background: active ? 'var(--white)' : 'var(--off-white)',
      color: active ? 'var(--text-primary)' : 'var(--text-muted)',
      border: 'none', borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
      cursor: 'pointer', fontSize: 12, fontWeight: active ? 600 : 400,
      transition: 'var(--transition)', fontFamily: 'var(--font-sans)',
    }}>
      {icon}{children}
    </button>
  )
}

function Badge({ children, muted }) {
  return (
    <span style={{
      background: muted ? 'var(--surface-2)' : 'var(--accent)',
      color: muted ? 'var(--text-secondary)' : 'white',
      borderRadius: 99, padding: '0 5px', fontSize: 10, marginLeft: 3,
    }}>
      {children}
    </span>
  )
}
