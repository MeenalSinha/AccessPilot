import React, { useState, useRef, useEffect } from 'react'
import { Send, Mic, MicOff, Square, ChevronDown, ChevronUp, Globe, History, X } from 'lucide-react'
import { useVoiceInput } from '../hooks/useVoiceInput.js'

const QUICK_COMMANDS = [
  'Find the cheapest flight from Delhi to Mumbai tomorrow',
  'Fill this registration form with my details',
  'Download all invoices from last month',
  'Navigate to settings and enable dark mode',
  'Search for the latest news about AI and summarise',
]

const HISTORY_KEY = 'accesspilot_cmd_history'
const MAX_HISTORY = 20

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') }
  catch { return [] }
}
function saveHistory(cmd, existing) {
  const next = [cmd, ...existing.filter(c => c !== cmd)].slice(0, MAX_HISTORY)
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)) }
  catch {}
  return next
}

export default function CommandInput({ onStart, onStop, isRunning, disabled }) {
  const [command, setCommand]           = useState('')
  const [targetUrl, setTargetUrl]       = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showQuick, setShowQuick]       = useState(false)
  const [showHistory, setShowHistory]   = useState(false)
  const [history, setHistory]           = useState(loadHistory)
  const textareaRef = useRef(null)

  const { listening, supported, start: startVoice, stop: stopVoice } =
    useVoiceInput((text) => setCommand(text))

  const handleSubmit = () => {
    if (!command.trim() || disabled || isRunning) return
    const trimmed = command.trim()
    setHistory(prev => saveHistory(trimmed, prev))
    onStart(trimmed, targetUrl.trim() || null)
    setShowQuick(false)
    setShowHistory(false)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
    if (e.key === 'ArrowUp' && !command && history.length) {
      setCommand(history[0]); e.preventDefault()
    }
  }

  const pick = (cmd) => {
    setCommand(cmd)
    setShowQuick(false)
    setShowHistory(false)
    textareaRef.current?.focus()
  }

  const clearHistory = () => {
    try { localStorage.removeItem(HISTORY_KEY) } catch {}
    setHistory([])
    setShowHistory(false)
  }

  return (
    <div style={{ background:'var(--white)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', overflow:'hidden', boxShadow:'var(--shadow)' }}>
      {/* Main input */}
      <div style={{ padding:'12px 14px 8px' }}>
        <label style={{ fontSize:11, fontWeight:600, color:'var(--text-muted)', letterSpacing:'0.06em', textTransform:'uppercase', display:'block', marginBottom:8 }}>
          Command
        </label>
        <textarea
          ref={textareaRef}
          value={command}
          onChange={e => setCommand(e.target.value)}
          onKeyDown={handleKey}
          disabled={isRunning || disabled}
          placeholder="Describe what the agent should do…"
          rows={3}
          style={{ width:'100%', resize:'none', border:'none', outline:'none', fontFamily:'var(--font-sans)', fontSize:14, lineHeight:1.6, color:'var(--text-primary)', background:'transparent' }}
        />
      </div>

      {/* Quick commands */}
      {showQuick && (
        <div style={{ padding:'0 14px 10px', borderTop:'1px solid var(--surface)' }}>
          <p style={{ fontSize:11, color:'var(--text-muted)', fontWeight:600, letterSpacing:'0.06em', textTransform:'uppercase', margin:'8px 0 6px' }}>Quick commands</p>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {QUICK_COMMANDS.map((cmd, i) => (
              <PickButton key={i} onClick={() => pick(cmd)}>{cmd}</PickButton>
            ))}
          </div>
        </div>
      )}

      {/* Command history */}
      {showHistory && history.length > 0 && (
        <div style={{ padding:'0 14px 10px', borderTop:'1px solid var(--surface)' }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', margin:'8px 0 6px' }}>
            <p style={{ fontSize:11, color:'var(--text-muted)', fontWeight:600, letterSpacing:'0.06em', textTransform:'uppercase' }}>Recent</p>
            <button onClick={clearHistory} style={{ fontSize:10, color:'var(--text-muted)', background:'none', border:'none', cursor:'pointer', display:'flex', alignItems:'center', gap:3 }}>
              <X size={9} /> Clear
            </button>
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {history.slice(0, 8).map((cmd, i) => (
              <PickButton key={i} onClick={() => pick(cmd)}>{cmd}</PickButton>
            ))}
          </div>
        </div>
      )}

      {/* Advanced — target URL */}
      {showAdvanced && (
        <div style={{ padding:'10px 14px', borderTop:'1px solid var(--surface)', background:'var(--off-white)' }}>
          <label style={{ fontSize:11, fontWeight:600, color:'var(--text-muted)', letterSpacing:'0.06em', textTransform:'uppercase', display:'block', marginBottom:6 }}>
            Target URL (optional)
          </label>
          <div style={{ display:'flex', alignItems:'center', gap:6, background:'var(--white)', border:'1px solid var(--border)', borderRadius:6, padding:'6px 10px' }}>
            <Globe size={13} color="var(--text-muted)" />
            <input
              value={targetUrl}
              onChange={e => setTargetUrl(e.target.value)}
              placeholder="https://example.com"
              style={{ flex:1, border:'none', outline:'none', fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-primary)', background:'transparent' }}
            />
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'8px 10px', borderTop:'1px solid var(--surface)', background:'var(--off-white)' }}>
        <div style={{ display:'flex', gap:4 }}>
          <ToolbarBtn onClick={() => { setShowQuick(v=>!v); setShowHistory(false) }} active={showQuick}>
            <span style={{ fontSize:11, fontWeight:600 }}>Quick</span>
            {showQuick ? <ChevronUp size={11}/> : <ChevronDown size={11}/>}
          </ToolbarBtn>

          {history.length > 0 && (
            <ToolbarBtn onClick={() => { setShowHistory(v=>!v); setShowQuick(false) }} active={showHistory}>
              <History size={12}/>
              <span style={{ fontSize:11, fontWeight:600 }}>History</span>
            </ToolbarBtn>
          )}

          <ToolbarBtn onClick={() => setShowAdvanced(v=>!v)} active={showAdvanced}>
            <Globe size={12}/>
            <span style={{ fontSize:11, fontWeight:600 }}>URL</span>
          </ToolbarBtn>

          {supported && (
            <ToolbarBtn onClick={listening ? stopVoice : startVoice} active={listening}
              style={{ color: listening ? 'var(--error)' : undefined }}>
              {listening ? <MicOff size={12}/> : <Mic size={12}/>}
              <span style={{ fontSize:11, fontWeight:600 }}>{listening ? 'Stop' : 'Voice'}</span>
            </ToolbarBtn>
          )}
        </div>

        <div style={{ display:'flex', gap:6 }}>
          {isRunning && (
            <button onClick={onStop} style={{ display:'flex', alignItems:'center', gap:5, background:'var(--error-bg)', color:'var(--error)', border:'1px solid #fecaca', borderRadius:6, padding:'7px 12px', fontSize:12, fontWeight:600, cursor:'pointer' }}>
              <Square size={11} fill="currentColor"/> Stop
            </button>
          )}
          <button
            onClick={handleSubmit}
            disabled={!command.trim() || isRunning || disabled}
            style={{ display:'flex', alignItems:'center', gap:5, background:(!command.trim()||isRunning||disabled)?'var(--surface-2)':'var(--text-primary)', color:(!command.trim()||isRunning||disabled)?'var(--text-muted)':'white', border:'none', borderRadius:6, padding:'7px 14px', fontSize:12, fontWeight:600, cursor:(!command.trim()||isRunning||disabled)?'not-allowed':'pointer', transition:'var(--transition)' }}
          >
            <Send size={11}/> {isRunning ? 'Running…' : 'Run Agent'}
          </button>
        </div>
      </div>
    </div>
  )
}

function PickButton({ children, onClick }) {
  return (
    <button onClick={onClick} style={{ textAlign:'left', background:'var(--surface)', border:'1px solid var(--border)', borderRadius:6, padding:'6px 10px', fontSize:12.5, color:'var(--text-secondary)', cursor:'pointer', transition:'var(--transition)' }}
      onMouseEnter={e=>e.currentTarget.style.background='var(--surface-2)'}
      onMouseLeave={e=>e.currentTarget.style.background='var(--surface)'}>
      {children}
    </button>
  )
}

function ToolbarBtn({ children, onClick, title, active, style: extra }) {
  return (
    <button onClick={onClick} title={title} style={{ display:'flex', alignItems:'center', gap:4, background:active?'var(--accent-light)':'transparent', color:active?'var(--accent)':'var(--text-muted)', border:active?'1px solid var(--accent-mid)':'1px solid transparent', borderRadius:5, padding:'4px 8px', cursor:'pointer', transition:'var(--transition)', ...extra }}
      onMouseEnter={e=>{ if(!active) e.currentTarget.style.background='var(--surface)' }}
      onMouseLeave={e=>{ if(!active) e.currentTarget.style.background='transparent' }}>
      {children}
    </button>
  )
}
