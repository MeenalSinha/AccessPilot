const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const VITE_API_KEY = import.meta.env.VITE_API_KEY || ''

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (VITE_API_KEY) {
    headers['x-api-key'] = VITE_API_KEY
  }
  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  startCommand: (command, sessionId, targetUrl, context) =>
    request('/api/v1/command', {
      method: 'POST',
      body: JSON.stringify({
        command,
        session_id: sessionId,
        target_url: targetUrl || null,
        context: context || null,
      }),
    }),

  stopAgent: (sessionId) =>
    request('/api/v1/stop', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }),

  getSession: (sessionId) => request(`/api/v1/session/${sessionId}`),

  getScreenshot: (sessionId) => request(`/api/v1/session/${sessionId}/screenshot`),

  listSessions: () => request('/api/v1/sessions'),

  analyzeScreenshot: (sessionId, screenshotB64) =>
    request('/api/v1/analyze', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, screenshot_b64: screenshotB64 }),
    }),

  getDemoScenarios: () => request('/api/v1/demo-scenarios'),
}
