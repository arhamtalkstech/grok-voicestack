import { ArrowLeft, ArrowRight, Globe, Phone, Play, Trash2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Badge, Button, Empty, ErrorNote, Input, Select, cx } from '../../components/ui'
import { del, get, useAgents, useConversation, useConversations, useConversationState, useInvalidate } from '../../lib/queries'
import { useApp } from '../../lib/store'
import type { Agent, ConversationDetail, Turn } from '../../lib/types'
import { Voiceprint } from '../../voiceprint/Voiceprint'

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString()
}

function duration(start: string, end: string | null) {
  if (!end) return null
  const s = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

function AgentChain({ ids, agents }: { ids: string[]; agents: Map<string, Agent> }) {
  return (
    <span className="flex items-center gap-1">
      {ids.map((id, i) => {
        const a = agents.get(id)
        return (
          <span key={`${id}-${i}`} className="flex items-center gap-1">
            {i > 0 && <ArrowRight className="size-3 text-fg-4" />}
            {a ? <Voiceprint seed={{ voice: a.voice_id, name: a.name, speed: a.speed }} size={16} /> : null}
            <span className="text-[12.5px] text-fg-2">{a?.name ?? 'removed agent'}</span>
          </span>
        )
      })}
    </span>
  )
}

function List() {
  const [q, setQ] = useState('')
  const [channel, setChannel] = useState('')
  const [agentId, setAgentId] = useState('')
  const { data, isLoading, error } = useConversations({ q, channel, agent_id: agentId, limit: '100' })
  const { data: agentList } = useAgents()
  const agents = new Map((agentList ?? []).map((a) => [a.id, a]))
  const navigate = useNavigate()
  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-5 py-8 md:px-10">
        <h1 className="display text-[34px]">Conversations</h1>
        <p className="mt-1 text-[13px] text-fg-3">Every preview and phone call, as one thread across all the agents it passed through.</p>
        <div className="mt-6 grid gap-2 sm:grid-cols-[1fr_160px_200px]">
          <Input placeholder="Search transcripts, summaries, numbers" value={q} onChange={(e) => setQ(e.target.value)} />
          <Select value={channel} onChange={(e) => setChannel(e.target.value)} aria-label="Channel">
            <option value="">All channels</option>
            <option value="web">Web preview</option>
            <option value="sip">Phone (SIP)</option>
          </Select>
          <Select value={agentId} onChange={(e) => setAgentId(e.target.value)} aria-label="Agent">
            <option value="">All agents</option>
            {agentList?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </div>
        <ErrorNote error={error} />
        <div className="mt-6">
          {!isLoading && !data?.items.length ? (
            <Empty title="No conversations yet">Start a call from the top bar. It shows up here with its transcript, handoffs, and summary.</Empty>
          ) : (
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="eyebrow border-b border-line">
                  <th className="py-2 pr-4 font-normal">Started</th>
                  <th className="py-2 pr-4 font-normal">Caller</th>
                  <th className="hidden py-2 pr-4 font-normal md:table-cell">Agents</th>
                  <th className="hidden py-2 pr-4 font-normal lg:table-cell">Summary</th>
                  <th className="py-2 font-normal">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((c) => (
                  <tr key={c.id} onClick={() => navigate(`/conversations/${c.id}`)} className="cursor-pointer border-b border-line transition-colors hover:bg-l1">
                    <td className="py-3 pr-4 align-top">
                      <span className="flex items-center gap-2">
                        {c.channel === 'sip' ? <Phone className="size-3.5 text-fg-3" /> : <Globe className="size-3.5 text-fg-3" />}
                        {ago(c.started_at)}
                      </span>
                    </td>
                    <td className="py-3 pr-4 align-top font-mono text-[12px] text-fg-2">{c.from_number ?? c.contact ?? '—'}</td>
                    <td className="hidden py-3 pr-4 align-top md:table-cell">
                      <AgentChain ids={c.agents_visited.length ? c.agents_visited : [c.entry_agent_id ?? '']} agents={agents} />
                    </td>
                    <td className="hidden max-w-md py-3 pr-4 align-top text-fg-3 lg:table-cell">
                      <span className="line-clamp-2">{c.summary || `${c.turn_count} turns`}</span>
                    </td>
                    <td className="py-3 align-top">
                      {c.status === 'live' ? (
                        <Badge tone="live">live</Badge>
                      ) : c.status === 'error' ? (
                        <Badge tone="danger">error</Badge>
                      ) : c.disposition ? (
                        <Badge tone={c.disposition === 'resolved' ? 'success' : 'neutral'}>{c.disposition}</Badge>
                      ) : (
                        <Badge>ended</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

function ToolTurn({ turn }: { turn: Turn }) {
  const [open, setOpen] = useState(false)
  const d = turn.data as { args?: unknown; output?: string; ok?: boolean; latency_ms?: number; server_side?: boolean }
  return (
    <div className="rounded-xl border border-line bg-l1 text-[12px]">
      <button className="flex w-full items-center gap-2 px-3 py-1.5 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="font-mono">{turn.text}</span>
        {d.server_side && <span className="font-mono text-[10.5px] text-fg-4">ran at xAI</span>}
        <span className="ml-auto flex items-center gap-2">
          {d.ok === false ? <Badge tone="danger">failed</Badge> : <Badge tone="success">ok</Badge>}
          {typeof d.latency_ms === 'number' && <span className="font-mono text-[10.5px] text-fg-3">{d.latency_ms} ms</span>}
        </span>
      </button>
      {open && (
        <div className="space-y-1.5 border-t border-line px-3 py-2 font-mono text-[11px] text-fg-2">
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(d.args ?? {}, null, 2)}</pre>
          {d.output && <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all text-fg-3">{d.output}</pre>}
        </div>
      )}
    </div>
  )
}

function EventLog({ id }: { id: string }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const { data } = useQuery({
    queryKey: ['conversation-events', id],
    queryFn: () => get<{ total: number; items: { id: number; direction: string; type: string; payload: unknown; created_at: string }[] }>(`/api/conversations/${id}/events?limit=2000`),
    enabled: open,
  })
  const [expanded, setExpanded] = useState<number | null>(null)
  return (
    <div className="mt-10 rounded-2xl border border-line">
      <button className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="text-[14px] font-medium">Realtime event log</span>
        <span className="text-xs text-fg-3">{open ? `${data?.total ?? '…'} events` : 'Every event to and from xAI, except audio'}</span>
      </button>
      {open && (
        <div className="border-t border-line p-4">
          <Input mono placeholder="Filter by event type" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-8" />
          <ol className="mt-3 max-h-[480px] overflow-auto font-mono text-[11px]">
            {data?.items
              .filter((e) => !filter || e.type.includes(filter))
              .map((e) => (
                <li key={e.id} className="border-b border-line">
                  <button className="flex w-full gap-3 py-1 text-left" onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                    <span className="w-20 shrink-0 text-fg-4">{new Date(e.created_at).toLocaleTimeString()}</span>
                    <span className={cx('w-8 shrink-0', e.direction === 'out' ? 'text-info' : 'text-fg-3')}>{e.direction === 'out' ? 'out' : 'in'}</span>
                    <span className="break-all text-fg-2">{e.type}</span>
                  </button>
                  {expanded === e.id && <pre className="mb-2 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-inset p-2 text-fg-3">{JSON.stringify(e.payload, null, 2)}</pre>}
                </li>
              ))}
            {data && !data.items.length && <li className="py-3 text-fg-3">No events were recorded for this conversation.</li>}
          </ol>
        </div>
      )}
    </div>
  )
}

function Lanes({ conv, agents }: { conv: ConversationDetail; agents: Map<string, Agent> }) {
  const laneIds = [...new Set([conv.entry_agent_id, ...conv.agents_visited, ...conv.turns.map((t) => t.agent_id)].filter(Boolean) as string[])]
  const cols = laneIds.length + 1
  const lane = (t: Turn) => (t.kind === 'user' || t.kind === 'dtmf' ? 0 : laneIds.indexOf(t.agent_id ?? '') + 1)
  const name = (id: string) => agents.get(id)?.name ?? conv.agents[id]?.name ?? 'removed agent'
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[640px]">
        <div className="sticky top-0 z-[1] grid border-b border-line bg-bg py-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          <p className="eyebrow px-3">Caller</p>
          {laneIds.map((id) => {
            const a = agents.get(id)
            return (
              <p key={id} className="flex items-center gap-1.5 px-3 text-[12px] text-fg-2">
                {a && <Voiceprint seed={{ voice: a.voice_id, name: a.name, speed: a.speed }} size={14} />}
                {name(id)}
              </p>
            )
          })}
        </div>
        <div className="relative">
          <div className="pointer-events-none absolute inset-0 grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
            {Array.from({ length: cols }, (_, i) => (
              <div key={i} className={cx(i > 0 && 'border-l border-dashed border-line')} />
            ))}
          </div>
          {conv.turns.map((t) =>
            t.kind === 'handoff' ? (
              <div key={t.id} className="relative my-3 px-3">
                <div className="rounded-2xl border border-line-2 bg-l1 px-4 py-2.5 text-center text-[12.5px]">
                  <span className="text-fg-2">Handoff </span>
                  {t.text}
                  {typeof t.data.summary === 'string' && t.data.summary && <p className="mt-1 text-[12px] text-fg-3">{t.data.summary}</p>}
                  {t.data.fields != null && Object.keys(t.data.fields as object).length > 0 && (
                    <div className="mt-1.5 flex flex-wrap justify-center gap-1">
                      {Object.entries(t.data.fields as Record<string, unknown>).map(([k, v]) => (
                        <span key={k} className="rounded-pill bg-l3 px-2 py-0.5 font-mono text-[11px] text-fg-2">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div key={t.id} className="relative grid py-1.5" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
                <div style={{ gridColumnStart: lane(t) + 1, gridColumnEnd: `span ${Math.min(2, cols - lane(t))}` }} className="px-3">
                  {t.kind === 'tool' ? (
                    <ToolTurn turn={t} />
                  ) : (
                  <div className={cx('rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed', t.kind === 'user' ? 'border border-line bg-l2' : t.kind === 'dtmf' ? 'font-mono text-fg-3' : 'bg-l1')}>
                    {t.kind === 'dtmf' ? `keypad ${t.text}` : t.text}
                    {t.data?.input === 'text' && <span className="ml-2 font-mono text-[10.5px] text-fg-4">typed</span>}
                  </div>
                  )}
                </div>
              </div>
            ),
          )}
        </div>
      </div>
    </div>
  )
}

function Detail({ id }: { id: string }) {
  const { data: conv, error } = useConversation(id)
  const { data: state } = useConversationState(id)
  const { data: agentList } = useAgents()
  const agents = new Map((agentList ?? []).map((a) => [a.id, a]))
  const openDock = useApp((s) => s.openDock)
  const dockOpen = useApp((s) => s.dock.open)
  const invalidate = useInvalidate()
  const navigate = useNavigate()
  if (error) return <div className="p-8"><ErrorNote error={error} /></div>
  if (!conv) return null
  const dur = duration(conv.started_at, conv.ended_at)
  return (
    <div className="flex h-full">
      <div className="scroll-thin min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-5 py-8 md:px-10">
          <Link to="/conversations" className="inline-flex items-center gap-1 text-[13px] text-fg-3 hover:text-fg">
            <ArrowLeft className="size-3.5" /> Conversations
          </Link>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow">
                {conv.channel === 'sip' ? 'Phone call' : 'Web preview'} · {new Date(conv.started_at).toLocaleString()}
                {dur ? ` · ${dur}` : ''}
              </p>
              <h1 className="display mt-2 text-[28px]">{conv.from_number ?? conv.contact ?? 'Anonymous caller'}</h1>
              <div className="mt-2">
                <AgentChain ids={conv.agents_visited} agents={agents} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" icon={<Play className="size-3.5" />} onClick={() => openDock({ resumeId: conv.id, agentId: conv.last_agent_id ?? undefined })} disabled={conv.status === 'live'}>
                Continue in preview
              </Button>
              <Button
                size="sm"
                variant="danger"
                icon={<Trash2 className="size-3.5" />}
                onClick={async () => {
                  if (!confirm('Delete this conversation and its saved state?')) return
                  await del(`/api/conversations/${conv.id}`)
                  invalidate('conversations')
                  navigate('/conversations')
                }}
              >
                Delete
              </Button>
            </div>
          </div>
          {conv.status === 'live' && <Badge tone="live" className="mt-4">live now</Badge>}
          {typeof conv.meta?.error === 'string' && <ErrorNote error={conv.meta.error} />}
          {conv.summary && (
            <div className="mt-6 rounded-2xl border border-line bg-l1 p-4">
              <div className="flex items-center gap-2">
                <p className="eyebrow">Summary</p>
                {conv.disposition && <Badge tone={conv.disposition === 'resolved' ? 'success' : 'neutral'}>{conv.disposition}</Badge>}
              </div>
              <p className="mt-2 text-[14px] leading-relaxed">{conv.summary}</p>
            </div>
          )}
          <div className="mt-8">
            {conv.turns.length ? <Lanes conv={conv} agents={agents} /> : <p className="text-[13px] text-fg-3">No turns were recorded.</p>}
          </div>
          <EventLog id={conv.id} />
        </div>
      </div>
      <aside className={`scroll-thin hidden w-[var(--inspector)] shrink-0 flex-col gap-6 overflow-y-auto border-l border-line p-5 ${dockOpen ? '2xl:flex' : 'xl:flex'}`}>
        <div>
          <p className="eyebrow mb-2">Context collected</p>
          {state && Object.keys(state.context).length ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-[12px]">
              {Object.entries(state.context).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-fg-3">{k}</dt>
                  <dd className="break-all">{String(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-[13px] text-fg-3">None</p>
          )}
        </div>
        {Object.keys(conv.extracted ?? {}).length > 0 && (
          <div>
            <p className="eyebrow mb-2">Extracted after the call</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-[12px]">
              {Object.entries(conv.extracted).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-fg-3">{k}</dt>
                  <dd className="break-all">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        <div>
          <p className="eyebrow mb-2">Graph state</p>
          <p className="text-[13px] text-fg-2">
            {state?.message_count ?? 0} messages · active agent <span className="font-mono">{state?.active_agent ?? '—'}</span>
          </p>
          <p className="mt-1 text-xs text-fg-3">LangGraph checkpoint {state?.checkpoint_id?.slice(0, 12) ?? '—'}</p>
        </div>
        {conv.resumed_from_id && (
          <div>
            <p className="eyebrow mb-2">Continues</p>
            <Link to={`/conversations/${conv.resumed_from_id}`} className="text-[13px] text-fg-2 hover:text-fg">
              Earlier conversation →
            </Link>
          </div>
        )}
      </aside>
    </div>
  )
}

export function ConversationsPage() {
  const { conversationId } = useParams()
  return conversationId ? <Detail id={conversationId} /> : <List />
}
