import { Check, Copy, PhoneOff, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Button, Card, ChipInput, Dialog, Empty, ErrorNote, Field, IconButton, Input, SectionTitle, Select, Switch, Textarea, cx } from '../../components/ui'
import { wsUrl } from '../../lib/api'
import { del, patch, post, useAgents, useInvalidate, useNumbers, useTelephonyInfo } from '../../lib/queries'
import type { PhoneNumber } from '../../lib/types'

function CopyText({ value }: { value: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      onClick={() => {
        void navigator.clipboard.writeText(value)
        setDone(true)
        setTimeout(() => setDone(false), 1200)
      }}
      className="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-inset px-2 py-1 font-mono text-[12px] text-fg-2 hover:text-fg"
    >
      <span className="truncate">{value}</span>
      {done ? <Check className="size-3 shrink-0 text-success" /> : <Copy className="size-3 shrink-0" />}
    </button>
  )
}

const PROVIDERS: Record<string, (uri: string) => string[]> = {
  Twilio: (uri) => [
    'In the Twilio Console, open Voice → Elastic SIP Trunking and create a trunk.',
    `Under Origination, add the origination URI ${uri}.`,
    'Assign your Twilio phone number to the trunk.',
    'If agents transfer calls, enable call transfer on the trunk.',
  ],
  Telnyx: () => [
    'In the Telnyx Portal, open Voice Suite → SIP Trunking and create an FQDN SIP Connection.',
    'Under Authentication and Routing, add sip.voice.x.ai as the primary FQDN on port 5060, record type A.',
    'Under Inbound, set the destination number format to E.164.',
    'Enable G.711 μ-law, G.711 A-law, or G.722.',
    'Assign the phone number to the connection.',
  ],
  Plivo: () => ['In the Plivo Console, open SIP Trunking and create a trunk.', 'Choose Inbound and create a URI with FQDN sip.voice.x.ai.', 'Link your phone number to the trunk.'],
  'Your PBX': (uri) => ['In your carrier, contact center, or PBX, create an outbound route or SIP trunk.', `Set the destination to ${uri}.`],
}

function Register({ open, onOpenChange, publicUrl }: { open: boolean; onOpenChange: (v: boolean) => void; publicUrl: string | null }) {
  const { data: agents } = useAgents()
  const [form, setForm] = useState({ e164: '', name: '', entry_agent_id: '', use_published: true, greeting_disclosure: '', register_with_xai: true, signing_secret: '', xai_phone_number_id: '' })
  const [auth, setAuth] = useState({ username: '', password: '', allowed_addresses: [] as string[] })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await post('/api/telephony/numbers', {
        ...form,
        entry_agent_id: form.entry_agent_id || null,
        signing_secret: form.signing_secret || null,
        xai_phone_number_id: form.xai_phone_number_id || null,
        sip_auth: { username: auth.username || null, password: auth.password || null, allowed_addresses: auth.allowed_addresses },
      })
      invalidate('numbers', 'landscape', 'telephony-info')
      onOpenChange(false)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Add a phone number" description="Bring your own number on a SIP trunk. xAI answers it and sends each call to this instance.">
      <div className="flex flex-col gap-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Number (E.164)">
            <Input mono value={form.e164} onChange={(e) => setForm({ ...form, e164: e.target.value.trim() })} placeholder="+18005550199" />
          </Field>
          <Field label="Name">
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Support line" />
          </Field>
          <Field label="Answered by">
            <Select value={form.entry_agent_id} onChange={(e) => setForm({ ...form, entry_agent_id: e.target.value })}>
              <option value="">Entry agent</option>
              {agents?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-1 rounded-pill border border-line-2 p-1" role="radiogroup">
          {[
            { v: true, label: 'Register with xAI now' },
            { v: false, label: 'Attach an existing registration' },
          ].map((o) => (
            <button key={String(o.v)} role="radio" aria-checked={form.register_with_xai === o.v} onClick={() => setForm({ ...form, register_with_xai: o.v })} className={cx('h-8 rounded-pill text-[13px]', form.register_with_xai === o.v ? 'bg-l3 text-fg' : 'text-fg-3')}>
              {o.label}
            </button>
          ))}
        </div>
        {form.register_with_xai ? (
          <>
            {!publicUrl && <p className="rounded-xl border border-warn/30 bg-warn/5 px-3 py-2 text-[12.5px] text-warn">Set PUBLIC_BASE_URL on the server first, so xAI can reach the call webhook.</p>}
            <Field label="Allowed carrier addresses" hint="CIDR ranges your carrier sends SIP from. Recommended.">
              <ChipInput mono values={auth.allowed_addresses} onChange={(v) => setAuth({ ...auth, allowed_addresses: v })} placeholder="203.0.113.0/24" />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="SIP digest username" hint="Optional. Configure the same credentials in your carrier.">
                <Input value={auth.username} onChange={(e) => setAuth({ ...auth, username: e.target.value })} autoComplete="off" />
              </Field>
              <Field label="SIP digest password" hint="xAI never returns it after creation.">
                <Input type="password" value={auth.password} onChange={(e) => setAuth({ ...auth, password: e.target.value })} autoComplete="new-password" />
              </Field>
            </div>
          </>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Webhook signing secret" hint="The dispatch_signing_secret from when the number was registered.">
              <Input type="password" mono value={form.signing_secret} onChange={(e) => setForm({ ...form, signing_secret: e.target.value })} placeholder="whsec_…" />
            </Field>
            <Field label="xAI phone number ID" hint="Optional. Lets this instance delete it later.">
              <Input mono value={form.xai_phone_number_id} onChange={(e) => setForm({ ...form, xai_phone_number_id: e.target.value })} placeholder="phone_…" />
            </Field>
          </div>
        )}
        <Field label="Disclosure" hint="Optional. Spoken word for word before the greeting, and cannot be interrupted.">
          <Textarea minRows={2} value={form.greeting_disclosure} onChange={(e) => setForm({ ...form, greeting_disclosure: e.target.value })} placeholder="This call may be recorded for quality purposes." />
        </Field>
        <label className="flex items-center gap-2 text-[13px] text-fg-2">
          <Switch checked={form.use_published} onChange={(v) => setForm({ ...form, use_published: v })} label="Use published versions" />
          Answer with published agent versions (recommended)
        </label>
        <ErrorNote error={error} />
        <Button variant="primary" className="w-fit" onClick={submit} loading={busy} disabled={!form.e164 || !form.name}>
          Add number
        </Button>
      </div>
    </Dialog>
  )
}

