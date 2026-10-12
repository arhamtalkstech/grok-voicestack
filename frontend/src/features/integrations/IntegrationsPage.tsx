import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router'
import { Badge, Button, Dialog, Empty, ErrorNote, Field, IconButton, Input, SectionTitle, Select, Switch, Textarea, cx } from '../../components/ui'
import { del, post, put, useInvalidate, useMcp, usePlugins, useSecrets, useTargets, useTools } from '../../lib/queries'
import type { McpServer, Tool, TransferTarget } from '../../lib/types'

const SECTIONS = [
  { id: 'tools', label: 'HTTP tools' },
  { id: 'mcp', label: 'MCP servers' },
  { id: 'plugins', label: 'Code plugins' },
  { id: 'secrets', label: 'Secrets' },
  { id: 'transfers', label: 'Transfer lines' },
]

type Param = { name: string; type: string; description: string; required: boolean }

function schemaToParams(schema: Record<string, unknown>): Param[] {
  const props = (schema.properties ?? {}) as Record<string, { type?: string; description?: string }>
  const required = new Set((schema.required as string[]) ?? [])
  return Object.entries(props).map(([name, p]) => ({ name, type: p.type ?? 'string', description: p.description ?? '', required: required.has(name) }))
}

function paramsToSchema(params: Param[]) {
  const valid = params.filter((p) => p.name.trim())
  return {
    type: 'object',
    properties: Object.fromEntries(valid.map((p) => [p.name, { type: p.type, ...(p.description ? { description: p.description } : {}) }])),
    required: valid.filter((p) => p.required).map((p) => p.name),
  }
}

