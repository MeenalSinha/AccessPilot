import React, { useState } from 'react'
import { Maximize2, Eye, Layers, Brain } from 'lucide-react'

export default function ScreenViewer({ screenshot, analysis, step, status }) {
  const [showOverlay, setShowOverlay] = useState(true)
  const [enlarged, setEnlarged]       = useState(false)
  const [imgLoaded, setImgLoaded]     = useState(false)

  const progress  = analysis?.task_progress ?? 0
  const elements  = analysis?.ui_elements ?? []
  const isRunning = status === 'running' || status === 'planning'

  // Reset loaded flag whenever the screenshot changes
  const handleNewScreenshot = (src) => {
    if (!src) return
    setImgLoaded(false)
  }
  React.useEffect(() => { handleNewScreenshot(screenshot) }, [screenshot])

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%' }}>
      {/* Toolbar */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'8px 12px', borderBottom:'1px solid var(--border)', background:'var(--white)', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <Eye size={13} color="var(--text-muted)"/>
          <span style={{ fontSize:12, fontWeight:600, color:'var(--text-secondary)' }}>Screen Capture</span>
          {step > 0 && (
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', background:'var(--surface)', padding:'1px 6px', borderRadius:3, color:'var(--text-muted)' }}>
              Step {step}
            </span>
          )}
        </div>
        <div style={{ display:'flex', gap:4 }}>
          <IconBtn active={showOverlay} onClick={() => setShowOverlay(v=>!v)} title="Toggle element overlay">
            <Layers size={12}/>
          </IconBtn>
          <IconBtn onClick={() => setEnlarged(v=>!v)} title="Enlarge">
            <Maximize2 size={12}/>
          </IconBtn>
        </div>
      </div>

      {/* Screenshot area */}
      <div style={{ flex:1, overflow:'hidden', background:'var(--surface)', position:'relative', display:'flex', alignItems:'center', justifyContent:'center', minHeight:0 }}>
        {!screenshot ? (
          /* Empty state */
          <div style={{ textAlign:'center', color:'var(--text-muted)', padding:24 }}>
            <div style={{ width:48, height:48, border:'2px dashed var(--border-strong)', borderRadius:10, margin:'0 auto 12px', display:'flex', alignItems:'center', justifyContent:'center' }}>
              <Eye size={20} color="var(--border-strong)"/>
            </div>
            <p style={{ fontSize:13, marginBottom:4 }}>
              {isRunning ? 'Capturing screen…' : 'Awaiting agent start'}
            </p>
            <p style={{ fontSize:11 }}>Live screenshots appear here</p>
          </div>
        ) : (
          <>
            {/* Skeleton shimmer while next frame loads */}
            {!imgLoaded && (
              <div style={{
                position:'absolute', inset:0,
                background:'linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 50%, var(--surface) 75%)',
                backgroundSize:'400% 100%',
                animation:'shimmer 1.2s ease infinite',
              }}/>
            )}
            <img
              src={`data:image/jpeg;base64,${screenshot}`}
              alt="Agent screen capture"
              onLoad={() => setImgLoaded(true)}
              style={{ maxWidth:'100%', maxHeight:'100%', objectFit:'contain', display:'block', opacity: imgLoaded ? 1 : 0, transition:'opacity 150ms ease' }}
            />
          </>
        )}

        {/* Scan line while running */}
        {isRunning && screenshot && imgLoaded && (
          <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:'linear-gradient(90deg,transparent,var(--accent),transparent)', animation:'scanline 2s linear infinite', pointerEvents:'none' }}/>
        )}
      </div>

      {/* Analysis strip */}
      {analysis && (
        <div style={{ borderTop:'1px solid var(--border)', background:'var(--white)', padding:'8px 12px', flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'flex-start', gap:10 }}>
            <Brain size={13} color="var(--status-planning)" style={{ marginTop:2, flexShrink:0 }}/>
            <div style={{ flex:1, minWidth:0 }}>
              <p style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.4, marginBottom:4 }}>
                {analysis.reasoning || analysis.suggested_next_action || 'Analysing…'}
              </p>
              <div style={{ display:'flex', alignItems:'center', gap:10, flexWrap:'wrap' }}>
                <Pill label="Elements" value={elements.length} color="var(--accent)"/>
                <Pill label="Progress"  value={`${Math.round(progress*100)}%`} color="var(--success)"/>
                {analysis.current_state && <Pill label={analysis.current_state} color="var(--text-muted)"/>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Enlarged modal */}
      {enlarged && screenshot && (
        <div onClick={() => setEnlarged(false)} style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.6)', zIndex:100, display:'flex', alignItems:'center', justifyContent:'center', padding:24 }}>
          <img
            src={`data:image/jpeg;base64,${screenshot}`}
            alt="Enlarged capture"
            style={{ maxWidth:'90vw', maxHeight:'90vh', objectFit:'contain', borderRadius:8, boxShadow:'0 24px 60px rgba(0,0,0,0.4)' }}
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}

function Pill({ label, value, color }) {
  return (
    <span style={{ display:'flex', alignItems:'center', gap:4, fontSize:11 }}>
      <span style={{ width:5, height:5, borderRadius:'50%', background:color, flexShrink:0 }}/>
      <span style={{ color:'var(--text-muted)' }}>{label}</span>
      {value !== undefined && <span style={{ fontWeight:600, color:'var(--text-secondary)' }}>{value}</span>}
    </span>
  )
}

function IconBtn({ children, onClick, title, active }) {
  return (
    <button onClick={onClick} title={title} style={{ width:26, height:26, display:'flex', alignItems:'center', justifyContent:'center', background:active?'var(--accent-light)':'transparent', color:active?'var(--accent)':'var(--text-muted)', border:'1px solid transparent', borderRadius:5, cursor:'pointer', transition:'var(--transition)' }}>
      {children}
    </button>
  )
}