function NumberCard({ n }: { n: PhoneNumber }) {
  const { data: agents } = useAgents()
  const invalidate = useInvalidate()
  const [provider, setProvider] = useState('Twilio')
  const update = async (body: Partial<PhoneNumber>) => {
    await patch(`/api/telephony/numbers/${n.id}`, body)
    invalidate('numbers', 'landscape')
  }
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[18px]">{n.e164}</p>
          <p className="text-[13px] text-fg-3">{n.name}</p>
        </div>
        <div className="flex items-center gap-2">
          {n.has_signing_secret ? <Badge tone="success">webhook verified</Badge> : <Badge tone="danger">no signing secret</Badge>}
          <IconButton
            label="Remove number"
            onClick={async () => {
              if (!confirm(`Remove ${n.e164}? It is also deleted from xAI (the number stays with your carrier).`)) return
              await del(`/api/telephony/numbers/${n.id}`)
              invalidate('numbers', 'landscape')
            }}
          >
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label="Route calls to">
          <Select value={n.entry_agent_id ?? ''} onChange={(e) => void update({ entry_agent_id: e.target.value || null })}>
            <option value="">Entry agent</option>
            {agents?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.published_version == null && n.use_published ? ' (not published, uses draft)' : ''}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Carrier destination" hint={n.sip_host && n.sip_host !== 'sip.voice.x.ai' ? `xAI also reported SIP host ${n.sip_host}.` : undefined}>
          <CopyText value={n.sip_uri} />
        </Field>
      </div>
      <div className="mt-5">
        <div className="flex gap-1">
          {Object.keys(PROVIDERS).map((p) => (
            <button key={p} onClick={() => setProvider(p)} className={cx('rounded-pill px-3 py-1 text-[12.5px]', provider === p ? 'bg-l3 text-fg' : 'text-fg-3 hover:text-fg-2')}>
              {p}
            </button>
          ))}
        </div>
        <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[13px] text-fg-2">
          {PROVIDERS[provider](n.sip_uri).map((step) => (
            <li key={step}>{step}</li>
          ))}
          {n.sip_auth.allowed_addresses?.length ? <li>Your carrier's signaling addresses must be in {n.sip_auth.allowed_addresses.join(', ')}.</li> : null}
        </ol>
      </div>
    </Card>
  )
}

interface LiveCall {
  conversation_id: string
  channel: string
  agent: string
  call_id: string | null
  started_at: number
  events: string[]
}

