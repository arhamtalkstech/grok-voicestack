import { Download, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Badge, Button, Card, ErrorNote, Input, SectionTitle, Switch } from '../../components/ui'
import { api } from '../../lib/api'
import { del, post, put, useAppSettings, useCredentials, useInvalidate } from '../../lib/queries'
import { useApp } from '../../lib/store'
import type { CredentialStatus } from '../../lib/types'

function KeyStatus({ status }: { status?: CredentialStatus }) {
  if (!status?.source) return <Badge tone="warn">not set</Badge>
  return (
    <Badge tone="success">
      {status.source === 'workspace' ? 'saved here' : 'from environment'} · …{status.last4}
    </Badge>
  )
}

function WorkspaceKey({ name, title, hint, status, validate }: { name: string; title: string; hint: string; status?: CredentialStatus; validate: boolean }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[14px] font-medium">{title}</p>
        <KeyStatus status={status} />
      </div>
      <p className="mt-1 text-xs leading-relaxed text-fg-3">{hint}</p>
      <form
        className="mt-4 flex gap-2"
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setError(null)
          try {
            await put(`/api/settings/credentials/${name}`, { value, skip_validation: !validate })
            setValue('')
            invalidate('credentials', 'voices', 'telephony-info')
          } catch (err) {
            setError(err)
          } finally {
            setBusy(false)
          }
        }}
      >
        <Input type="password" mono autoComplete="off" placeholder="xai-…" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button type="submit" loading={busy} disabled={value.length < 8}>
          {validate ? 'Check and save' : 'Save'}
        </Button>
        {status?.source === 'workspace' && (
          <Button
            type="button"
            variant="danger"
            onClick={async () => {
              await del(`/api/settings/credentials/${name}`)
              invalidate('credentials', 'voices', 'telephony-info')
            }}
          >
            Remove
          </Button>
        )}
      </form>
      <ErrorNote error={error} />
    </Card>
  )
}

function SessionKey() {
  const sessionKey = useApp((s) => s.sessionKey)
  const setSessionKey = useApp((s) => s.setSessionKey)
  const [value, setValue] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const invalidate = useInvalidate()
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[14px] font-medium">Session-only key</p>
        {sessionKey ? <Badge tone="info">active · …{sessionKey.slice(-4)}</Badge> : <Badge>off</Badge>}
      </div>
      <p className="mt-1 text-xs leading-relaxed text-fg-3">
        Kept in this tab's memory and sent with each request. Never stored on the server or in the browser, and gone when you reload. It overrides the saved key for previews, voices, and the optimiser. Phone calls cannot use it.
      </p>
      {sessionKey ? (
        <Button className="mt-4" onClick={() => { setSessionKey(null); invalidate('voices') }}>
          Forget key
        </Button>
      ) : (
        <form
          className="mt-4 flex gap-2"
          onSubmit={async (e) => {
            e.preventDefault()
            setBusy(true)
            setError(null)
            try {
              await post('/api/settings/credentials/test-session-key', { value })
              setSessionKey(value.trim())
              setValue('')
              invalidate('voices')
            } catch (err) {
              setError(err)
            } finally {
              setBusy(false)
            }
          }}
        >
          <Input type="password" mono autoComplete="off" placeholder="xai-…" value={value} onChange={(e) => setValue(e.target.value)} />
          <Button type="submit" loading={busy} disabled={value.length < 8}>
            Use for this session
          </Button>
        </form>
      )}
      <ErrorNote error={error} />
    </Card>
  )
}

function ImportExport() {
  const input = useRef<HTMLInputElement>(null)
  const [replace, setReplace] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  return (
    <Card className="p-5">
      <p className="text-[14px] font-medium">Agents as code</p>
      <p className="mt-1 text-xs leading-relaxed text-fg-3">Export agents, handoffs, tools, MCP servers, and transfer lines as YAML to version them in git, or apply a file. The same format works with <code className="font-mono">voicestack apply -f</code>. Secret values are never exported.</p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          icon={<Download className="size-3.5" />}
          onClick={async () => {
            const text = await api<string>('/api/landscape/export')
            const url = URL.createObjectURL(new Blob([text], { type: 'text/yaml' }))
            const a = document.createElement('a')
            a.href = url
            a.download = 'voicestack.yaml'
            a.click()
            URL.revokeObjectURL(url)
          }}
        >
          Export YAML
        </Button>
        <input
          ref={input}
          type="file"
          accept=".yaml,.yml,text/yaml"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            setError(null)
            try {
              const r = await api<Record<string, number>>(`/api/landscape/import?replace=${replace}`, { method: 'POST', body: await file.text(), headers: { 'Content-Type': 'text/plain' } })
              setResult(Object.entries(r).map(([k, v]) => `${v} ${k.replace('_', ' ')}`).join(', '))
              invalidate('agents', 'landscape', 'tools', 'mcp', 'knowledge', 'targets')
            } catch (err) {
              setError(err)
            } finally {
              e.target.value = ''
            }
          }}
        />
        <Button icon={<Upload className="size-3.5" />} onClick={() => input.current?.click()}>
          Apply YAML
        </Button>
        <label className="ml-2 flex items-center gap-2 text-[13px] text-fg-2">
          <Switch checked={replace} onChange={setReplace} label="Replace everything" /> Replace existing agents
        </label>
      </div>
      {result && <p className="mt-3 text-[13px] text-success">Applied: {result}.</p>}
      <ErrorNote error={error} />
    </Card>
  )
}

export function SettingsPage() {
  const { data: creds } = useCredentials()
  const { data: app } = useAppSettings()
  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-5 py-8 md:px-10">
        <h1 className="display text-[34px]">Settings</h1>
        <section className="mt-8 flex flex-col gap-4">
          <SectionTitle eyebrow="Bring your own key" title="xAI keys">
            Keys are used server-side only. Browsers get short-lived ephemeral tokens for live previews, never your key. Saved keys are encrypted at rest.
          </SectionTitle>
          <WorkspaceKey name="xai_api_key" title="Workspace API key" hint="Used for previews, voices, the optimiser, summaries, and phone calls. Falls back to XAI_API_KEY from the environment." status={creds?.xai_api_key} validate />
          <SessionKey />
        </section>
        <section className="mt-10 flex flex-col gap-4">
          <SectionTitle title="Landscape" />
          <ImportExport />
        </section>
        {app && (
          <section className="mt-10 flex flex-col gap-3">
            <SectionTitle title="This instance" />
            <dl className="grid grid-cols-[180px_1fr] gap-y-2 rounded-2xl border border-line p-5 text-[13px]">
              {Object.entries({
                Version: app.version,
                'Voice model': app.voice_model,
                'Text model': app.text_model,
                'Handoff voice mode': app.handoff_voice_mode,
                Database: app.database,
                Embeddings: `${app.embeddings_provider} · ${app.embeddings_model}`,
                Role: app.role,
                'Builder access': app.auth_mode,
                'Public URL': app.public_base_url ?? 'not set',
              }).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-fg-3">{k}</dt>
                  <dd className="font-mono text-[12.5px]">{v}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>
    </div>
  )
}
