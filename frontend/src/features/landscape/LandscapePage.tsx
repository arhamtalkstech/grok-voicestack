import {
  Background,
  BaseEdge,
  BackgroundVariant,
  Controls,
  EdgeLabelRenderer,
  getBezierPath,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type EdgeProps,
  type Node,
  type NodeProps,
  type Edge as FlowEdge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { BookOpen, Globe, LayoutGrid, Phone, Plug, Plus, Wrench, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useLive } from '../../audio/live'
import { Badge, Button, Empty, ErrorNote, cx } from '../../components/ui'
import { wsUrl } from '../../lib/api'
import { post, put, useCreateAgent, useInvalidate, useLandscape } from '../../lib/queries'
import { useApp } from '../../lib/store'
import type { Edge, Landscape, LandscapeAgent } from '../../lib/types'
import { Voiceprint } from '../../voiceprint/Voiceprint'
import { EdgeEditor } from './EdgeEditor'

interface LiveOverlay {
  active: Set<string>
  pulses: Record<string, number>
}
const LiveContext = createContext<LiveOverlay>({ active: new Set(), pulses: {} })

/** Watches every live session (web previews and phone calls) for the Landscape overlay. */
function useLiveOverlay(): LiveOverlay {
  const [active, setActive] = useState<Record<string, string>>({})
  const [pulses, setPulses] = useState<Record<string, number>>({})
  useEffect(() => {
    let ws: WebSocket | null = null
    let stopped = false
    const connect = () => {
      ws = new WebSocket(wsUrl('/api/live/ws?conversation_id=*'))
      ws.onmessage = (e) => {
        const ev = JSON.parse(e.data)
        if (ev.type === 'snapshot') setActive(Object.fromEntries(ev.sessions.map((s: { conversation_id: string; agent: string }) => [s.conversation_id, s.agent])))
        else if (ev.type === 'agent.active') setActive((a) => ({ ...a, [ev.conversation_id]: ev.agent }))
        else if (ev.type === 'session.ended')
          setActive((a) => {
            const next = { ...a }
            delete next[ev.conversation_id]
            return next
          })
        else if (ev.type === 'handoff') setPulses((p) => ({ ...p, [`${ev.from}>${ev.to}`]: Date.now() }))
      }
      ws.onclose = () => {
        if (!stopped) setTimeout(connect, 2000)
      }
    }
    connect()
    return () => {
      stopped = true
      ws?.close()
    }
  }, [])
  return useMemo(() => ({ active: new Set(Object.values(active)), pulses }), [active, pulses])
}

type AgentNodeData = { agent: LandscapeAgent }

function AgentNode({ data, selected }: NodeProps<Node<AgentNodeData>>) {
  const { agent } = data
  const live = useContext(LiveContext).active.has(agent.slug)
  const counts = [
    { icon: Wrench, n: agent.tools.length, label: 'tools' },
    { icon: Plug, n: agent.mcps.length, label: 'MCP servers' },
    { icon: BookOpen, n: agent.knowledge.length, label: 'knowledge bases' },
    { icon: Globe, n: agent.builtin.length, label: 'search tools' },
    { icon: Phone, n: agent.transfers, label: 'transfer lines' },
  ].filter((c) => c.n)
  return (
    <div
      className={cx(
        'relative w-[248px] rounded-2xl border bg-l1 p-4 transition-[border-color,box-shadow] duration-200',
        selected ? 'border-fg/60' : 'border-line-2 hover:border-line-strong',
        live && 'border-live/70 shadow-[0_0_0_4px_var(--live-soft)]',
      )}
    >
      <Handle id="t-left" type="target" position={Position.Left} className="!size-2.5" />
      <Handle id="t-top" type="target" position={Position.Top} className="!size-2 !opacity-0" style={{ left: '35%' }} />
      <Handle id="t-bottom" type="target" position={Position.Bottom} className="!size-2 !opacity-0" style={{ left: '65%' }} />
      <Handle id="t-right" type="target" position={Position.Right} className="!size-2 !opacity-0" style={{ top: '70%' }} />
      <div className="flex items-start gap-3">
        <Voiceprint seed={{ voice: agent.voice_id, name: agent.name, speed: agent.speed }} size={40} live={live} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-[14px] font-medium">{agent.name}</p>
            {live && <span className="live-dot shrink-0" aria-label="In a live call" />}
          </div>
          <p className="truncate font-mono text-[11px] text-fg-3">
            {agent.voice_id} · {agent.speed}×
          </p>
        </div>
      </div>
      {agent.description && <p className="mt-3 line-clamp-2 text-[12px] leading-relaxed text-fg-3">{agent.description}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {agent.is_entry && <Badge>entry</Badge>}
        {agent.published_version != null ? <Badge tone="success">v{agent.published_version}</Badge> : <Badge>draft</Badge>}
        {counts.map(({ icon: Icon, n, label }) => (
          <span key={label} title={`${n} ${label}`} className="inline-flex items-center gap-1 rounded-pill bg-l3 px-1.5 py-0.5 font-mono text-[10.5px] text-fg-2">
            <Icon className="size-3" />
            {n}
          </span>
        ))}
      </div>
      <Handle id="s-right" type="source" position={Position.Right} className="!size-2.5" />
      <Handle id="s-bottom" type="source" position={Position.Bottom} className="!size-2 !opacity-0" style={{ left: '35%' }} isConnectable={false} />
      <Handle id="s-top" type="source" position={Position.Top} className="!size-2 !opacity-0" style={{ left: '65%' }} isConnectable={false} />
      <Handle id="s-left" type="source" position={Position.Left} className="!size-2 !opacity-0" style={{ top: '70%' }} isConnectable={false} />
    </div>
  )
}

/** Picks handles from the agents' relative positions so reverse and vertical handoffs do not loop around cards. */
function handlesFor(src: { x: number; y: number }, dst: { x: number; y: number }) {
  const dx = dst.x - src.x
  const dy = dst.y - src.y
  if (dx > 200) return { sourceHandle: 's-right', targetHandle: 't-left' }
  if (dx < -200) return { sourceHandle: 's-left', targetHandle: 't-right' }
  return dy >= 0 ? { sourceHandle: 's-bottom', targetHandle: 't-top' } : { sourceHandle: 's-top', targetHandle: 't-bottom' }
}

function EntryNode({ data }: NodeProps<Node<{ label: string; kind: 'web' | 'phone'; name?: string }>>) {
  return (
    <div className="flex items-center gap-2 rounded-pill border border-line-2 bg-bg px-3 py-1.5 text-[12px] text-fg-2">
      {data.kind === 'phone' ? <Phone className="size-3.5" /> : <Globe className="size-3.5" />}
      <span className={data.kind === 'phone' ? 'font-mono' : ''}>{data.label}</span>
      <Handle type="source" position={Position.Right} className="!size-2" isConnectable={false} />
    </div>
  )
}

function HandoffEdge(props: EdgeProps<FlowEdge<{ edge: Edge; sourceSlug: string; targetSlug: string; fields: number }>>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected, markerEnd } = props
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, curvature: 0.35 })
  const pulses = useContext(LiveContext).pulses
  const pulseAt = data ? pulses[`${data.sourceSlug}>${data.targetSlug}`] : undefined
  const [pulseKey, setPulseKey] = useState<number | null>(null)
  useEffect(() => {
    if (!pulseAt) return
    setPulseKey(pulseAt)
    const t = setTimeout(() => setPulseKey(null), 1600)
    return () => clearTimeout(t)
  }, [pulseAt])
  return (
    <>
      <BaseEdge path={path} markerEnd={markerEnd} style={{ stroke: pulseKey ? 'var(--live)' : selected ? 'var(--fg)' : 'var(--line-strong)', strokeWidth: selected || pulseKey ? 1.8 : 1.2 }} />
      {pulseKey && (
        <circle key={pulseKey} r="5" fill="var(--live)">
          <animateMotion dur="1.2s" repeatCount="1" path={path} fill="freeze" />
        </circle>
      )}
      {data && (data.edge.description || data.fields > 0) && (
        <EdgeLabelRenderer>
          <div
            className={cx(
              'nodrag nopan pointer-events-auto absolute max-w-[180px] -translate-y-1/2 truncate rounded-pill border bg-bg px-2 py-0.5 text-[10.5px]',
              // Vertical pairs run side by side: push each label outward so they do not overlap.
              Math.abs(sourceX - targetX) > 140 ? '-translate-x-1/2' : targetY > sourceY ? '-translate-x-[calc(100%+10px)]' : 'translate-x-[10px]',
              selected ? 'border-fg/50 text-fg' : 'border-line-2 text-fg-3',
            )}
            style={{ left: labelX, top: labelY }}
          >
            {data.fields > 0 && <span className="mr-1 font-mono text-fg-2">{data.fields}↦</span>}
            {data.edge.description || 'handoff'}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { agent: AgentNode, entry: EntryNode }
const edgeTypes = { handoff: HandoffEdge }

function layered(landscape: Landscape): Record<string, { x: number; y: number }> {
  const bySlug = new Map(landscape.agents.map((a) => [a.id, a]))
  const out = new Map<string, string[]>()
  for (const e of landscape.edges) out.set(e.source_id, [...(out.get(e.source_id) ?? []), e.target_id])
  const entry = landscape.agents.find((a) => a.is_entry) ?? landscape.agents[0]
  const level = new Map<string, number>()
  if (entry) {
    const queue = [entry.id]
    level.set(entry.id, 0)
    while (queue.length) {
      const id = queue.shift()!
      for (const t of out.get(id) ?? []) {
        if (!level.has(t)) {
          level.set(t, level.get(id)! + 1)
          queue.push(t)
        }
      }
    }
  }
  const maxLevel = Math.max(0, ...level.values())
  for (const a of landscape.agents) if (!level.has(a.id)) level.set(a.id, maxLevel + 1)
  const columns = new Map<number, string[]>()
  for (const [id, l] of level) columns.set(l, [...(columns.get(l) ?? []), id])
  const pos: Record<string, { x: number; y: number }> = {}
  for (const [l, ids] of columns) {
    ids.forEach((id, i) => {
      if (bySlug.has(id)) pos[id] = { x: l * 360, y: (i - (ids.length - 1) / 2) * 220 + 160 }
    })
  }
  return pos
}

function buildFlow(landscape: Landscape, layout?: Record<string, { x: number; y: number }>) {
  const auto = layered(landscape)
  const agents = new Map(landscape.agents.map((a) => [a.id, a]))
  const entry = landscape.agents.find((a) => a.is_entry) ?? landscape.agents[0]
  const nodes: Node[] = landscape.agents.map((a) => ({
    id: a.id,
    type: 'agent',
    position: layout?.[a.id] ?? (a.position?.x != null ? { x: a.position.x, y: a.position.y ?? 0 } : auto[a.id]),
    data: { agent: a },
  }))
  const positionOf = (id: string) => nodes.find((n) => n.id === id)?.position ?? { x: 0, y: 0 }
  const edges: FlowEdge[] = landscape.edges
    .filter((e) => agents.has(e.source_id) && agents.has(e.target_id))
    .map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      ...handlesFor(positionOf(e.source_id), positionOf(e.target_id)),
      type: 'handoff',
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: 'var(--line-strong)' },
      data: { edge: e, sourceSlug: agents.get(e.source_id)!.slug, targetSlug: agents.get(e.target_id)!.slug, fields: e.context_fields.length },
    }))
  if (entry) {
    const entryPos = nodes.find((n) => n.id === entry.id)?.position ?? { x: 0, y: 0 }
    const points = [{ id: 'entry-web', label: 'Web preview', kind: 'web' as const, agent: entry.id }, ...landscape.entry_points.map((p) => ({ id: `entry-${p.id}`, label: p.label, kind: 'phone' as const, agent: p.agent_id ?? entry.id }))]
    points.forEach((p, i) => {
      const target = nodes.find((n) => n.id === p.agent)?.position ?? entryPos
      nodes.push({ id: p.id, type: 'entry', position: { x: target.x - 220, y: target.y + 20 + i * 44 }, data: { label: p.label, kind: p.kind }, draggable: false, selectable: false })
      edges.push({ id: `${p.id}-edge`, source: p.id, target: p.agent, targetHandle: 't-left', selectable: false, style: { stroke: 'var(--line-2)', strokeDasharray: '4 4' } })
    })
  }
  return { nodes, edges }
}

