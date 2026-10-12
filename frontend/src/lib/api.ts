import { useApp } from './store'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra)
  const { sessionKey, adminToken } = useApp.getState()
  if (sessionKey) h.set('X-XAI-API-Key', sessionKey)
  if (adminToken) h.set('Authorization', `Bearer ${adminToken}`)
  return h
}

async function parseError(res: Response): Promise<ApiError> {
  let message = res.statusText
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail)) message = detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
    else if (body?.error) message = String(body.error)
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 401) window.dispatchEvent(new CustomEvent('vs:unauthorized'))
  return new ApiError(res.status, message)
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init
  const h = headers(rest.headers)
  let body = rest.body
  if (json !== undefined) {
    h.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  }
  const res = await fetch(path, { ...rest, headers: h, body })
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  if (type.includes('application/json')) return (await res.json()) as T
  if (type.startsWith('audio/')) return (await res.blob()) as T
  return (await res.text()) as T
}

export const get = <T,>(path: string) => api<T>(path)
export const post = <T,>(path: string, json?: unknown) => api<T>(path, { method: 'POST', json })
export const put = <T,>(path: string, json?: unknown) => api<T>(path, { method: 'PUT', json })
export const patch = <T,>(path: string, json?: unknown) => api<T>(path, { method: 'PATCH', json })
export const del = <T,>(path: string) => api<T>(path, { method: 'DELETE' })

export function wsUrl(path: string): string {
  const url = new URL(path, window.location.href)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = useApp.getState().adminToken
  if (token) url.searchParams.set('token', token)
  return url.toString()
}
