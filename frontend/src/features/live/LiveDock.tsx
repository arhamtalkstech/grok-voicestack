import * as Tabs from '@radix-ui/react-tabs'
import { ArrowRight, ChevronRight, Maximize2, Mic, MicOff, Minimize2, PhoneOff, Send, Wrench, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { getLiveSession, LiveSession, useLive, type LiveItem } from '../../audio/live'
import { Badge, Button, Field, IconButton, Input, Select, cx } from '../../components/ui'
import { useAgents } from '../../lib/queries'
import { useApp } from '../../lib/store'
import { LiveVoiceprint, Voiceprint } from '../../voiceprint/Voiceprint'

function useSeed(slug: string | null) {
  const agents = useLive((s) => s.agents)
  return useMemo(() => {
    const a = slug ? agents[slug] : undefined
    return { voice: a?.voice_id ?? 'eve', name: a?.name ?? 'agent', speed: a?.speed ?? 1 }
  }, [agents, slug])
}

function Setup() {
  const dock = useApp((s) => s.dock)
  const { data: agents } = useAgents()
  const [agentId, setAgentId] = useState(dock.agentId ?? '')
  const [identity, setIdentity] = useState(() => localStorage.getItem('vs-caller') ?? '')
  const [mode, setMode] = useState<'direct' | 'relay'>(() => (localStorage.getItem('vs-mode') as 'direct' | 'relay') ?? 'direct')
  const status = useLive((s) => s.status)
  const error = useLive((s) => s.error)
  const conversationId = useLive((s) => s.conversationId)

  useEffect(() => {
    if (dock.agentId) setAgentId(dock.agentId)
  }, [dock.agentId])
  const entry = agents?.find((a) => a.is_entry)

  const start = () => {
    localStorage.setItem('vs-caller', identity)
    localStorage.setItem('vs-mode', mode)
    void LiveSession.start({ agentId: agentId || entry?.id, mode, callerIdentity: identity.trim() || undefined, resumeId: dock.resumeId })
  }

  return (
    <div className="flex flex-col gap-5 p-5">
      {status === 'ended' && conversationId && (
        <div className="rounded-2xl border border-line bg-l1 p-4 text-[13px]">
          <p className="font-medium">Conversation saved</p>
          <p className="mt-1 text-fg-3">The transcript, handoffs, and summary are in Conversations.</p>
          <Link to={`/conversations/${conversationId}`} className="mt-3 inline-flex items-center gap-1 text-fg hover:underline">
            Open conversation <ArrowRight className="size-3.5" />
          </Link>
        </div>
      )}
      {error && <p className="rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-[13px] text-danger">{error}</p>}
      {dock.resumeId && <Badge tone="info">Continuing an earlier conversation</Badge>}
      <Field label="Start with" hint="Handoffs from this agent follow the Landscape.">
        <Select value={agentId || entry?.id || ''} onChange={(e) => setAgentId(e.target.value)}>
          {agents?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.is_entry ? ' (entry)' : ''}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Caller identity" hint="Optional. A phone number or email that keys memory across calls, like a caller ID.">
        <Input placeholder="+14155550100" value={identity} onChange={(e) => setIdentity(e.target.value)} />
      </Field>
      <Field
        label="Audio path"
        hint={mode === 'direct' ? 'Your browser talks to xAI with a short-lived token. Lowest latency.' : 'Audio goes through this server. Use when browsers cannot reach api.x.ai.'}
      >
        <div className="grid grid-cols-2 gap-1 rounded-pill border border-line-2 p-1" role="radiogroup">
          {(['direct', 'relay'] as const).map((m) => (
            <button
              key={m}
              role="radio"
              aria-checked={mode === m}
              onClick={() => setMode(m)}
              className={cx('h-8 rounded-pill text-[13px] capitalize transition-colors', mode === m ? 'bg-l3 text-fg' : 'text-fg-3 hover:text-fg-2')}
            >
              {m === 'direct' ? 'Direct' : 'Relay'}
            </button>
          ))}
        </div>
      </Field>
      <Button variant="primary" className="h-11" onClick={start} loading={status === 'connecting'} disabled={!agents?.length}>
        {status === 'ended' ? 'Start another call' : 'Start call'}
      </Button>
      <p className="text-xs leading-relaxed text-fg-3">Your microphone is used only during the call. Edits you save in the builder apply to a live call immediately.</p>
    </div>
  )
}

function ToolCard({ item }: { item: LiveItem }) {
  const [open, setOpen] = useState(false)
  const data = item.data ?? {}
  const status = data.status as string
  return (
    <div className="rounded-xl border border-line bg-l1 text-[12.5px]">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Wrench className="size-3.5 text-fg-3" />
        <span className="font-mono">{item.text}</span>
        <span className="ml-auto flex items-center gap-2">
          {status === 'running' ? <span className="shimmer font-mono text-[11px]">running</span> : <Badge tone={status === 'ok' ? 'success' : 'danger'}>{status}</Badge>}
          {typeof data.latency_ms === 'number' && <span className="font-mono text-[11px] text-fg-3">{data.latency_ms} ms</span>}
          <ChevronRight className={cx('size-3.5 text-fg-3 transition-transform', open && 'rotate-90')} />
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2 font-mono text-[11.5px] text-fg-2">
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(data.args ?? {}, null, 2)}</pre>
          {data.output != null && <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all text-fg-3">{String(data.output)}</pre>}
        </div>
      )}
    </div>
  )
}

