import { ArrowRight, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Badge, Button, ChipInput, Empty, ErrorNote, Field, IconButton, Input, Select, Switch, cx } from '../../components/ui'
import { post, useAgents, useInvalidate, useKnowledge, useLandscape, useMcp, useTargets, useTools } from '../../lib/queries'
import type { Agent, Edge } from '../../lib/types'
import { EdgeEditor } from '../landscape/EdgeEditor'
import type { Draft, Update } from './AgentsPage'

export const LANGUAGES: [string, string][] = [
  ['en', 'English'], ['ar-EG', 'Arabic (Egypt)'], ['ar-SA', 'Arabic (Saudi Arabia)'], ['ar-AE', 'Arabic (UAE)'], ['bn', 'Bengali'],
  ['zh', 'Chinese (Simplified)'], ['fr', 'French'], ['de', 'German'], ['hi', 'Hindi'], ['id', 'Indonesian'], ['it', 'Italian'],
  ['ja', 'Japanese'], ['ko', 'Korean'], ['pt-BR', 'Portuguese (Brazil)'], ['pt-PT', 'Portuguese (Portugal)'], ['ru', 'Russian'],
  ['es-MX', 'Spanish (Mexico)'], ['es-ES', 'Spanish (Spain)'], ['tr', 'Turkish'], ['vi', 'Vietnamese'],
]

function Row({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-3 border-b border-line py-5 first:pt-0 sm:grid-cols-[1fr_minmax(0,320px)] sm:items-start">
      <div>
        <p className="text-[14px] font-medium">{title}</p>
        {hint && <p className="mt-1 text-xs leading-relaxed text-fg-3">{hint}</p>}
      </div>
      <div>{children}</div>
    </div>
  )
}