function LiveCalls() {
  const [calls, setCalls] = useState<Record<string, LiveCall>>({})
  const [, tick] = useState(0)
  useEffect(() => {
    const ws = new WebSocket(wsUrl('/api/live/ws?conversation_id=*'))
    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      if (ev.type === 'snapshot') setCalls(Object.fromEntries(ev.sessions.map((s: LiveCall) => [s.conversation_id, { ...s, events: [] }])))
      else if (ev.type === 'session.started') setCalls((c) => ({ ...c, [ev.conversation_id]: { conversation_id: ev.conversation_id, channel: '…', agent: '…', call_id: null, started_at: ev.ts, events: [] } }))
      else if (ev.type === 'session.ended')
        setCalls((c) => {
          const next = { ...c }
          delete next[ev.conversation_id]
          return next
        })
      else if (ev.conversation_id)
        setCalls((c) => {
          const call = c[ev.conversation_id]
          if (!call) return c
          const line = ev.type === 'turn' ? `${ev.turn.kind}: ${ev.turn.text}` : ev.type === 'dtmf' ? `keypad ${ev.digit}` : ev.type === 'handoff' ? `handoff ${ev.from} → ${ev.to}` : null
          return { ...c, [ev.conversation_id]: { ...call, agent: ev.type === 'agent.active' ? ev.agent : call.agent, events: line ? [...call.events.slice(-5), line] : call.events } }
        })
    }
    const t = setInterval(() => tick((x) => x + 1), 1000)
    return () => {
      ws.close()
      clearInterval(t)
    }
  }, [])
  const list = Object.values(calls)
  if (!list.length) return <p className="text-[13px] text-fg-3">No live calls or previews right now.</p>
  return (
    <ul className="flex flex-col gap-2">
      {list.map((c) => (
        <li key={c.conversation_id} className="rounded-2xl border border-live/30 bg-l1 p-4">
          <div className="flex items-center gap-3">
            <span className="live-dot" />
            <span className="text-[13px]">{c.channel === 'sip' ? 'Phone call' : 'Web preview'}</span>
            <span className="font-mono text-[12px] text-fg-3">{c.agent}</span>
            <span className="ml-auto font-mono text-[12px] text-fg-3">{Math.max(0, Math.round(Date.now() / 1000 - c.started_at))}s</span>
            <Button size="sm" variant="danger" icon={<PhoneOff className="size-3.5" />} onClick={() => void post(`/api/live/${c.conversation_id}/hangup`)}>
              Hang up
            </Button>
          </div>
          {c.events.length > 0 && (
            <ul className="mt-2 space-y-0.5 font-mono text-[11.5px] text-fg-3">
              {c.events.map((e, i) => (
                <li key={i} className="truncate">
                  {e}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  )
}

export function TelephonyPage() {
  const { data: info } = useTelephonyInfo()
  const { data: numbers } = useNumbers()
  const [adding, setAdding] = useState(false)
  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="display text-[34px]">Telephony</h1>
            <p className="mt-1 max-w-xl text-[13px] text-fg-3">Route PSTN, contact-center, or PBX calls to your agents over SIP. xAI bridges the audio; this instance runs the conversation.</p>
          </div>
          <Button variant="primary" size="sm" icon={<Plus className="size-3.5" />} onClick={() => setAdding(true)}>
            Add number
          </Button>
        </div>

        <div className="mt-8 grid gap-3 md:grid-cols-3">
          <Card className="p-4">
            <p className="eyebrow">Call webhook</p>
            {info?.webhook_url ? <div className="mt-2"><CopyText value={info.webhook_url} /></div> : <p className="mt-2 text-[13px] text-warn">Set PUBLIC_BASE_URL</p>}
          </Card>
          <Card className="p-4">
            <p className="eyebrow">Server key</p>
            <p className={cx('mt-2 text-[13px]', info?.server_key_configured ? 'text-success' : 'text-warn')}>
              {info?.server_key_configured ? 'Configured' : 'Missing: calls need a stored key or XAI_API_KEY'}
            </p>
          </Card>
          <Card className="p-4">
            <p className="eyebrow">This process</p>
            <p className="mt-2 text-[13px]">role={info?.role ?? '…'}</p>
          </Card>
        </div>

        <section className="mt-10 flex flex-col gap-4">
          <SectionTitle title="Numbers" />
          {numbers?.length ? numbers.map((n) => <NumberCard key={n.id} n={n} />) : <Empty title="No numbers yet">Add a number you own on any SIP trunk: Twilio, Telnyx, Plivo, or your own PBX.</Empty>}
        </section>

        <section className="mt-10 flex flex-col gap-4">
          <SectionTitle title="Live now">Phone calls and web previews running on this instance.</SectionTitle>
          <LiveCalls />
        </section>

        <section className="mt-10 flex flex-col gap-3">
          <SectionTitle title="Recent webhooks" />
          {info?.recent_webhooks.length ? (
            <ul className="divide-y divide-line rounded-2xl border border-line font-mono text-[12px]">
              {info.recent_webhooks.map((w) => (
                <li key={w.id} className="flex gap-3 px-4 py-2">
                  <span className="text-fg-3">{new Date(w.received_at).toLocaleString()}</span>
                  <span>{w.event_type}</span>
                  <span className="ml-auto text-fg-3">{w.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-fg-3">
              None received yet. To test routing without a carrier, run <code className="font-mono">voicestack sip simulate --to +1…</code>.
            </p>
          )}
        </section>
      </div>
      <Register open={adding} onOpenChange={setAdding} publicUrl={info?.public_base_url ?? null} />
    </div>
  )
}
