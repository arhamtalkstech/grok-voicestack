import { useQuery } from '@tanstack/react-query'
import { AlertCircle, AlertTriangle, Copy, Info, Plus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router'
import { Badge, Button, Empty, ErrorNote, IconButton, Switch, Tip, cx } from '../../components/ui'
import { del, get, post, useAgents, useCreateAgent, useInvalidate, useSaveAgent } from '../../lib/queries'
import { useApp } from '../../lib/store'
import type { Agent, Lint } from '../../lib/types'
import { Voiceprint } from '../../voiceprint/Voiceprint'
import { BehaviorTab, HandoffsTab, KnowledgeTab, ToolsTab } from './OtherTabs'
import { PromptTab } from './PromptTab'
import { VoiceTab } from './VoiceTab'

const TABS = [
  { id: 'prompt', label: 'Prompt' },
  { id: 'voice', label: 'Voice' },
  { id: 'behavior', label: 'Behavior' },
  { id: 'tools', label: 'Tools' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'handoffs', label: 'Handoffs' },
]

const EDITABLE = [
  'name', 'description', 'prompt_mode', 'prompt_sections', 'raw_prompt', 'key_facts', 'greeting', 'greeting_mode',
  'greeting_interruptible', 'voice_id', 'speed', 'reasoning_effort', 'language_hint', 'keyterms', 'replace_map',
  'idle_timeout_ms', 'builtin_tools', 'tool_ids', 'mcp_ids', 'knowledge_ids', 'transfer_target_ids', 'allow_end_call', 'is_entry',
] as const satisfies readonly (keyof Agent)[]

export type Draft = Agent
export type Update = (patch: Partial<Agent>) => void

function AgentRail({ agents, onCreate, creating }: { agents: Agent[]; onCreate: () => void; creating: boolean }) {
  return (
    <aside className="scroll-thin hidden w-[var(--rail)] shrink-0 flex-col overflow-y-auto border-r border-line px-3 py-5 md:flex">
      <div className="mb-2 flex items-center justify-between px-2">
        <p className="eyebrow">Agents</p>
        <IconButton label="New agent" onClick={onCreate} disabled={creating}>
          <Plus className="size-4" />
        </IconButton>
      </div>
      <nav className="flex flex-col gap-0.5">
        {agents.map((a) => (
          <NavLink
            key={a.id}
            to={`/agents/${a.id}`}
            className={({ isActive }) => cx('flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[14px]', isActive ? 'bg-l2 text-fg' : 'text-fg-2 hover:text-fg')}
          >
            <Voiceprint seed={{ voice: a.voice_id, name: a.name, speed: a.speed }} size={20} />
            <span className="min-w-0 flex-1 truncate">{a.name}</span>
            {a.lint.findings.some((f) => f.severity === 'error') && <span className="size-1.5 rounded-pill bg-danger" aria-label="Prompt has errors" />}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

const SEVERITY_ICON = { error: AlertCircle, warning: AlertTriangle, info: Info }

export function LintPanel({ lint, onJump }: { lint: Lint; onJump?: (section: string) => void }) {
  const tone = lint.score >= 90 ? 'text-success' : lint.score >= 70 ? 'text-warn' : 'text-danger'
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="eyebrow">Prompt check</p>
        <p className={cx('font-mono text-[13px]', tone)}>{lint.score}/100</p>
      </div>
      <p className="mt-1 text-xs text-fg-3">Rules from the xAI speech-to-speech prompting guide.</p>
      <ul className="mt-3 flex flex-col gap-2">
        {lint.findings.length === 0 && <li className="text-[13px] text-fg-2">No issues. The prompt follows the guide's structure.</li>}
        {lint.findings.map((f, i) => {
          const Icon = SEVERITY_ICON[f.severity]
          return (
            <li key={i}>
              <button
                onClick={() => f.section && onJump?.(f.section)}
                className="flex w-full gap-2 rounded-xl border border-line bg-l1 p-2.5 text-left text-[12.5px] leading-relaxed hover:border-line-2"
              >
                <Icon className={cx('mt-0.5 size-3.5 shrink-0', f.severity === 'error' ? 'text-danger' : f.severity === 'warning' ? 'text-warn' : 'text-info')} />
                <span>
                  {f.message}
                  {f.quote && <span className="mt-1 block font-mono text-[11px] text-fg-3">“{f.quote}”</span>}
                  {f.guide && <span className="mt-1 block text-[11px] text-fg-4">Guide: {f.guide}</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function CompiledPanel({ agentId, version }: { agentId: string; version: string }) {
  const { data } = useQuery({
    queryKey: ['compiled', agentId, version],
    queryFn: () => get<{ instructions: string; session: Record<string, unknown>; tool_errors: string[] }>(`/api/agents/${agentId}/compiled`),
  })
  if (!data) return null
  return (
    <div className="flex flex-col gap-2">
      <p className="eyebrow">What the model receives</p>
      {data.tool_errors.map((e) => (
        <p key={e} className="text-xs text-danger">
          {e}
        </p>
      ))}
      <details>
        <summary className="cursor-pointer text-[13px] text-fg-2">Instructions ({data.instructions.length.toLocaleString()} chars)</summary>
        <pre className="mt-2 max-h-[420px] overflow-auto whitespace-pre-wrap rounded-xl bg-inset p-3 font-mono text-[11px] leading-relaxed text-fg-2">{data.instructions}</pre>
      </details>
      <details>
        <summary className="cursor-pointer text-[13px] text-fg-2">Full session.update</summary>
        <pre className="mt-2 max-h-[420px] overflow-auto rounded-xl bg-inset p-3 font-mono text-[11px] text-fg-2">{JSON.stringify(data.session, null, 2)}</pre>
      </details>
    </div>
  )
}

function Editor({ agent }: { agent: Agent }) {
  const params = useParams()
  const navigate = useNavigate()
  const tab = params.tab ?? 'prompt'
  const [draft, setDraft] = useState<Agent>(agent)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [error, setError] = useState<unknown>(null)
  const dirty = useRef(false)
  const save = useSaveAgent()
  const invalidate = useInvalidate()
  const openDock = useApp((s) => s.openDock)
  const dockOpen = useApp((s) => s.dock.open)
  const [publishing, setPublishing] = useState(false)
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    if (!dirty.current) setDraft(agent)
  }, [agent])
  useEffect(() => {
    dirty.current = false
    setDraft(agent)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.id])

  const update: Update = (p) => {
    dirty.current = true
    setDraft((d) => ({ ...d, ...p }))
  }

  useEffect(() => {
    if (!dirty.current) return
    setStatus('saving')
    const t = setTimeout(async () => {
      const body = Object.fromEntries(EDITABLE.map((k) => [k, draft[k]])) as Partial<Agent>
      try {
        await save.mutateAsync({ id: draft.id, ...body })
        dirty.current = false
        setStatus('saved')
        setError(null)
      } catch (e) {
        setStatus('error')
        setError(e)
      }
    }, 700)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  const publish = async () => {
    setPublishing(true)
    try {
      await post(`/api/agents/${agent.id}/publish`, {})
      invalidate('agents', 'landscape')
    } finally {
      setPublishing(false)
    }
  }

  const jump = (section: string) => {
    if (tab !== 'prompt') navigate(`/agents/${agent.id}/prompt`)
    setTimeout(() => sectionRefs.current[section]?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60)
  }

  return (
    <div className="flex min-w-0 flex-1">
      <div className="scroll-thin min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-5 pb-24 pt-8 md:px-10">
          <div className="flex flex-wrap items-start gap-x-5 gap-y-4">
            <Voiceprint seed={{ voice: draft.voice_id, name: draft.name, speed: draft.speed }} size={72} />
            <div className="min-w-[min(100%,16rem)] flex-1">
              <input
                aria-label="Agent name"
                value={draft.name}
                onChange={(e) => update({ name: e.target.value })}
                className="display w-full bg-transparent text-[34px] focus:outline-none"
              />
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[12px] text-fg-3">{agent.slug}</span>
                {agent.published_version != null ? (
                  <Badge tone={agent.draft_changed ? 'warn' : 'success'}>{agent.draft_changed ? `v${agent.published_version} · unpublished edits` : `v${agent.published_version} live on phone`}</Badge>
                ) : (
                  <Badge>never published</Badge>
                )}
                <span className="font-mono text-[11px] text-fg-4" aria-live="polite">
                  {status === 'saving' ? 'saving…' : status === 'saved' ? 'saved' : status === 'error' ? 'not saved' : ''}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="primary" size="sm" onClick={() => openDock({ agentId: agent.id })}>
                Talk to agent
              </Button>
              <Tip label="Phone numbers use the published version. Previews use your latest edits.">
                <Button size="sm" onClick={publish} loading={publishing} disabled={agent.published_version != null && !agent.draft_changed}>
                  Publish
                </Button>
              </Tip>
            </div>
          </div>
          <input
            aria-label="Description"
            className="mt-4 h-9 w-full bg-transparent text-sm text-fg-2 placeholder:text-fg-4 focus:outline-none"
            placeholder="One line on what this agent does (shown on the Landscape)"
            value={draft.description}
            onChange={(e) => update({ description: e.target.value })}
          />
          <div className="mt-2 flex items-center gap-2 text-[13px] text-fg-2">
            <Switch checked={draft.is_entry} onChange={(v) => update({ is_entry: v })} label="Entry agent" />
            Entry agent <span className="text-fg-3">— answers new calls and previews by default</span>
          </div>
          <ErrorNote error={error} />
          <nav className="mt-7 flex gap-1 overflow-x-auto border-b border-line pb-px" aria-label="Agent sections">
            {TABS.map((t) => (
              <NavLink
                key={t.id}
                to={`/agents/${agent.id}/${t.id}`}
                className={cx('-mb-px shrink-0 border-b px-3 py-2 text-[14px] transition-colors', tab === t.id ? 'border-fg text-fg' : 'border-transparent text-fg-3 hover:text-fg-2')}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="pt-7">
            {tab === 'prompt' && <PromptTab draft={draft} update={update} sectionRefs={sectionRefs} />}
            {tab === 'voice' && <VoiceTab draft={draft} update={update} />}
            {tab === 'behavior' && <BehaviorTab draft={draft} update={update} />}
            {tab === 'tools' && <ToolsTab draft={draft} update={update} />}
            {tab === 'knowledge' && <KnowledgeTab draft={draft} update={update} />}
            {tab === 'handoffs' && <HandoffsTab agent={agent} />}
          </div>
          <div className="mt-16 flex gap-2 border-t border-line pt-6">
            <Button
              size="sm"
              variant="ghost"
              icon={<Copy className="size-3.5" />}
              onClick={async () => {
                const copy = await post<Agent>(`/api/agents/${agent.id}/duplicate`)
                invalidate('agents', 'landscape')
                navigate(`/agents/${copy.id}`)
              }}
            >
              Duplicate
            </Button>
            <Button
              size="sm"
              variant="danger"
              icon={<Trash2 className="size-3.5" />}
              onClick={async () => {
                if (!confirm(`Delete ${agent.name}? Its handoffs are deleted too. Past conversations stay.`)) return
                await del(`/api/agents/${agent.id}`)
                invalidate('agents', 'landscape')
                navigate('/agents')
              }}
            >
              Delete agent
            </Button>
          </div>
        </div>
      </div>
      <aside className={`scroll-thin hidden w-[var(--inspector)] shrink-0 flex-col gap-8 overflow-y-auto border-l border-line p-5 ${dockOpen ? '2xl:flex' : 'xl:flex'}`}>
        <LintPanel lint={agent.lint} onJump={jump} />
        <CompiledPanel agentId={agent.id} version={agent.updated_at} />
      </aside>
    </div>
  )
}

export function AgentsPage() {
  const { agentId } = useParams()
  const { data: agents, isLoading, error } = useAgents()
  const navigate = useNavigate()
  const create = useCreateAgent()

  useEffect(() => {
    if (!agentId && agents?.length) navigate(`/agents/${(agents.find((a) => a.is_entry) ?? agents[0]).id}`, { replace: true })
  }, [agentId, agents, navigate])

  const onCreate = async () => {
    const a = await create.mutateAsync({ name: 'New agent', prompt_sections: { role: 'You are a helpful voice agent.' } })
    navigate(`/agents/${a.id}`)
  }

  if (error) return <div className="p-8"><ErrorNote error={error} /></div>
  const agent = agents?.find((a) => a.id === agentId)
  return (
    <div className="flex h-full">
      <AgentRail agents={agents ?? []} onCreate={onCreate} creating={create.isPending} />
      {agent ? (
        <Editor agent={agent} />
      ) : (
        !isLoading && (
          <div className="flex flex-1 items-center justify-center p-8">
            <Empty title={agents?.length ? 'Agent not found' : 'No agents yet'} action={<Button variant="primary" onClick={onCreate}>New agent</Button>}>
              Each agent has a prompt, a voice, tools, and handoffs to other agents.
            </Empty>
          </div>
        )
      )}
    </div>
  )
}
