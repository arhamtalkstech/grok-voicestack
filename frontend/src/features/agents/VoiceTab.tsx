import { Check, Loader2, Pause, Play, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { Badge, Button, ErrorNote, Field, Input, Select, Slider, Switch, cx } from '../../components/ui'
import { api } from '../../lib/api'
import { useInvalidate, useVoices } from '../../lib/queries'
import type { Voice } from '../../lib/types'
import { Voiceprint } from '../../voiceprint/Voiceprint'
import type { Draft, Update } from './AgentsPage'

const cache = new Map<string, string>()
let currentAudio: HTMLAudioElement | null = null

function usePreview() {
  const [playing, setPlaying] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const play = async (voiceId: string, speed: number, text?: string) => {
    const key = `${voiceId}|${speed}|${text ?? ''}`
    currentAudio?.pause()
    if (playing === key) {
      setPlaying(null)
      return
    }
    setError(null)
    try {
      let url = cache.get(key)
      if (!url) {
        setLoading(key)
        const blob = await api<Blob>('/api/voices/preview', { method: 'POST', json: { voice_id: voiceId, speed, ...(text ? { text } : {}) } })
        url = URL.createObjectURL(blob)
        cache.set(key, url)
      }
      const audio = new Audio(url)
      currentAudio = audio
      audio.onended = () => setPlaying(null)
      setPlaying(key)
      await audio.play()
    } catch (e) {
      setError(e)
      setPlaying(null)
    } finally {
      setLoading(null)
    }
  }
  return { play, playing, loading, error }
}

function VoiceCard({ voice, selected, agentName, speed, onSelect, preview }: { voice: Voice; selected: boolean; agentName: string; speed: number; onSelect: () => void; preview: ReturnType<typeof usePreview> }) {
  const key = `${voice.voice_id}|${speed}|`
  const label = voice.name || voice.voice_id
  const meta = [voice.gender, voice.tone, voice.accent, voice.language].filter(Boolean).join(' · ')
  return (
    <div className={cx('relative flex flex-col gap-3 rounded-2xl border p-4 transition-colors', selected ? 'border-fg/60 bg-l2' : 'border-line bg-l1 hover:border-line-2')}>
      <button className="absolute inset-0 rounded-2xl" aria-label={`Use ${label}`} aria-pressed={selected} onClick={onSelect} />
      <div className="flex items-center gap-3">
        <Voiceprint seed={{ voice: voice.voice_id, name: agentName, speed }} size={36} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium capitalize">{label}</p>
          <p className="truncate font-mono text-[11px] text-fg-3">{voice.voice_id}</p>
        </div>
        {selected && <Check className="size-4 text-fg" />}
      </div>
      {(voice.description || meta) && <p className="line-clamp-2 text-[12px] leading-relaxed text-fg-3">{String(voice.description || meta)}</p>}
      <button
        onClick={() => void preview.play(voice.voice_id, speed)}
        className="relative z-10 inline-flex w-fit items-center gap-1.5 rounded-pill border border-line-2 px-2.5 py-1 text-[12px] text-fg-2 hover:border-line-strong hover:text-fg"
      >
        {preview.loading === key ? <Loader2 className="size-3 animate-spin" /> : preview.playing === key ? <Pause className="size-3" /> : <Play className="size-3" />}
        Sample at {speed}×
      </button>
    </div>
  )
}

function CustomVoiceForm({ notice, onCreated }: { notice: string; onCreated: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [consent, setConsent] = useState(false)
  const [language, setLanguage] = useState('en')
  const [tone, setTone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const input = useRef<HTMLInputElement>(null)
  const submit = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('name', name || file.name)
      form.append('consent', String(consent))
      form.append('language', language)
      if (tone) form.append('tone', tone)
      const voice = await api<{ voice_id: string }>('/api/voices/custom', { method: 'POST', body: form })
      onCreated(voice.voice_id)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-line p-5">
      <p className="text-[14px] font-medium">Clone a voice</p>
      <p className="text-xs leading-relaxed text-fg-3">{notice}</p>
      <p className="text-xs leading-relaxed text-fg-3">Upload up to 120 seconds of one speaker in a quiet room (90–120 s works best). WAV at 24 kHz is recommended. Record the way the agent should sound.</p>
      <input ref={input} type="file" accept="audio/*,video/mp4" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <Button variant="outline" icon={<Upload className="size-4" />} onClick={() => input.current?.click()} className="w-fit">
        {file ? file.name : 'Choose a reference clip'}
      </Button>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Support voice" />
        </Field>
        <Field label="Language">
          <Input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" />
        </Field>
        <Field label="Tone">
          <Select value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="">—</option>
            {['warm', 'casual', 'professional', 'friendly', 'authoritative', 'expressive', 'calm'].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
      </div>
      <label className="flex items-start gap-2 text-[13px] text-fg-2">
        <Switch checked={consent} onChange={setConsent} label="Speaker consent" />
        <span>The person in this recording agreed to have their voice cloned for this use.</span>
      </label>
      <ErrorNote error={error} />
      <Button variant="primary" className="w-fit" onClick={submit} loading={busy} disabled={!file || !consent}>
        Create voice
      </Button>
    </div>
  )
}

export function VoiceTab({ draft, update }: { draft: Draft; update: Update }) {
  const { data, error, isLoading } = useVoices()
  const preview = usePreview()
  const invalidate = useInvalidate()
  const [manualId, setManualId] = useState('')
  const [speed, setSpeed] = useState(draft.speed)
  const known = new Set([...(data?.builtin ?? []), ...(data?.custom ?? [])].map((v) => v.voice_id.toLowerCase()))

  return (
    <div className="flex flex-col gap-8">
      <section>
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[14px] font-medium">Speaking speed</p>
            <p className="mt-1 text-xs text-fg-3">Applies to everything this agent says. 0.7× is slower, 1.5× is faster.</p>
          </div>
          <span className="font-mono text-[22px]">{speed.toFixed(2)}×</span>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <span className="font-mono text-[11px] text-fg-3">0.7</span>
          <Slider label="Speaking speed" value={speed} min={0.7} max={1.5} step={0.05} onChange={setSpeed} onCommit={(v) => update({ speed: Math.round(v * 100) / 100 })} />
          <span className="font-mono text-[11px] text-fg-3">1.5</span>
          <Button size="sm" variant="outline" icon={<Play className="size-3" />} onClick={() => void preview.play(draft.voice_id, speed)}>
            Preview
          </Button>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <p className="text-[14px] font-medium">Voice</p>
          <span className="font-mono text-[12px] text-fg-3">selected: {draft.voice_id}</span>
        </div>
        {error ? (
          <div className="rounded-2xl border border-line p-4 text-[13px] text-fg-2">
            Voices load from the xAI API. {(error as Error).message}{' '}
            <Link to="/settings" className="text-fg underline">
              Add a key in Settings
            </Link>
            .
          </div>
        ) : isLoading ? (
          <p className="shimmer text-[13px]">Loading voices from xAI…</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data?.builtin.map((v) => (
              <VoiceCard key={v.voice_id} voice={v} agentName={draft.name} speed={speed} selected={draft.voice_id.toLowerCase() === v.voice_id.toLowerCase()} onSelect={() => update({ voice_id: v.voice_id })} preview={preview} />
            ))}
          </div>
        )}
        <ErrorNote error={preview.error} />
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <p className="text-[14px] font-medium">Custom voices</p>
          <Badge tone="info">US only</Badge>
        </div>
        <p className="rounded-xl border border-info/25 bg-info/5 px-3 py-2 text-[12.5px] leading-relaxed text-fg-2">
          {data?.custom_notice ?? 'Custom voices are available only in the United States, excluding Illinois. Teams in other countries need to contact the xAI sales team.'}
        </p>
        {data?.custom_error && <p className="text-[12.5px] text-fg-3">Custom voices: {data.custom_error}</p>}
        {data && data.custom.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.custom.map((v) => (
              <VoiceCard key={v.voice_id} voice={v} agentName={draft.name} speed={speed} selected={draft.voice_id === v.voice_id} onSelect={() => update({ voice_id: v.voice_id })} preview={preview} />
            ))}
          </div>
        )}
        <Field label="Use a voice ID" hint="Created a voice in the xAI console? Copy its voice ID (8 characters) and paste it here.">
          <div className="flex gap-2">
            <Input mono value={manualId} onChange={(e) => setManualId(e.target.value.trim())} placeholder="nlbqfwie" maxLength={64} />
            <Button disabled={!manualId} onClick={() => update({ voice_id: manualId })}>
              Use
            </Button>
          </div>
        </Field>
        {!known.has(draft.voice_id.toLowerCase()) && data && <p className="text-[12.5px] text-warn">“{draft.voice_id}” is not in your voice list. Check the ID before taking calls.</p>}
        <CustomVoiceForm
          notice={data?.custom_notice ?? ''}
          onCreated={(id) => {
            invalidate('voices')
            update({ voice_id: id })
          }}
        />
      </section>
    </div>
  )
}