function Transcript() {
  const items = useLive((s) => s.items)
  const agents = useLive((s) => s.agents)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Braced on purpose: Chrome's scrollIntoView returns a Promise, which React would treat as a cleanup.
    void end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [items.length])
  if (!items.length) return <p className="px-1 py-6 text-center text-[13px] text-fg-3">Say hello, or type below.</p>
  return (
    <div className="flex flex-col gap-3">
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <motion.div key={item.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            {item.kind === 'user' && (
              <div className="ml-auto max-w-[88%] rounded-3xl rounded-br-lg border border-line bg-l2 px-3.5 py-2 text-[13.5px]">{item.text}</div>
            )}
            {item.kind === 'assistant' && (
              <div className="max-w-[94%]">
                <div className="mb-1 flex items-center gap-1.5 text-[11.5px] text-fg-3">
                  {item.agent && agents[item.agent] && <Voiceprint seed={{ voice: agents[item.agent].voice_id, name: agents[item.agent].name, speed: agents[item.agent].speed }} size={14} />}
                  {item.agent ? agents[item.agent]?.name ?? item.agent : 'Agent'}
                  {item.data?.force_message ? <span className="font-mono">· verbatim</span> : null}
                </div>
                <p className="text-[13.5px] leading-relaxed">{item.text}</p>
              </div>
            )}
            {item.kind === 'tool' && <ToolCard item={item} />}
            {item.kind === 'handoff' && <HandoffBanner item={item} />}
            {(item.kind === 'system' || item.kind === 'dtmf') && <p className="text-center font-mono text-[11.5px] text-fg-3">{item.kind === 'dtmf' ? `keypad ${item.text}` : item.text}</p>}
            {item.kind === 'error' && <p className="rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-[12.5px] text-danger">{item.text}</p>}
          </motion.div>
        ))}
      </AnimatePresence>
      <div ref={end} />
    </div>
  )
}

