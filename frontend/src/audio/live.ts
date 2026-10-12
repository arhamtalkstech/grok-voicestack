import { create } from 'zustand'
import { post, wsUrl } from '../lib/api'
import { AudioEngine, base64ToInt16, bytesToBase64 } from './engine'

export type LiveStatus = 'idle' | 'connecting' | 'live' | 'ending' | 'ended' | 'error'

export interface LiveItem {
  id: string
  kind: 'user' | 'assistant' | 'handoff' | 'tool' | 'system' | 'error' | 'dtmf'
  agent?: string | null
  text: string
  data?: Record<string, unknown>
  at: number
}

export interface LiveAgent {
  id: string
  name: string
  voice_id: string
  speed: number
}

interface LiveState {
  status: LiveStatus
  mode: 'direct' | 'relay'
  conversationId: string | null
  agents: Record<string, LiveAgent>
  activeAgent: string | null
  previousAgent: string | null
  items: LiveItem[]
  caption: string
  thinking: boolean
  userSpeaking: boolean
  agentSpeaking: boolean
  muted: boolean
  ttfa: number[]
  context: Record<string, unknown>
  memory: string | null
  sessionConfig: Record<string, unknown> | null
  events: { t: number; dir: 'in' | 'out' | 'ui'; type: string; data?: unknown }[]
  error: string | null
  lastHandoff: { from: string; to: string; at: number } | null
}

const initial: LiveState = {
  status: 'idle',
  mode: 'direct',
  conversationId: null,
  agents: {},
  activeAgent: null,
  previousAgent: null,
  items: [],
  caption: '',
  thinking: false,
  userSpeaking: false,
  agentSpeaking: false,
  muted: false,
  ttfa: [],
  context: {},
  memory: null,
  sessionConfig: null,
  events: [],
  error: null,
  lastHandoff: null,
}

export const useLive = create<LiveState>(() => ({ ...initial }))
const set = useLive.setState
const FORWARD = new Set([
  'conversation.created',
  'session.updated',
  'input_audio_buffer.speech_started',
  'input_audio_buffer.speech_stopped',
  'input_audio_buffer.timeout_triggered',
  'conversation.item.input_audio_transcription.completed',
  'response.created',
  'response.output_audio.delta',
  'response.output_audio_transcript.done',
  'response.function_call_arguments.done',
  'response.done',
  'mcp_list_tools.completed',
  'mcp_list_tools.failed',
  'response.mcp_call.in_progress',
  'response.mcp_call.completed',
  'response.mcp_call.failed',
  'error',
])

function log(dir: 'in' | 'out' | 'ui', type: string, data?: unknown) {
  if (type === 'response.output_audio.delta' || type === 'input_audio_buffer.append') return
  set((s) => ({ events: [...s.events.slice(-299), { t: Date.now(), dir, type, data }] }))
}

function addItem(item: Omit<LiveItem, 'at'>) {
  set((s) => {
    const idx = s.items.findIndex((i) => i.id === item.id)
    if (idx >= 0) {
      const items = s.items.slice()
      items[idx] = { ...items[idx], ...item }
      return { items }
    }
    return { items: [...s.items, { ...item, at: Date.now() }] }
  })
}

let current: LiveSession | null = null

export function getLiveSession() {
  return current
}

export class LiveSession {
  private engine = new AudioEngine()
  private control: WebSocket | null = null
  private xai: WebSocket | null = null
  private earlyAudio: ArrayBuffer[] = []
  private xaiOpen = false
  private audioSeq = 0
  private itemStart = new Map<string, number>()
  private currentItem: string | null = null
  private closed = false
  private forwardedAudio = new Set<string>()
  mode: 'direct' | 'relay'

  constructor(mode: 'direct' | 'relay') {
    this.mode = mode
  }

  getOutLevel = () => this.engine.outLevel()
  getMicLevel = () => this.engine.micLevel()

  static async start(opts: { agentId?: string; mode: 'direct' | 'relay'; callerIdentity?: string; resumeId?: string }) {
    if (current) await current.end()
    const session = new LiveSession(opts.mode)
    current = session
    set({ ...initial, status: 'connecting', mode: opts.mode })
    try {
      await session.open(opts)
    } catch (err) {
      set({ status: 'error', error: err instanceof Error ? err.message : String(err) })
      await session.teardown()
    }
    return session
  }

