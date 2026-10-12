import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button, ErrorNote, Field, IconButton, Input, Select, Switch, Textarea } from '../../components/ui'
import { del, patch, useInvalidate } from '../../lib/queries'
import type { ContextField, Edge } from '../../lib/types'

export function EdgeEditor({
  edge,
  sourceName,
  targetName,
  targetSlug,
  onDeleted,
}: {
  edge: Edge
  sourceName: string
  targetName: string
  targetSlug: string
  onDeleted?: () => void
}) {
  const [draft, setDraft] = useState(edge)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState(false)
  const invalidate = useInvalidate()
  useEffect(() => {
    setDraft(edge)
  }, [edge])

  const update = (fields: Partial<Edge>) => {
    setSaved(false)
    setDraft((d) => ({ ...d, ...fields }))
  }
  const setField = (i: number, f: Partial<ContextField>) => update({ context_fields: draft.context_fields.map((c, j) => (j === i ? { ...c, ...f } : c)) })
  const toolName = `transfer_to_${targetSlug.replace(/-/g, '_')}`

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await patch(`/api/edges/${edge.id}`, {
        description: draft.description,
        context_fields: draft.context_fields.filter((f) => f.name.trim()),
        handoff_greeting: draft.handoff_greeting,
        voice_policy: draft.voice_policy,
      })
      invalidate('landscape', 'agents')
      setSaved(true)
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="eyebrow mb-1">Handoff</p>
        <p className="text-[15px] font-medium">
          {sourceName} <span className="text-fg-3">→</span> {targetName}
        </p>
        <p className="mt-1 text-[12px] text-fg-3">
          {sourceName} gets a tool named <code className="font-mono text-fg-2">{toolName}</code>.
        </p>
      </div>
      <Field label="When should this happen?" hint="Becomes the tool description and a line in the agent's Conversation Flow.">
        <Textarea minRows={2} value={draft.description} placeholder="the caller asks about billing or a charge" onChange={(e) => update({ description: e.target.value })} />
      </Field>
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-medium">Context to pass</p>
          <Button size="sm" variant="ghost" icon={<Plus className="size-3.5" />} onClick={() => update({ context_fields: [...draft.context_fields, { name: '', type: 'string', description: '', required: false }] })}>
            Add field
          </Button>
        </div>
        <p className="text-xs text-fg-3">The model fills these when it hands off. Required fields must be collected first. A reason and summary are always included.</p>
        {draft.context_fields.map((f, i) => (
          <div key={i} className="grid grid-cols-[1fr_96px_auto] items-center gap-2 rounded-xl border border-line p-2">
            <Input mono placeholder="field_name" value={f.name} onChange={(e) => setField(i, { name: e.target.value.replace(/[^a-z0-9_]/gi, '_').toLowerCase() })} />
            <Select value={f.type} onChange={(e) => setField(i, { type: e.target.value as ContextField['type'] })}>
              <option value="string">text</option>
              <option value="number">number</option>
              <option value="integer">integer</option>
              <option value="boolean">yes/no</option>
            </Select>
            <IconButton label="Remove field" onClick={() => update({ context_fields: draft.context_fields.filter((_, j) => j !== i) })}>
              <Trash2 className="size-3.5" />
            </IconButton>
            <Input className="col-span-2" placeholder="What it means" value={f.description} onChange={(e) => setField(i, { description: e.target.value })} />
            <label className="flex items-center gap-2 text-xs text-fg-3">
              <Switch checked={f.required} onChange={(v) => setField(i, { required: v })} label="Required" /> required
            </label>
          </div>
        ))}
      </div>
      <Field label="Voice" hint="Switch to the next agent's voice, or keep the caller on the same voice.">
        <Select value={draft.voice_policy} onChange={(e) => update({ voice_policy: e.target.value as Edge['voice_policy'] })}>
          <option value="switch">Switch to {targetName}'s voice</option>
          <option value="keep">Keep the current voice</option>
        </Select>
      </Field>
      <Field label="First line after handoff" hint="Optional. Leave empty to let the next agent introduce itself.">
        <Input value={draft.handoff_greeting} placeholder={`Hi, this is ${targetName}. I can help with that.`} onChange={(e) => update({ handoff_greeting: e.target.value })} />
      </Field>
      <ErrorNote error={error} />
      <div className="flex items-center gap-2">
        <Button variant="primary" onClick={save} loading={saving}>
          {saved ? 'Saved' : 'Save handoff'}
        </Button>
        <Button
          variant="danger"
          onClick={async () => {
            await del(`/api/edges/${edge.id}`)
            invalidate('landscape', 'agents')
            onDeleted?.()
          }}
        >
          Delete
        </Button>
      </div>
    </div>
  )
}