function Inspector({ landscape, selection, onClose }: { landscape: Landscape; selection: { kind: 'agent' | 'edge'; id: string }; onClose: () => void }) {
  const navigate = useNavigate()
  const openDock = useApp((s) => s.openDock)
  const agents = new Map(landscape.agents.map((a) => [a.id, a]))
  const content =
    selection.kind === 'edge'
      ? (() => {
          const edge = landscape.edges.find((e) => e.id === selection.id)
          if (!edge) return null
          const s = agents.get(edge.source_id)
          const t = agents.get(edge.target_id)
          return <EdgeEditor edge={edge} sourceName={s?.name ?? ''} targetName={t?.name ?? ''} targetSlug={t?.slug ?? ''} onDeleted={onClose} />
        })()
      : (() => {
          const a = agents.get(selection.id)
          if (!a) return null
          const outgoing = landscape.edges.filter((e) => e.source_id === a.id)
          const incoming = landscape.edges.filter((e) => e.target_id === a.id)
          return (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3">
                <Voiceprint seed={{ voice: a.voice_id, name: a.name, speed: a.speed }} size={56} />
                <div>
                  <p className="text-[16px] font-medium">{a.name}</p>
                  <p className="font-mono text-[11.5px] text-fg-3">{a.slug}</p>
                </div>
              </div>
              {a.description && <p className="text-[13px] leading-relaxed text-fg-2">{a.description}</p>}
              <div className="flex gap-2">
                <Button variant="primary" size="sm" onClick={() => openDock({ agentId: a.id })}>
                  Talk to {a.name.split(' ')[0]}
                </Button>
                <Button size="sm" onClick={() => navigate(`/agents/${a.id}`)}>
                  Edit agent
                </Button>
              </div>
              <dl className="grid grid-cols-[110px_1fr] gap-y-2 text-[13px]">
                <dt className="text-fg-3">Voice</dt>
                <dd className="font-mono text-[12px]">
                  {a.voice_id} · {a.speed}×
                </dd>
                <dt className="text-fg-3">Hands off to</dt>
                <dd>{outgoing.map((e) => agents.get(e.target_id)?.name).join(', ') || '—'}</dd>
                <dt className="text-fg-3">Receives from</dt>
                <dd>{incoming.map((e) => agents.get(e.source_id)?.name).join(', ') || '—'}</dd>
                <dt className="text-fg-3">Tools</dt>
                <dd className="font-mono text-[12px]">{[...a.tools, ...a.builtin, ...a.mcps.map((m) => `mcp:${m}`)].join(', ') || '—'}</dd>
                <dt className="text-fg-3">Knowledge</dt>
                <dd>{a.knowledge.join(', ') || '—'}</dd>
              </dl>
              <p className="text-xs leading-relaxed text-fg-3">Drag from the right edge of a card to another agent to add a handoff.</p>
            </div>
          )
        })()
  return (
    <motion.aside
      initial={{ x: 24, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 24, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="scroll-thin absolute inset-y-0 right-0 z-10 w-full overflow-y-auto border-l border-line bg-bg/95 p-5 backdrop-blur-md sm:w-[var(--inspector)]"
    >
      <button aria-label="Close inspector" onClick={onClose} className="absolute right-3 top-3 rounded-pill p-1.5 text-fg-3 hover:bg-l2 hover:text-fg">
        <X className="size-4" />
      </button>
      {content}
    </motion.aside>
  )
}

function useIsNarrow() {
  const query = '(max-width: 767px)'
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = () => setNarrow(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return narrow
}

function MobileLandscape({ landscape, active }: { landscape: Landscape; active: Set<string> }) {
  const openDock = useApp((s) => s.openDock)
  const byId = new Map(landscape.agents.map((a) => [a.id, a]))
  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 pb-10 pt-48">
      <ul className="flex flex-col gap-3">
        {landscape.agents.map((a) => {
          const out = landscape.edges.filter((e) => e.source_id === a.id).map((e) => byId.get(e.target_id)?.name)
          return (
            <li key={a.id} className={cx('rounded-2xl border bg-l1 p-4', active.has(a.slug) ? 'border-live/70' : 'border-line-2')}>
              <Link to={`/agents/${a.id}`} className="flex items-center gap-3">
                <Voiceprint seed={{ voice: a.voice_id, name: a.name, speed: a.speed }} size={40} live={active.has(a.slug)} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium">{a.name}</p>
                  <p className="font-mono text-[11px] text-fg-3">
                    {a.voice_id} · {a.speed}×{a.is_entry ? ' · entry' : ''}
                  </p>
                </div>
              </Link>
              {out.length > 0 && <p className="mt-3 text-[12.5px] text-fg-3">Hands off to {out.join(', ')}</p>}
              <Button size="sm" className="mt-3" onClick={() => openDock({ agentId: a.id })}>
                Talk to {a.name.split(' ')[0]}
              </Button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function LandscapePage() {
  const narrow = useIsNarrow()
  const { data: landscape, isLoading, error } = useLandscape()
  const overlay = useLiveOverlay()
  const localHandoff = useLive((s) => s.lastHandoff)
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([])
  const [selection, setSelection] = useState<{ kind: 'agent' | 'edge'; id: string } | null>(null)
  const [actionError, setActionError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  const createAgent = useCreateAgent()
  const navigate = useNavigate()
  const layoutRef = useRef<Record<string, { x: number; y: number }>>({})

  useEffect(() => {
    if (!landscape) return
    const flow = buildFlow(landscape, layoutRef.current)
    setNodes(flow.nodes)
    setEdges(flow.edges)
  }, [landscape, setNodes, setEdges])

  const pulses = useMemo(() => {
    if (!localHandoff) return overlay.pulses
    return { ...overlay.pulses, [`${localHandoff.from}>${localHandoff.to}`]: Math.max(overlay.pulses[`${localHandoff.from}>${localHandoff.to}`] ?? 0, localHandoff.at) }
  }, [overlay.pulses, localHandoff])

  const onConnect = useCallback(
    async (c: Connection) => {
      if (!c.source || !c.target || c.source.startsWith('entry-')) return
      setActionError(null)
      try {
        const edge = await post<Edge>('/api/edges', { source_id: c.source, target_id: c.target })
        invalidate('landscape', 'agents')
        setSelection({ kind: 'edge', id: edge.id })
      } catch (e) {
        setActionError(e)
      }
    },
    [invalidate],
  )

  const savePositions = useCallback(
    async (moved: Node[]) => {
      const positions = Object.fromEntries(moved.filter((n) => n.type === 'agent').map((n) => [n.id, n.position]))
      Object.assign(layoutRef.current, positions)
      if (Object.keys(positions).length) await put('/api/landscape/positions', { positions })
    },
    [],
  )

  const tidy = async () => {
    if (!landscape) return
    const pos = layered(landscape)
    layoutRef.current = pos
    const flow = buildFlow(landscape, pos)
    setNodes(flow.nodes)
    setEdges(flow.edges)
    await put('/api/landscape/positions', { positions: pos })
  }

  const addAgent = async () => {
    const xs = nodes.filter((n) => n.type === 'agent').map((n) => n.position)
    const position = { x: Math.max(0, ...xs.map((p) => p.x)) + 360, y: 160 }
    const agent = await createAgent.mutateAsync({ name: 'New agent', position, prompt_sections: { role: 'You are a helpful voice agent.' } })
    navigate(`/agents/${agent.id}`)
  }

  if (error) return <div className="p-8"><ErrorNote error={error} /></div>
  return (
    <LiveContext.Provider value={{ active: overlay.active, pulses }}>
      <div className="relative h-full">
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-4 p-5">
          <div className="pointer-events-auto">
            <h1 className="display text-[30px]">Landscape</h1>
            <p className="mt-1 max-w-md text-[13px] text-fg-3">Every agent, the handoffs between them, and where calls come in. Live calls light up here.</p>
          </div>
          <div className="pointer-events-auto flex items-center gap-2">
            <Button size="sm" variant="ghost" icon={<LayoutGrid className="size-3.5" />} onClick={tidy}>
              Tidy
            </Button>
            <Button size="sm" icon={<Plus className="size-3.5" />} onClick={addAgent} loading={createAgent.isPending}>
              New agent
            </Button>
          </div>
        </div>
        {actionError ? <div className="absolute bottom-5 left-5 z-10 max-w-md"><ErrorNote error={actionError} /></div> : null}
        {narrow && landscape && landscape.agents.length > 0 ? (
          <MobileLandscape landscape={landscape} active={overlay.active} />
        ) : !isLoading && landscape && landscape.agents.length === 0 ? (
          <div className="flex h-full items-center justify-center p-8">
            <Empty title="No agents yet" action={<Button variant="primary" onClick={addAgent}>Create your first agent</Button>}>
              Agents are the voices callers talk to. Add one, then connect agents to hand calls between them.
            </Empty>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={(_, __, moved) => {
              void savePositions(moved)
              const pos = new Map(nodes.map((n) => [n.id, n.position]))
              for (const m of moved) pos.set(m.id, m.position)
              setEdges((es) => es.map((e) => (e.type === 'handoff' ? { ...e, ...handlesFor(pos.get(e.source)!, pos.get(e.target)!) } : e)))
            }}
            onNodeClick={(_, n) => n.type === 'agent' && setSelection({ kind: 'agent', id: n.id })}
            onNodeDoubleClick={(_, n) => n.type === 'agent' && navigate(`/agents/${n.id}`)}
            onEdgeClick={(_, e) => !e.id.startsWith('entry-') && setSelection({ kind: 'edge', id: e.id })}
            onPaneClick={() => setSelection(null)}
            fitView
            fitViewOptions={{ padding: 0.35, maxZoom: 1 }}
            minZoom={0.3}
            proOptions={{ hideAttribution: true }}
            deleteKeyCode={null}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="var(--grid-dot)" />
            <Controls showInteractive={false} position="bottom-left" />
          </ReactFlow>
        )}
        <AnimatePresence>{selection && landscape && <Inspector key={selection.id} landscape={landscape} selection={selection} onClose={() => setSelection(null)} />}</AnimatePresence>
        {landscape && landscape.agents.length > 0 && (
          <div className="pointer-events-none absolute bottom-5 right-5 hidden text-right text-[11.5px] text-fg-4 md:block">
            {landscape.agents.length} agents · {landscape.edges.length} handoffs · <Link to="/settings" className="pointer-events-auto hover:text-fg-2">Import / export</Link>
          </div>
        )}
      </div>
    </LiveContext.Provider>
  )
}