export function BehaviorTab({ draft, update }: { draft: Draft; update: Update }) {
  const replaceRows = Object.entries(draft.replace_map)
  const setReplace = (rows: [string, string][]) => update({ replace_map: Object.fromEntries(rows) })
  return (
    <div>
      <Row title="Reasoning" hint="High thinks before answering (better on complex flows). None answers fastest.">
        <Select value={draft.reasoning_effort} onChange={(e) => update({ reasoning_effort: e.target.value as Draft['reasoning_effort'] })}>
          <option value="high">High</option>
          <option value="none">None (fastest)</option>
        </Select>
      </Row>
      <Row title="Language hint" hint="Biases transcription toward a language. The agent still detects and replies in the caller's language unless the prompt locks it.">
        <Select value={draft.language_hint ?? ''} onChange={(e) => update({ language_hint: e.target.value || null })}>
          <option value="">Detect automatically</option>
          {LANGUAGES.map(([code, label]) => (
            <option key={code} value={code}>
              {label} ({code})
            </option>
          ))}
        </Select>
      </Row>
      <Row title="Key terms" hint="Product names and proper nouns transcription should get right. Up to 100, 50 characters each. Press Enter to add.">
        <ChipInput values={draft.keyterms} onChange={(keyterms) => update({ keyterms: keyterms.slice(0, 100) })} placeholder="Acme Fiber, Zephyr" />
      </Row>
      <Row title="Pronunciation" hint="Changes how a word is spoken without changing the transcript. Whole words, case-insensitive.">
        <div className="flex flex-col gap-2">
          {replaceRows.map(([k, v], i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2">
              <Input value={k} placeholder="Written" onChange={(e) => setReplace(replaceRows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))} />
              <ArrowRight className="size-3.5 text-fg-3" />
              <Input value={v} placeholder="Spoken" onChange={(e) => setReplace(replaceRows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))} />
              <IconButton label="Remove" onClick={() => setReplace(replaceRows.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </IconButton>
            </div>
          ))}
          <Button size="sm" variant="ghost" className="w-fit" icon={<Plus className="size-3.5" />} onClick={() => setReplace([...replaceRows, ['', '']])}>
            Add word
          </Button>
        </div>
      </Row>
      <Row title="Check in after silence" hint="If the caller says nothing for this long after the agent finishes, the agent checks in.">
        <Select value={draft.idle_timeout_ms ? String(draft.idle_timeout_ms) : ''} onChange={(e) => update({ idle_timeout_ms: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Never</option>
          {[5000, 8000, 12000, 20000, 30000].map((ms) => (
            <option key={ms} value={ms}>
              {ms / 1000} seconds
            </option>
          ))}
        </Select>
      </Row>
      <Row title="Can end the call" hint="Gives the agent an end_call tool so it can hang up after saying goodbye.">
        <Switch checked={draft.allow_end_call} onChange={(v) => update({ allow_end_call: v })} label="Can end the call" />
      </Row>
    </div>
  )
}

function Toggle({ checked, onChange, title, detail, badge }: { checked: boolean; onChange: (v: boolean) => void; title: string; detail?: string; badge?: string }) {
  return (
    <label className={cx('flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors', checked ? 'border-line-strong bg-l2' : 'border-line hover:border-line-2')}>
      <Switch checked={checked} onChange={onChange} label={title} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 text-[13.5px]">
          <span className="font-mono">{title}</span>
          {badge && <Badge>{badge}</Badge>}
        </span>
        {detail && <span className="mt-0.5 block text-xs leading-relaxed text-fg-3">{detail}</span>}
      </span>
    </label>
  )
}

const toggleId = (list: string[], id: string, on: boolean) => (on ? [...new Set([...list, id])] : list.filter((x) => x !== id))

export function ToolsTab({ draft, update }: { draft: Draft; update: Update }) {
  const { data: tools } = useTools()
  const { data: mcps } = useMcp()
  const { data: targets } = useTargets()
  const web = draft.builtin_tools.web_search ?? {}
  const xs = draft.builtin_tools.x_search ?? {}
  const setBuiltin = (key: 'web_search' | 'x_search', value: Record<string, unknown>) => update({ builtin_tools: { ...draft.builtin_tools, [key]: { ...(draft.builtin_tools[key] ?? {}), ...value } } })
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <p className="text-[14px] font-medium">Search (runs at xAI)</p>
        <Toggle checked={!!web.enabled} onChange={(v) => setBuiltin('web_search', { enabled: v })} title="web_search" detail="Search the web. Limit it to your own domains to keep answers on-brand." />
        {web.enabled && (
          <div className="ml-12 grid gap-3 sm:grid-cols-2">
            <Field label="Only these domains" hint="Up to 5. No protocol.">
              <ChipInput mono values={web.allowed_domains ?? []} onChange={(v) => setBuiltin('web_search', { allowed_domains: v.slice(0, 5), excluded_domains: [] })} placeholder="docs.example.com" />
            </Field>
            <Field label="Never these domains" hint="Up to 5. Cannot combine with the list on the left.">
              <ChipInput mono values={web.excluded_domains ?? []} onChange={(v) => setBuiltin('web_search', { excluded_domains: v.slice(0, 5), allowed_domains: [] })} placeholder="example.org" />
            </Field>
          </div>
        )}
        <Toggle checked={!!xs.enabled} onChange={(v) => setBuiltin('x_search', { enabled: v })} title="x_search" detail="Search posts on X." />
        {xs.enabled && (
          <div className="ml-12 grid gap-3 sm:grid-cols-2">
            <Field label="Only these handles" hint="Up to 20, without @.">
              <ChipInput mono values={xs.allowed_x_handles ?? []} onChange={(v) => setBuiltin('x_search', { allowed_x_handles: v.slice(0, 20), excluded_x_handles: [] })} placeholder="xai" />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="From">
                <Input type="date" value={xs.from_date ?? ''} onChange={(e) => setBuiltin('x_search', { from_date: e.target.value })} />
              </Field>
              <Field label="To">
                <Input type="date" value={xs.to_date ?? ''} onChange={(e) => setBuiltin('x_search', { to_date: e.target.value })} />
              </Field>
            </div>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <p className="text-[14px] font-medium">Your tools (run by Voice Stack)</p>
          <Link to="/integrations/tools" className="text-[12.5px] text-fg-3 hover:text-fg">Manage tools →</Link>
        </div>
        {tools?.length ? (
          tools.map((t) => (
            <Toggle key={t.id} checked={draft.tool_ids.includes(t.id)} onChange={(v) => update({ tool_ids: toggleId(draft.tool_ids, t.id, v) })} title={t.name} detail={t.description} badge={t.kind} />
          ))
        ) : (
          <p className="text-[13px] text-fg-3">No HTTP or plugin tools yet. Add one in Integrations.</p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <p className="text-[14px] font-medium">MCP servers</p>
          <Link to="/integrations/mcp" className="text-[12.5px] text-fg-3 hover:text-fg">Manage servers →</Link>
        </div>
        {mcps?.length ? (
          mcps.map((m) => (
            <Toggle
              key={m.id}
              checked={draft.mcp_ids.includes(m.id)}
              onChange={(v) => update({ mcp_ids: toggleId(draft.mcp_ids, m.id, v) })}
              title={m.label}
              detail={`${m.description || m.url || m.command}${m.allowed_tools.length ? ` · ${m.allowed_tools.join(', ')}` : ''}`}
              badge={m.mode === 'xai' ? 'hosted by xAI' : 'run here'}
            />
          ))
        ) : (
          <p className="text-[13px] text-fg-3">No MCP servers yet.</p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <p className="text-[14px] font-medium">Transfer to a person</p>
          <Link to="/integrations/transfers" className="text-[12.5px] text-fg-3 hover:text-fg">Manage lines →</Link>
        </div>
        <p className="text-xs text-fg-3">Adds a transfer_call tool. On phone calls it sends a SIP REFER; in previews it is simulated.</p>
        {targets?.map((t) => (
          <Toggle key={t.id} checked={draft.transfer_target_ids.includes(t.id)} onChange={(v) => update({ transfer_target_ids: toggleId(draft.transfer_target_ids, t.id, v) })} title={t.name} detail={`${t.uri}${t.description ? ` · ${t.description}` : ''}`} />
        ))}
        {!targets?.length && <p className="text-[13px] text-fg-3">No transfer lines yet.</p>}
      </section>
    </div>
  )
}

export function KnowledgeTab({ draft, update }: { draft: Draft; update: Update }) {
  const { data: kbs } = useKnowledge()
  if (!kbs?.length)
    return (
      <Empty title="No knowledge bases" action={<Link to="/knowledge"><Button>Create one</Button></Link>}>
        Upload PDFs, docs, or pages. The agent searches them during calls.
      </Empty>
    )
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-fg-3">Local knowledge bases add a search_knowledge tool. xAI Collections are searched server-side with file_search.</p>
      {kbs.map((kb) => {
        const ready = kb.documents.filter((d) => d.status === 'ready').length
        return (
          <Toggle
            key={kb.id}
            checked={draft.knowledge_ids.includes(kb.id)}
            onChange={(v) => update({ knowledge_ids: toggleId(draft.knowledge_ids, kb.id, v) })}
            title={kb.name}
            badge={kb.mode === 'local' ? 'local' : 'xAI collection'}
            detail={`${ready} of ${kb.documents.length} documents ready${kb.description ? ` · ${kb.description}` : ''}`}
          />
        )
      })}
    </div>
  )
}

export function HandoffsTab({ agent }: { agent: Agent }) {
  const { data: landscape } = useLandscape()
  const { data: agents } = useAgents()
  const [target, setTarget] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [openEdge, setOpenEdge] = useState<string | null>(null)
  const invalidate = useInvalidate()
  const byId = new Map((agents ?? []).map((a) => [a.id, a]))
  const outgoing = landscape?.edges.filter((e) => e.source_id === agent.id) ?? []
  const incoming = landscape?.edges.filter((e) => e.target_id === agent.id) ?? []
  const available = (agents ?? []).filter((a) => a.id !== agent.id && !outgoing.some((e) => e.target_id === a.id))

  const add = async () => {
    setError(null)
    try {
      const edge = await post<Edge>('/api/edges', { source_id: agent.id, target_id: target })
      invalidate('landscape', 'agents')
      setTarget('')
      setOpenEdge(edge.id)
    } catch (e) {
      setError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-[13px] leading-relaxed text-fg-3">
        A handoff moves the caller to another agent in the same call. The model calls a transfer tool with a reason, a summary, and the context fields you define, and the next agent starts with that context. The full transcript carries over.
      </p>
      <div className="flex gap-2">
        <Select value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="">Add a handoff to…</option>
          {available.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </Select>
        <Button onClick={add} disabled={!target}>
          Add
        </Button>
      </div>
      <ErrorNote error={error} />
      <div className="flex flex-col gap-2">
        {outgoing.map((e) => {
          const t = byId.get(e.target_id)
          return (
            <div key={e.id} className="rounded-2xl border border-line">
              <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setOpenEdge(openEdge === e.id ? null : e.id)} aria-expanded={openEdge === e.id}>
                <span className="text-[14px]">{agent.name}</span>
                <ArrowRight className="size-3.5 text-fg-3" />
                <span className="text-[14px] font-medium">{t?.name}</span>
                <span className="ml-auto truncate text-xs text-fg-3">{e.description || 'No description yet'}</span>
                {e.context_fields.length > 0 && <Badge>{e.context_fields.length} fields</Badge>}
              </button>
              {openEdge === e.id && t && (
                <div className="border-t border-line p-4">
                  <EdgeEditor edge={e} sourceName={agent.name} targetName={t.name} targetSlug={t.slug} onDeleted={() => setOpenEdge(null)} />
                </div>
              )}
            </div>
          )
        })}
        {!outgoing.length && <p className="text-[13px] text-fg-3">This agent does not hand off to anyone yet.</p>}
      </div>
      {incoming.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Receives calls from</p>
          <p className="text-[13px] text-fg-2">{incoming.map((e) => byId.get(e.source_id)?.name).join(', ')}</p>
        </div>
      )}
    </div>
  )
}
