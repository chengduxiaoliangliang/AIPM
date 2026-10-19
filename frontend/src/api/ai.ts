import request from './request'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AICapabilities {
  user_id: number
  nickname: string
  roles: string[]
  accessible_projects_count: number
  prompt_chips: string[]
  is_deepseek_configured: boolean
  current_session_id: string | null
}

export interface AISession {
  session_id: string
  user_id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AIStatusResponse {
  ai_enabled: boolean
  is_llm_configured: boolean
  redis_connected: boolean
  model_info: {
    provider: string
    model: string
    base_url: string
    max_tokens: number
    temperature: number
    is_configured: boolean
    api_key_preview: string
  }
  session_config: {
    session_ttl_days: number
    max_history_turns: number
    max_sessions_per_user: number
  }
}

// ─── Capabilities & Status ────────────────────────────────────────────────────

export function getAICapabilitiesApi() {
  return request<AICapabilities>({
    url: '/ai/capabilities',
    method: 'GET'
  })
}

export function getAIStatusApi() {
  return request<AIStatusResponse>({
    url: '/ai/status',
    method: 'GET'
  })
}

// ─── LLM Config Management ────────────────────────────────────────────────────

export interface AIConfig {
  api_key_preview: string
  base_url: string
  model: string
  max_tokens: number
  temperature: number
  ai_enabled: boolean
  is_runtime_override: boolean
}

export interface AIConfigUpdatePayload {
  api_key?: string
  base_url?: string
  model?: string
  max_tokens?: number
  temperature?: number
  ai_enabled?: boolean
}

export function getAIConfigApi() {
  return request<AIConfig>({
    url: '/ai/config',
    method: 'GET'
  })
}

export function updateAIConfigApi(payload: AIConfigUpdatePayload) {
  return request<AIConfig>({
    url: '/ai/config',
    method: 'PUT',
    data: payload
  })
}

export function resetAIConfigApi() {
  return request<null>({
    url: '/ai/config/reset',
    method: 'DELETE'
  })
}

// ─── Session Management ───────────────────────────────────────────────────────

export function createSessionApi(title?: string) {
  return request<AISession>({
    url: '/ai/sessions',
    method: 'POST',
    data: { title: title || '' }
  })
}

export function listSessionsApi() {
  return request<AISession[]>({
    url: '/ai/sessions',
    method: 'GET'
  })
}

export function deleteSessionApi(sessionId: string) {
  return request<null>({
    url: `/ai/sessions/${sessionId}`,
    method: 'DELETE'
  })
}

export function getSessionHistoryApi(sessionId: string) {
  return request<HistoryMessage[]>({
    url: `/ai/sessions/${sessionId}/history`,
    method: 'GET'
  })
}

// ─── Chat Streaming ───────────────────────────────────────────────────────────

/**
 * Stream AI Chat Response using Fetch + ReadableStream (SSE).
 * If sessionId is provided, history is managed by the backend (Redis).
 */
export async function streamAIChatApi(
  message: string,
  options: {
    sessionId?: string | null
    history?: Array<{ role: string; content: string }>
    onToken: (token: string) => void
    onFinish: () => void
    onError: (err: any) => void
  }
) {
  const { sessionId, history = [], onToken, onFinish, onError } = options
  const token = localStorage.getItem('aipm_token')
  try {
    const response = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        message,
        session_id: sessionId || null,
        history: sessionId ? [] : history  // Don't send history if session_id manages it
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    if (!reader) {
      throw new Error('No readable stream available')
    }

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6))
            if (data.status === 'streaming' && data.content) {
              onToken(data.content)
            } else if (data.status === 'finished') {
              onFinish()
            }
          } catch (e) {
            // Ignore parse errors on partial chunks
          }
        }
      }
    }
    onFinish()
  } catch (err) {
    onError(err)
  }
}