function KeyValueRows({ rows, onChange, keyPlaceholder, valuePlaceholder, mono }: { rows: [string, string][]; onChange: (r: [string, string][]) => void; keyPlaceholder: string; valuePlaceholder: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      {rows.map(([k, v], i) => (
        <div key={i} className="grid grid-cols-[1fr_1.4fr_auto] gap-2">
          <Input mono value={k} placeholder={keyPlaceholder} onChange={(e) => onChange(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))} />
          <Input mono={mono} value={v} placeholder={valuePlaceholder} onChange={(e) => onChange(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))} />
          <IconButton label="Remove" onClick={() => onChange(rows.filter((_, j) => j !== i))}>
            <Trash2 className="size-3.5" />
          </IconButton>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="w-fit" icon={<Plus className="size-3.5" />} onClick={() => onChange([...rows, ['', '']])}>
        Add
      </Button>
    </div>
  )
}

const EMPTY_TOOL: Tool = {
  id: '',
  name: '',
  kind: 'http',
  description: '',
  parameters: { type: 'object', properties: {} },
  config: { method: 'GET', url: '', headers: {}, send_args_as: 'query', max_chars: 1500, timeout_s: 15 },
  preamble: '',
  requires_confirmation: false,
  enabled: true,
}

function ToolEditor({ tool, onClose }: { tool: Tool; onClose: () => void }) {
  const [t, setT] = useState(tool)
  const [params, setParams] = useState<Param[]>(schemaToParams(tool.parameters))
  const [testArgs, setTestArgs] = useState('{}')
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  const cfg = t.config as Record<string, any>
  const setCfg = (patch: Record<string, unknown>) => setT({ ...t, config: { ...cfg, ...patch } })

  const save = async (): Promise<Tool | null> => {
    setBusy(true)
    setError(null)
    try {
      const body = { ...t, parameters: paramsToSchema(params) }
      const saved = t.id ? await put<Tool>(`/api/tools/${t.id}`, body) : await post<Tool>('/api/tools', body)
      setT(saved)
      invalidate('tools', 'agents', 'landscape')
      return saved
    } catch (e) {
      setError(e)
      return null
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    const saved = await save()
    if (!saved) return
    try {
      setTestResult(await post(`/api/tools/${saved.id}/test`, JSON.parse(testArgs || '{}')))
    } catch (e) {
      setError(e)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" hint="snake_case. The model calls the tool by this name.">
          <Input mono value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} placeholder="check_order_status" />
        </Field>
        <Field label="Spoken preamble" hint="Optional. A line the agent says before calling.">
          <Input value={t.preamble} onChange={(e) => setT({ ...t, preamble: e.target.value })} placeholder="Let me look that up." />
        </Field>
      </div>
      <Field label="Description" hint="Tell the model when to call it and what it returns.">
        <Textarea minRows={2} value={t.description} onChange={(e) => setT({ ...t, description: e.target.value })} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-[110px_1fr]">
        <Field label="Method">
          <Select value={cfg.method} onChange={(e) => setCfg({ method: e.target.value, send_args_as: ['GET', 'DELETE'].includes(e.target.value) ? 'query' : 'json' })}>
            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => (
              <option key={m}>{m}</option>
            ))}
          </Select>
        </Field>
        <Field label="URL" hint="Use {param} for path values and {{secret:NAME}} for credentials.">
          <Input mono value={cfg.url} onChange={(e) => setCfg({ url: e.target.value })} placeholder="https://api.example.com/orders/{order_id}" />
        </Field>
      </div>
      <Field label="Parameters" hint="What the model must provide. These become the tool's JSON schema.">
        <div className="flex flex-col gap-2">
          {params.map((p, i) => (
            <div key={i} className="grid grid-cols-[1fr_100px_1.5fr_auto_auto] items-center gap-2">
              <Input mono value={p.name} placeholder="name" onChange={(e) => setParams(params.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
              <Select value={p.type} onChange={(e) => setParams(params.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}>
                {['string', 'number', 'integer', 'boolean'].map((ty) => (
                  <option key={ty}>{ty}</option>
                ))}
              </Select>
              <Input value={p.description} placeholder="what it is" onChange={(e) => setParams(params.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
              <Switch checked={p.required} onChange={(v) => setParams(params.map((x, j) => (j === i ? { ...x, required: v } : x)))} label="Required" />
              <IconButton label="Remove" onClick={() => setParams(params.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </IconButton>
            </div>
          ))}
          <Button size="sm" variant="ghost" className="w-fit" icon={<Plus className="size-3.5" />} onClick={() => setParams([...params, { name: '', type: 'string', description: '', required: false }])}>
            Add parameter
          </Button>
        </div>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Send other arguments as">
          <Select value={cfg.send_args_as} onChange={(e) => setCfg({ send_args_as: e.target.value })}>
            <option value="query">Query string</option>
            <option value="json">JSON body</option>
            <option value="none">Nothing (URL only)</option>
          </Select>
        </Field>
        <Field label="Timeout (seconds)">
          <Input type="number" min={1} max={60} value={cfg.timeout_s ?? 15} onChange={(e) => setCfg({ timeout_s: Number(e.target.value) })} />
        </Field>
      </div>
      <Field label="Headers">
        <KeyValueRows mono rows={Object.entries(cfg.headers ?? {}) as [string, string][]} onChange={(rows) => setCfg({ headers: Object.fromEntries(rows) })} keyPlaceholder="Authorization" valuePlaceholder="Bearer {{secret:ORDERS_TOKEN}}" />
      </Field>
      <Field label="Fields to return" hint="Pick fields with JSONPath so the agent gets a short, speakable result. Leave empty to return the whole response.">
        <KeyValueRows mono rows={Object.entries(cfg.response_fields ?? {}) as [string, string][]} onChange={(rows) => setCfg({ response_fields: Object.fromEntries(rows) })} keyPlaceholder="status" valuePlaceholder="$.order.status" />
      </Field>
      <label className="flex items-center gap-2 text-[13px] text-fg-2">
        <Switch checked={t.requires_confirmation} onChange={(v) => setT({ ...t, requires_confirmation: v })} label="Confirm first" />
        This tool changes something: the agent asks the caller to confirm before calling it
      </label>
      <div className="rounded-2xl border border-line p-4">
        <p className="text-[13px] font-medium">Test with real arguments</p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <Textarea mono minRows={2} value={testArgs} onChange={(e) => setTestArgs(e.target.value)} />
          <Button onClick={test} loading={busy} className="sm:self-start">
            Save and run
          </Button>
        </div>
        {testResult && <pre className="mt-3 max-h-64 overflow-auto rounded-xl bg-inset p-3 font-mono text-[11.5px] text-fg-2">{JSON.stringify(testResult, null, 2)}</pre>}
      </div>
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button variant="primary" onClick={async () => (await save()) && onClose()} loading={busy}>
          Save tool
        </Button>
        {t.id && (
          <Button
            variant="danger"
            onClick={async () => {
              await del(`/api/tools/${t.id}`)
              invalidate('tools', 'agents', 'landscape')
              onClose()
            }}
          >
            Delete
          </Button>
        )}
      </div>
    </div>
  )
}

function ToolsSection() {
  const { data: tools } = useTools()
  const [editing, setEditing] = useState<Tool | null>(null)
  return (
    <div className="flex flex-col gap-6">
      <SectionTitle eyebrow="Run by Voice Stack" title="HTTP tools" action={<Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => setEditing(EMPTY_TOOL)}>New tool</Button>}>
        Call any REST endpoint during a conversation. Attach tools to agents on their Tools tab.
      </SectionTitle>
      {tools?.filter((t) => t.kind === 'http').length ? (
        <ul className="divide-y divide-line rounded-2xl border border-line">
          {tools.filter((t) => t.kind === 'http').map((t) => (
            <li key={t.id}>
              <button className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-l1" onClick={() => setEditing(t)}>
                <span className="font-mono text-[13px]">{t.name}</span>
                <Badge>{String((t.config as any).method)}</Badge>
                <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-fg-3">{String((t.config as any).url)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No HTTP tools">Wire an agent to your order system, CRM, or any API.</Empty>
      )}
      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)} title={editing?.id ? editing.name : 'New HTTP tool'} wide>
        {editing && <ToolEditor tool={editing} onClose={() => setEditing(null)} />}
      </Dialog>
    </div>
  )
}

const EMPTY_MCP: McpServer = { id: '', label: '', description: '', mode: 'xai', transport: 'streamable_http', url: '', command: '', args: [], allowed_tools: [], authorization_secret: null, header_secrets: {}, enabled: true }

function McpEditor({ server, onClose }: { server: McpServer; onClose: () => void }) {
  const [m, setM] = useState(server)
  const [discovered, setDiscovered] = useState<{ name: string; description: string }[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const { data: secrets } = useSecrets()
  const invalidate = useInvalidate()

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      const saved = m.id ? await put<McpServer>(`/api/mcp/${m.id}`, m) : await post<McpServer>('/api/mcp', m)
      setM(saved)
      invalidate('mcp', 'agents', 'landscape')
      return saved
    } catch (e) {
      setError(e)
      return null
    } finally {
      setBusy(false)
    }
  }
  const discover = async () => {
    const saved = await save()
    if (!saved) return
    setBusy(true)
    const r = await post<{ ok: boolean; tools: { name: string; description: string }[]; error?: string }>(`/api/mcp/${saved.id}/discover`)
    setBusy(false)
    if (r.ok) setDiscovered(r.tools)
    else setError(new Error(r.error ?? 'Discovery failed'))
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Label" hint="Prefix for the server's tools.">
          <Input mono value={m.label} onChange={(e) => setM({ ...m, label: e.target.value })} placeholder="crm" />
        </Field>
        <Field label="Who connects">
          <Select value={m.mode} onChange={(e) => setM({ ...m, mode: e.target.value as McpServer['mode'], transport: e.target.value === 'xai' && m.transport === 'stdio' ? 'streamable_http' : m.transport })}>
            <option value="xai">xAI (hosted, lowest latency, public URL)</option>
            <option value="managed">Voice Stack (private networks, stdio)</option>
          </Select>
        </Field>
      </div>
      <Field label="Description">
        <Input value={m.description} onChange={(e) => setM({ ...m, description: e.target.value })} placeholder="Order lookups and returns" />
      </Field>
      <div className="grid gap-3 sm:grid-cols-[180px_1fr]">
        <Field label="Transport">
          <Select value={m.transport} onChange={(e) => setM({ ...m, transport: e.target.value as McpServer['transport'] })}>
            <option value="streamable_http">Streamable HTTP</option>
            <option value="sse">SSE</option>
            {m.mode === 'managed' && <option value="stdio">stdio (local process)</option>}
          </Select>
        </Field>
        {m.transport === 'stdio' ? (
          <Field label="Command" hint="Arguments separated by spaces.">
            <Input mono value={[m.command, ...m.args].join(' ')} onChange={(e) => { const [command, ...args] = e.target.value.split(' '); setM({ ...m, command, args }) }} placeholder="npx -y @modelcontextprotocol/server-everything" />
          </Field>
        ) : (
          <Field label="Server URL">
            <Input mono value={m.url} onChange={(e) => setM({ ...m, url: e.target.value })} placeholder="https://mcp.example.com/mcp" />
          </Field>
        )}
      </div>
      <Field label="Authorization" hint="A secret sent as the Authorization header. Manage values under Secrets.">
        <Select value={m.authorization_secret ?? ''} onChange={(e) => setM({ ...m, authorization_secret: e.target.value || null })}>
          <option value="">None</option>
          {secrets?.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name} (…{s.last4})
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Extra headers from secrets">
        <KeyValueRows rows={Object.entries(m.header_secrets) as [string, string][]} onChange={(rows) => setM({ ...m, header_secrets: Object.fromEntries(rows) })} keyPlaceholder="X-Api-Key" valuePlaceholder="secret name" mono />
      </Field>
      <div className="rounded-2xl border border-line p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[13px] font-medium">Allowed tools</p>
            <p className="text-xs text-fg-3">{m.allowed_tools.length ? m.allowed_tools.join(', ') : 'All tools the server exposes.'}</p>
          </div>
          <Button size="sm" onClick={discover} loading={busy}>
            Test connection
          </Button>
        </div>
        {discovered && (
          <ul className="mt-3 flex flex-col gap-2">
            {discovered.map((d) => (
              <li key={d.name}>
                <label className="flex items-start gap-3 text-[13px]">
                  <Switch
                    checked={m.allowed_tools.includes(d.name)}
                    onChange={(v) => setM({ ...m, allowed_tools: v ? [...m.allowed_tools, d.name] : m.allowed_tools.filter((x) => x !== d.name) })}
                    label={d.name}
                  />
                  <span>
                    <span className="font-mono">{d.name}</span>
                    <span className="block text-xs text-fg-3">{d.description.slice(0, 200)}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button variant="primary" onClick={async () => (await save()) && onClose()} loading={busy}>
          Save server
        </Button>
        {m.id && (
          <Button variant="danger" onClick={async () => { await del(`/api/mcp/${m.id}`); invalidate('mcp', 'agents', 'landscape'); onClose() }}>
            Delete
          </Button>
        )}
      </div>
    </div>
  )
}

function McpSection() {
  const { data: servers } = useMcp()
  const [editing, setEditing] = useState<McpServer | null>(null)
  return (
    <div className="flex flex-col gap-6">
      <SectionTitle eyebrow="Model Context Protocol" title="MCP servers" action={<Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => setEditing(EMPTY_MCP)}>Add server</Button>}>
        Hosted by xAI: xAI calls the server directly, with the lowest latency. Run by Voice Stack: works with private networks and local stdio servers, with every call logged here.
      </SectionTitle>
      {servers?.length ? (
        <ul className="divide-y divide-line rounded-2xl border border-line">
          {servers.map((m) => (
            <li key={m.id}>
              <button className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-l1" onClick={() => setEditing(m)}>
                <span className="font-mono text-[13px]">{m.label}</span>
                <Badge tone={m.mode === 'xai' ? 'info' : 'neutral'}>{m.mode === 'xai' ? 'hosted by xAI' : 'run here'}</Badge>
                <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-fg-3">{m.url || m.command}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No MCP servers">Connect a server to give agents its tools.</Empty>
      )}
      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)} title={editing?.id ? editing.label : 'Add MCP server'} wide>
        {editing && <McpEditor server={editing} onClose={() => setEditing(null)} />}
      </Dialog>
    </div>
  )
}

function PluginsSection() {
  const { data: plugins } = usePlugins()
  const { data: tools } = useTools()
  const invalidate = useInvalidate()
  const [error, setError] = useState<unknown>(null)
  const registered = new Set(tools?.filter((t) => t.kind === 'plugin').map((t) => t.name))
  return (
    <div className="flex flex-col gap-6">
      <SectionTitle eyebrow="Python" title="Code plugins">
        Any LangChain tool can become an agent tool. Install a package with a <code className="font-mono">voicestack.tools</code> entry point, or drop a file using <code className="font-mono">@voice_tool</code> into PLUGINS_DIR. See docs/extending.md.
      </SectionTitle>
      <ErrorNote error={error} />
      {plugins?.length ? (
        <ul className="divide-y divide-line rounded-2xl border border-line">
          {plugins.map((p) => (
            <li key={p.name} className="flex items-center gap-3 px-4 py-3">
              <span className="font-mono text-[13px]">{p.name}</span>
              <span className="min-w-0 flex-1 truncate text-[12.5px] text-fg-3">{p.description}</span>
              {registered.has(p.name) ? (
                <Badge tone="success">available to agents</Badge>
              ) : (
                <Button
                  size="sm"
                  onClick={async () => {
                    try {
                      await post('/api/tools', { name: p.name, kind: 'plugin', description: p.description, parameters: p.parameters })
                      invalidate('tools')
                    } catch (e) {
                      setError(e)
                    }
                  }}
                >
                  Make available
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No plugins installed">Plugins load at startup from entry points and PLUGINS_DIR.</Empty>
      )}
    </div>
  )
}

function SecretsSection() {
  const { data: secrets } = useSecrets()
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  return (
    <div className="flex flex-col gap-6">
      <SectionTitle eyebrow="Encrypted at rest" title="Secrets">
        Credentials for tools and MCP servers. Reference them as <code className="font-mono">{'{{secret:NAME}}'}</code>. Values are never shown again after saving.
      </SectionTitle>
      <form
        className="grid gap-2 sm:grid-cols-[1fr_1.5fr_auto]"
        onSubmit={async (e) => {
          e.preventDefault()
          setError(null)
          try {
            await put('/api/secrets', { name, value })
            setName('')
            setValue('')
            invalidate('secrets')
          } catch (err) {
            setError(err)
          }
        }}
      >
        <Input mono placeholder="ORDERS_TOKEN" value={name} onChange={(e) => setName(e.target.value)} />
        <Input type="password" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" />
        <Button type="submit" disabled={!name || !value}>
          Save secret
        </Button>
      </form>
      <ErrorNote error={error} />
      <ul className="divide-y divide-line rounded-2xl border border-line">
        {secrets?.map((s) => (
          <li key={s.name} className="flex items-center gap-3 px-4 py-3 text-[13px]">
            <span className="font-mono">{s.name}</span>
            <span className="font-mono text-fg-3">…{s.last4}</span>
            <span className="ml-auto text-xs text-fg-4">updated {new Date(s.updated_at).toLocaleDateString()}</span>
            <IconButton label={`Delete ${s.name}`} onClick={async () => { await del(`/api/secrets/${s.name}`); invalidate('secrets') }}>
              <Trash2 className="size-3.5" />
            </IconButton>
          </li>
        ))}
        {!secrets?.length && <li className="px-4 py-6 text-center text-[13px] text-fg-3">No secrets yet.</li>}
      </ul>
    </div>
  )
}

function TransfersSection() {
  const { data: targets } = useTargets()
  const [draft, setDraft] = useState<Partial<TransferTarget>>({ name: '', uri: '', description: '' })
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  return (
    <div className="flex flex-col gap-6">
      <SectionTitle eyebrow="SIP REFER" title="Transfer lines">
        People or phone lines an agent can transfer a caller to. Use <code className="font-mono">tel:+E.164</code> for phone numbers or <code className="font-mono">sip:user@host</code> for SIP. Transfers happen on phone calls; previews simulate them.
      </SectionTitle>
      <form
        className="grid gap-2 sm:grid-cols-[1fr_1.2fr_1.4fr_auto]"
        onSubmit={async (e) => {
          e.preventDefault()
          setError(null)
          try {
            await post('/api/transfer-targets', draft)
            setDraft({ name: '', uri: '', description: '' })
            invalidate('targets')
          } catch (err) {
            setError(err)
          }
        }}
      >
        <Input placeholder="Billing team" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <Input mono placeholder="tel:+14155550123" value={draft.uri} onChange={(e) => setDraft({ ...draft, uri: e.target.value })} />
        <Input placeholder="When to use it" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        <Button type="submit" disabled={!draft.name || !draft.uri}>
          Add
        </Button>
      </form>
      <ErrorNote error={error} />
      <ul className="divide-y divide-line rounded-2xl border border-line">
        {targets?.map((t) => (
          <li key={t.id} className="flex items-center gap-3 px-4 py-3 text-[13px]">
            <span>{t.name}</span>
            <span className="font-mono text-fg-3">{t.uri}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-fg-3">{t.description}</span>
            <IconButton label={`Delete ${t.name}`} onClick={async () => { await del(`/api/transfer-targets/${t.id}`); invalidate('targets', 'agents') }}>
              <Trash2 className="size-3.5" />
            </IconButton>
          </li>
        ))}
        {!targets?.length && <li className="px-4 py-6 text-center text-[13px] text-fg-3">No transfer lines yet.</li>}
      </ul>
    </div>
  )
}

export function IntegrationsPage() {
  const { section } = useParams()
  const navigate = useNavigate()
  useEffect(() => {
    if (!section) navigate('/integrations/tools', { replace: true })
  }, [section, navigate])
  return (
    <div className="flex h-full">
      <aside className="hidden w-[var(--rail)] shrink-0 border-r border-line px-3 py-5 md:block">
        <p className="eyebrow mb-2 px-2">Integrations</p>
        <nav className="flex flex-col gap-0.5">
          {SECTIONS.map((s) => (
            <NavLink key={s.id} to={`/integrations/${s.id}`} className={({ isActive }) => cx('rounded-lg px-2 py-1.5 text-[14px]', isActive ? 'bg-l2 text-fg' : 'text-fg-2 hover:text-fg')}>
              {s.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="scroll-thin min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-5 py-8 md:px-10">
          <div className="mb-6 flex gap-1 overflow-x-auto md:hidden">
            {SECTIONS.map((s) => (
              <NavLink key={s.id} to={`/integrations/${s.id}`} className={({ isActive }) => cx('shrink-0 rounded-pill px-3 py-1 text-[13px]', isActive ? 'bg-l2 text-fg' : 'text-fg-2')}>
                {s.label}
              </NavLink>
            ))}
          </div>
          {section === 'tools' && <ToolsSection />}
          {section === 'mcp' && <McpSection />}
          {section === 'plugins' && <PluginsSection />}
          {section === 'secrets' && <SecretsSection />}
          {section === 'transfers' && <TransfersSection />}
        </div>
      </div>
    </div>
  )
}