function HandoffBanner({ item }: { item: LiveItem }) {
  const agents = useLive((s) => s.agents)
  const d = (item.data ?? {}) as { from?: string; to?: string; reason?: string; summary?: string; fields?: Record<string, unknown> }
  const name = (slug?: string) => (slug ? agents[slug]?.name ?? slug : '')
  return (
    <div className="my-1 rounded-2xl border border-line-2 bg-l1 p-3">
      <div className="flex items-center justify-center gap-2 text-[12.5px]">
        <span className="text-fg-2">{name(d.from)}</span>
        <ArrowRight className="size-3.5 text-live" />
        <span className="font-medium">{name(d.to)}</span>
      </div>
      {(d.summary || d.reason) && <p className="mt-1.5 text-center text-[12px] text-fg-3">{d.summary || d.reason}</p>}
      {d.fields && Object.keys(d.fields).length > 0 && (
        <div className="mt-2 flex flex-wrap justify-center gap-1">
          {Object.entries(d.fields).map(([k, v]) => (
            <span key={k} className="rounded-pill bg-l3 px-2 py-0.5 font-mono text-[11px] text-fg-2">
              {k}: {String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function StatePanel() {
  const context = useLive((s) => s.context)
  const memory = useLive((s) => s.memory)
  const config = useLive((s) => s.sessionConfig)
  const active = useLive((s) => s.activeAgent)
  const agents = useLive((s) => s.agents)
  return (
    <div className="flex flex-col gap-4 text-[13px]">
      <div>
        <p className="eyebrow mb-1.5">Active agent</p>
        <p>{active ? agents[active]?.name ?? active : '—'}</p>
      </div>
      <div>
        <p className="eyebrow mb-1.5">Collected context</p>
        {Object.keys(context).length ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-[12px]">
            {Object.entries(context).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-fg-3">{k}</dt>
                <dd className="break-all">{String(v)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-fg-3">Fields collected at handoffs appear here.</p>
        )}
      </div>
      {memory && (
        <div>
          <p className="eyebrow mb-1.5">Caller memory</p>
          <p className="whitespace-pre-wrap text-fg-2">{memory}</p>
        </div>
      )}
      {config && (
        <details>
          <summary className="eyebrow cursor-pointer">session.update sent</summary>
          <pre className="mt-2 max-h-96 overflow-auto rounded-xl bg-inset p-3 font-mono text-[11px] text-fg-2">{JSON.stringify(config, null, 2)}</pre>
        </details>
      )}
    </div>
  )
}

function EventsPanel() {
  const events = useLive((s) => s.events)
  const [filter, setFilter] = useState('')
  const shown = events.filter((e) => !filter || e.type.includes(filter)).slice(-200)
  return (
    <div className="flex flex-col gap-2">
      <Input mono placeholder="Filter event types" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-8" />
      <ol className="flex flex-col font-mono text-[11px]">
        {shown.map((e, i) => (
          <li key={i} className="flex gap-2 border-b border-line py-1">
            <span className="w-14 shrink-0 text-fg-4">{new Date(e.t).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' })}</span>
            <span className={cx('w-6 shrink-0', e.dir === 'out' ? 'text-info' : e.dir === 'ui' ? 'text-fg-3' : 'text-fg-2')}>{e.dir === 'out' ? '→' : e.dir === 'in' ? '←' : '·'}</span>
            <span className="break-all text-fg-2">{e.type}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function LiveStage() {
  const active = useLive((s) => s.activeAgent)
  const agents = useLive((s) => s.agents)
  const caption = useLive((s) => s.caption)
  const thinking = useLive((s) => s.thinking)
  const agentSpeaking = useLive((s) => s.agentSpeaking)
  const userSpeaking = useLive((s) => s.userSpeaking)
  const muted = useLive((s) => s.muted)
  const ttfa = useLive((s) => s.ttfa)
  const status = useLive((s) => s.status)
  const seed = useSeed(active)
  const session = getLiveSession()
  const getLevel = useMemo(() => () => getLiveSession()?.getOutLevel() ?? 0, [])
  const [micLevel, setMicLevel] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setMicLevel(getLiveSession()?.getMicLevel() ?? 0), 80)
    return () => clearInterval(id)
  }, [])
  const avg = ttfa.length ? Math.round(ttfa.reduce((a, b) => a + b, 0) / ttfa.length) : null
  const state = status === 'connecting' ? 'Connecting' : thinking ? 'Working on it' : agentSpeaking ? 'Speaking' : userSpeaking ? 'Listening' : 'Your turn'

  return (
    <div className="flex flex-col items-center gap-3 border-b border-line px-5 pb-5 pt-4">
      <LiveVoiceprint seed={seed} size={196} getLevel={getLevel} speaking={agentSpeaking} />
      <div className="text-center">
        <AnimatePresence mode="wait">
          <motion.p key={active ?? 'none'} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="text-[15px] font-medium">
            {active ? agents[active]?.name ?? active : '—'}
          </motion.p>
        </AnimatePresence>
        <p className={cx('mt-0.5 text-[12.5px]', thinking ? 'shimmer' : 'text-fg-3')}>
          {state}
          {active && agents[active] ? <span className="font-mono text-fg-4"> · {agents[active].voice_id} · {agents[active].speed}×</span> : null}
        </p>
      </div>
      <p className="min-h-10 max-w-full text-center text-[13px] leading-relaxed text-fg-2" aria-live="polite">
        {caption}
      </p>
      <div className="flex w-full items-center gap-2">
        <IconButton label={muted ? 'Unmute' : 'Mute'} onClick={() => session?.setMuted(!muted)} className={cx('border border-line-2', muted && 'text-danger')}>
          {muted ? <MicOff className="size-4" /> : <Mic className="size-4" />}
        </IconButton>
        <div className="h-1 flex-1 overflow-hidden rounded-pill bg-l3" aria-label="Microphone level">
          <div className="h-full rounded-pill bg-fg-2 transition-[width] duration-75" style={{ width: `${Math.min(100, micLevel * 600)}%` }} />
        </div>
        {avg != null && <Badge>{avg} ms first audio</Badge>}
        <Button variant="danger" size="sm" icon={<PhoneOff className="size-3.5" />} onClick={() => void session?.end()}>
          End
        </Button>
      </div>
    </div>
  )
}

function Composer() {
  const [text, setText] = useState('')
  return (
    <form
      className="flex items-center gap-2 border-t border-line p-3"
      onSubmit={(e) => {
        e.preventDefault()
        getLiveSession()?.sendText(text)
        setText('')
      }}
    >
      <Input placeholder="Type instead of speaking" value={text} onChange={(e) => setText(e.target.value)} className="rounded-pill" />
      <IconButton label="Send" type="submit" disabled={!text.trim()} className="border border-line-2">
        <Send className="size-4" />
      </IconButton>
    </form>
  )
}

export function LiveDock() {
  const status = useLive((s) => s.status)
  const closeDock = useApp((s) => s.closeDock)
  const expanded = useApp((s) => s.dock.expanded)
  const toggle = useApp((s) => s.toggleDockExpanded)
  const live = status === 'live' || status === 'connecting' || status === 'ending'

  return (
    <div className="flex h-full w-full flex-col md:w-[var(--dock)]" style={expanded ? { width: '100%' } : undefined}>
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-4">
        <p className="eyebrow">Live preview</p>
        {live && <Badge tone="live">{status === 'connecting' ? 'connecting' : 'live'}</Badge>}
        <div className="ml-auto flex items-center">
          <IconButton label={expanded ? 'Narrow' : 'Widen'} onClick={toggle} className="hidden md:inline-flex">
            {expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </IconButton>
          <IconButton label="Close preview" onClick={closeDock}>
            <X className="size-4" />
          </IconButton>
        </div>
      </div>
      {!live ? (
        <div className="scroll-thin flex-1 overflow-y-auto">
          <Setup />
        </div>
      ) : (
        <>
          <LiveStage />
          <Tabs.Root defaultValue="transcript" className="flex min-h-0 flex-1 flex-col">
            <Tabs.List className="flex gap-1 border-b border-line px-3 py-2">
              {['transcript', 'state', 'events'].map((t) => (
                <Tabs.Trigger key={t} value={t} className="rounded-pill px-3 py-1 text-[12.5px] capitalize text-fg-3 data-[state=active]:bg-l2 data-[state=active]:text-fg">
                  {t}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <Tabs.Content value="transcript" className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">
              <Transcript />
            </Tabs.Content>
            <Tabs.Content value="state" className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">
              <StatePanel />
            </Tabs.Content>
            <Tabs.Content value="events" className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">
              <EventsPanel />
            </Tabs.Content>
          </Tabs.Root>
          <Composer />
        </>
      )}
    </div>
  )
}
