/**
 * useAgentSocket — production-grade WebSocket hook
 *
 * Features:
 * - Exponential backoff reconnect (1s → 16s max)
 * - Heartbeat ping every 25s to keep connection alive through proxies/load balancers
 * - Intentional disconnect suppresses reconnect
 * - Latest onEvent always called without recreating the socket
 */
import { useEffect, useRef, useCallback, useState } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
const MIN_DELAY_MS = 1000
const MAX_DELAY_MS = 16000
const HEARTBEAT_MS  = 25000

export function useAgentSocket(sessionId, onEvent) {
  const wsRef              = useRef(null)
  const onEventRef         = useRef(onEvent)
  const reconnectTimerRef  = useRef(null)
  const heartbeatTimerRef  = useRef(null)
  const reconnectDelayRef  = useRef(MIN_DELAY_MS)
  const intentionalRef     = useRef(false)   // true when we closed deliberately
  const unmountedRef       = useRef(false)
  const [connected, setConnected] = useState(false)

  // Always call the latest handler without re-creating the socket
  onEventRef.current = onEvent

  const stopHeartbeat = useCallback(() => {
    clearInterval(heartbeatTimerRef.current)
    heartbeatTimerRef.current = null
  }, [])

  const startHeartbeat = useCallback((ws) => {
    stopHeartbeat()
    heartbeatTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_MS)
  }, [stopHeartbeat])

  const connect = useCallback(() => {
    if (unmountedRef.current || !sessionId) return
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }

    let ws
    const token = import.meta.env.VITE_API_KEY || ''
    const url = `${WS_BASE}/ws/${sessionId}${token ? `?token=${token}` : ''}`
    try {
      ws = new WebSocket(url)
    } catch (err) {
      console.error('[WS] Failed to construct WebSocket:', err)
      scheduleReconnect()
      return
    }
    wsRef.current = ws

    ws.onopen = () => {
      if (unmountedRef.current) return
      setConnected(true)
      reconnectDelayRef.current = MIN_DELAY_MS
      startHeartbeat(ws)
      console.log('[WS] Connected:', sessionId)
    }

    ws.onmessage = (e) => {
      if (unmountedRef.current) return
      try {
        const msg = JSON.parse(e.data)
        onEventRef.current?.(msg)
      } catch (err) {
        console.error('[WS] Parse error:', err)
      }
    }

    ws.onclose = (ev) => {
      stopHeartbeat()
      if (unmountedRef.current || intentionalRef.current) return
      setConnected(false)
      console.log(`[WS] Closed (code=${ev.code}) — scheduling reconnect`)
      scheduleReconnect()
    }

    ws.onerror = () => {
      setConnected(false)
      // onclose always fires after onerror — let it schedule reconnect
    }
  }, [sessionId, startHeartbeat, stopHeartbeat]) // eslint-disable-line

  function scheduleReconnect() {
    clearTimeout(reconnectTimerRef.current)
    const delay = reconnectDelayRef.current
    reconnectDelayRef.current = Math.min(delay * 2, MAX_DELAY_MS)
    console.log(`[WS] Reconnecting in ${delay}ms`)
    reconnectTimerRef.current = setTimeout(() => {
      if (!unmountedRef.current) connect()
    }, delay)
  }

  const disconnect = useCallback(() => {
    intentionalRef.current = true
    clearTimeout(reconnectTimerRef.current)
    stopHeartbeat()
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setConnected(false)
  }, [stopHeartbeat])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  // Reset intentional flag and reconnect when sessionId changes
  useEffect(() => {
    unmountedRef.current = false
    intentionalRef.current = false
    reconnectDelayRef.current = MIN_DELAY_MS
    connect()
    return () => {
      unmountedRef.current = true
      disconnect()
    }
  }, [connect, disconnect])

  return { connected, send, disconnect }
}