  private async open(opts: { agentId?: string; mode: 'direct' | 'relay'; callerIdentity?: string; resumeId?: string }) {
    // Start the mic before the network, buffering audio until the socket is open.
    this.engine.onPcm = (pcm) => this.sendAudio(pcm)
    this.engine.onPlayback = (playing) => {
      set({ agentSpeaking: playing })
      this.controlSend({ kind: 'playback', playing, seq: this.audioSeq })
    }
    await this.engine.start()

    const created = await post<{
      conversation_id: string
      ws_path: string
      realtime: { url: string; token: string; subprotocol_prefix: string } | null
    }>('/api/sessions', {
      entry_agent_id: opts.agentId || null,
      mode: opts.mode,
      caller_identity: opts.callerIdentity || null,
      resume_conversation_id: opts.resumeId || null,
    })
    set({ conversationId: created.conversation_id })

    await new Promise<void>((resolve, reject) => {
      const ws = new WebSocket(wsUrl(created.ws_path))
      ws.binaryType = 'arraybuffer'
      this.control = ws
      ws.onmessage = (e) => this.onControl(e.data, resolve)
      ws.onerror = () => reject(new Error('Could not open the session socket'))
      ws.onclose = (e) => {
        if (!this.closed && e.code >= 4000) set({ status: 'error', error: e.reason || `Session closed (${e.code})` })
        void this.teardown()
      }
    })

    if (opts.mode === 'direct' && created.realtime) {
      const rt = created.realtime
      const xai = new WebSocket(rt.url, [`${rt.subprotocol_prefix}${rt.token}`])
      this.xai = xai
      xai.onopen = () => {
        this.xaiOpen = true
        this.controlSend({ kind: 'xai_open' })
        for (const chunk of this.earlyAudio) this.sendAudio(chunk)
        this.earlyAudio = []
        set({ status: 'live' })
      }
      xai.onmessage = (e) => {
        if (typeof e.data !== 'string') return
        const event = JSON.parse(e.data)
        this.onXai(event)
        if (event.type === 'response.output_audio.delta') {
          // The server only needs the first audio delta per response (latency metric, voice lock).
          if (this.forwardedAudio.has(event.response_id)) return
          this.forwardedAudio.add(event.response_id)
          this.controlSend({ kind: 'xai_event', event: { type: event.type, response_id: event.response_id, item_id: event.item_id }, playing: true })
        } else if (FORWARD.has(event.type)) {
          this.controlSend({ kind: 'xai_event', event, playing: this.engine.playing })
        }
      }
      xai.onerror = () => set({ error: 'The connection to xAI failed' })
      xai.onclose = (e) => {
        if (!this.closed) {
          this.controlSend({ kind: 'xai_closed', reason: e.reason || `xai_closed_${e.code}` })
          addItem({ id: `close-${Date.now()}`, kind: 'system', text: `xAI closed the connection${e.reason ? `: ${e.reason}` : ''}` })
        }
      }
    } else {
      set({ status: 'live' })
    }
  }

  private onControl(raw: string | ArrayBuffer, onReady: () => void) {
    if (typeof raw !== 'string') return
    const msg = JSON.parse(raw)
    if (msg.kind === 'ready') {
      set({ agents: msg.agents, activeAgent: msg.entry_agent })
      onReady()
    } else if (msg.kind === 'command') {
      log('out', msg.event.type, msg.event)
      this.xaiSend(msg.event)
    } else if (msg.kind === 'xai_event') {
      this.audioSeq = msg.seq ?? this.audioSeq
      this.onXai(msg.event)
    } else if (msg.kind === 'ui') {
      this.onUi(msg.event)
    }
  }

  private onXai(event: { type: string; [k: string]: any }) {
    log('in', event.type, event.type.includes('delta') ? undefined : event)
    switch (event.type) {
      case 'response.output_audio.delta':
      case 'response.audio.delta': {
        const pcm = base64ToInt16(event.delta)
        if (event.item_id && !this.itemStart.has(event.item_id)) this.itemStart.set(event.item_id, this.engine.queued)
        this.currentItem = event.item_id ?? this.currentItem
        this.engine.push(pcm)
        break
      }
      case 'response.output_audio_transcript.delta':
        set((s) => ({ caption: s.caption + (event.delta ?? '') }))
        break
      case 'response.created':
        set({ caption: '' })
        break
      case 'response.done':
        set({ caption: '' })
        break
      case 'input_audio_buffer.speech_started':
        set({ userSpeaking: true })
        this.bargeIn()
        break
      case 'input_audio_buffer.speech_stopped':
        set({ userSpeaking: false })
        break
      case 'error':
        addItem({ id: `err-${Date.now()}`, kind: 'error', text: event.error?.message ?? 'Realtime error' })
        break
    }
  }

  private bargeIn() {
    if (!this.engine.playing || !this.currentItem) return
    const start = this.itemStart.get(this.currentItem) ?? 0
    const playedMs = Math.max(0, Math.round(((this.engine.played - start) / 24000) * 1000))
    this.engine.clear()
    const truncate = { type: 'conversation.item.truncate', item_id: this.currentItem, content_index: 0, audio_end_ms: playedMs }
    if (this.mode === 'direct') this.xaiSend(truncate)
    else this.controlSend({ kind: 'client_event', event: truncate })
    set({ caption: '' })
  }

  private onUi(event: { type: string; [k: string]: any }) {
    log('ui', event.type, event)
    switch (event.type) {
      case 'turn': {
        const t = event.turn
        if (t.kind === 'handoff') break
        if (t.kind === 'tool') {
          // Voice Stack's own tools already render from tool.started/finished; show xAI-side tools here.
          if (!t.data?.server_side) break
          addItem({ id: t.id, kind: 'tool', agent: t.agent, text: t.text, data: { ...t.data, status: t.data.ok === false ? 'error' : 'ok' } })
          break
        }
        addItem({ id: t.id, kind: t.kind, agent: t.agent, text: t.text, data: t.data })
        break
      }
      case 'tool.started':
        addItem({ id: event.call_id, kind: 'tool', agent: event.agent, text: event.name, data: { args: event.args, status: 'running' } })
        break
      case 'tool.finished':
        addItem({
          id: event.call_id,
          kind: 'tool',
          agent: event.agent,
          text: event.name,
          data: { ...(useLive.getState().items.find((i) => i.id === event.call_id)?.data ?? {}), status: event.ok ? 'ok' : 'error', output: event.output, latency_ms: event.latency_ms },
        })
        break
      case 'handoff':
        addItem({ id: `handoff-${event.at}`, kind: 'handoff', agent: event.to, text: `${event.from} → ${event.to}`, data: event })
        set((s) => ({ context: { ...s.context, ...(event.fields ?? {}) }, lastHandoff: { from: event.from, to: event.to, at: Date.now() } }))
        break
      case 'agent.active':
        set((s) => ({ previousAgent: s.activeAgent, activeAgent: event.agent }))
        break
      case 'session.config':
        set({ sessionConfig: event.session })
        break
      case 'thinking':
        set({ thinking: !!event.on })
        break
      case 'metric':
        if (event.name === 'time_to_first_audio_ms') set((s) => ({ ttfa: [...s.ttfa.slice(-19), event.value] }))
        break
      case 'memory.loaded':
        set({ memory: event.text })
        break
      case 'transfer.started':
        addItem({ id: `xfer-${Date.now()}`, kind: 'system', text: `Transferring to ${event.destination} (${event.uri})` })
        break
      case 'transfer.finished':
        addItem({
          id: `xfer-done-${Date.now()}`,
          kind: 'system',
          text: event.simulated ? `Transfer to ${event.destination} simulated in preview` : event.ok ? `Transferred to ${event.destination}` : `Transfer failed: ${event.error}`,
        })
        break
      case 'tool.config_error':
      case 'error':
        addItem({ id: `err-${Date.now()}-${Math.random()}`, kind: 'error', text: event.message })
        break
      case 'session.end':
        set({ status: 'ended' })
        void this.teardown()
        break
    }
  }

  private sendAudio(pcm: ArrayBuffer) {
    if (this.mode === 'relay') {
      if (this.control?.readyState === WebSocket.OPEN) this.control.send(pcm)
      return
    }
    if (!this.xaiOpen) {
      this.earlyAudio.push(pcm)
      if (this.earlyAudio.length > 50) this.earlyAudio.shift()
      return
    }
    this.xaiSend({ type: 'input_audio_buffer.append', audio: bytesToBase64(pcm) })
  }

  private xaiSend(event: unknown) {
    if (this.xai?.readyState === WebSocket.OPEN) this.xai.send(JSON.stringify(event))
  }

  private controlSend(msg: unknown) {
    if (this.control?.readyState === WebSocket.OPEN) this.control.send(JSON.stringify(msg))
  }

  sendText(text: string) {
    if (!text.trim()) return
    this.controlSend({ kind: 'text', text })
  }

  setMuted(muted: boolean) {
    this.engine.muted = muted
    set({ muted })
  }

  async end() {
    if (this.closed) return
    set({ status: 'ending' })
    this.controlSend({ kind: 'hangup' })
    await new Promise((r) => setTimeout(r, 150))
    await this.teardown()
    set({ status: 'ended' })
  }

  private async teardown() {
    if (this.closed) return
    this.closed = true
    try {
      this.xai?.close()
      this.control?.close()
    } catch {
      /* already closed */
    }
    await this.engine.stop()
    if (current === this) current = null
    set((s) => ({ status: s.status === 'error' ? 'error' : 'ended', agentSpeaking: false, userSpeaking: false, thinking: false }))
  }
}
