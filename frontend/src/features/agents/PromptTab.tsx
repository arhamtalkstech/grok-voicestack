import { Sparkles } from 'lucide-react'
import { useState, type MutableRefObject } from 'react'
import { Button, Field, Select, Switch, Textarea, cx } from '../../components/ui'
import type { SectionKey } from '../../lib/types'
import type { Draft, Update } from './AgentsPage'
import { OptimizeDialog } from './OptimizeDialog'

export const SECTIONS: { key: SectionKey; title: string; hint: string; placeholder: string }[] = [
  { key: 'role', title: 'Role & Persona', hint: 'Who the agent is: identity, brand, and disposition. Write in second person.', placeholder: 'You are a calm, efficient support agent for Acme Internet.' },
  { key: 'objective', title: 'Objective', hint: 'What done looks like, in one or two sentences.', placeholder: "Resolve the caller's billing question, or hand them to the right specialist." },
  { key: 'flow', title: 'Conversation Flow', hint: "How the call goes from the caller's first response. Name only tools this agent has; transfer and knowledge lines are added for you.", placeholder: '- Ask one question at a time until you know the issue.\n- Confirm the account email before looking anything up.' },
  { key: 'guardrails', title: 'Guardrails & Escalation', hint: 'Scope, refusals, when to escalate, and the safety path.', placeholder: 'Stay within billing. If the caller mentions self-harm or an emergency, respond with empathy and point them to emergency services.' },
  { key: 'style', title: 'Voice & Communication Style', hint: 'How replies are worded for speech: length, tone, language, how to read numbers.', placeholder: 'Spoken word only: no markdown or lists. One or two short sentences per turn.' },
  { key: 'critical', title: 'CRITICAL INSTRUCTIONS', hint: 'Optional. Only absolute, non-negotiable rules. Keep it short.', placeholder: 'NEVER read out a full card number.' },
]

export function PromptTab({ draft, update, sectionRefs }: { draft: Draft; update: Update; sectionRefs: MutableRefObject<Record<string, HTMLElement | null>> }) {
  const [optimizing, setOptimizing] = useState(false)
  const setSection = (key: SectionKey, value: string) => update({ prompt_sections: { ...draft.prompt_sections, [key]: value } })

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid grid-cols-2 gap-1 rounded-pill border border-line-2 p-1" role="radiogroup" aria-label="Prompt format">
          {(['sections', 'raw'] as const).map((m) => (
            <button
              key={m}
              role="radio"
              aria-checked={draft.prompt_mode === m}
              onClick={() => update({ prompt_mode: m })}
              className={cx('h-8 rounded-pill px-4 text-[13px] transition-colors', draft.prompt_mode === m ? 'bg-l3 text-fg' : 'text-fg-3 hover:text-fg-2')}
            >
              {m === 'sections' ? 'Guided sections' : 'Single prompt'}
            </button>
          ))}
        </div>
        <Button variant="outline" size="sm" icon={<Sparkles className="size-3.5" />} onClick={() => setOptimizing(true)}>
          Optimise with guide
        </Button>
      </div>

      {draft.prompt_mode === 'sections' ? (
        SECTIONS.map((s) => (
          <section key={s.key} ref={(el) => { sectionRefs.current[s.key] = el }} className="scroll-mt-24">
            <Field label={<span className="font-mono text-[12px] text-fg-2">## {s.title}</span>} hint={s.hint}>
              <Textarea value={draft.prompt_sections[s.key] ?? ''} onChange={(e) => setSection(s.key, e.target.value)} placeholder={s.placeholder} minRows={s.key === 'flow' ? 5 : 3} />
            </Field>
          </section>
        ))
      ) : (
        <Field label="System prompt" hint="Use ## headers for the guide's sections so the checks can read them.">
          <Textarea mono minRows={18} value={draft.raw_prompt} onChange={(e) => update({ raw_prompt: e.target.value })} placeholder="## Role & Persona&#10;You are…" />
        </Field>
      )}

      <section ref={(el) => { sectionRefs.current.facts = el }}>
        <Field label="Business facts" hint="Hours, prices, policies, URLs. Added verbatim after the persona. Long documents belong in a knowledge base.">
          <Textarea value={draft.key_facts} onChange={(e) => update({ key_facts: e.target.value })} placeholder={'Open 8am–8pm Pacific, Monday to Saturday.\nThe website is https://acme.example'} minRows={3} />
        </Field>
      </section>

      <section className="rounded-2xl border border-line p-5">
        <p className="text-[14px] font-medium">Greeting</p>
        <p className="mt-1 text-xs text-fg-3">The first line of a new call. Kept separate from the prompt, as the guide recommends.</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-[180px_1fr]">
          <Field label="How">
            <Select value={draft.greeting_mode} onChange={(e) => update({ greeting_mode: e.target.value as Draft['greeting_mode'] })}>
              <option value="model">Agent words it</option>
              <option value="verbatim">Say exactly</option>
              <option value="none">Wait for caller</option>
            </Select>
          </Field>
          <Field label="Line" hint={draft.greeting_mode === 'verbatim' ? 'Spoken word for word with text-to-speech (force_message). Good for disclosures.' : 'The agent greets with this meaning in natural words.'}>
            <Textarea minRows={2} value={draft.greeting} disabled={draft.greeting_mode === 'none'} onChange={(e) => update({ greeting: e.target.value })} placeholder="Thanks for calling Acme. How can I help?" />
          </Field>
        </div>
        {draft.greeting_mode === 'verbatim' && (
          <label className="mt-3 flex items-center gap-2 text-[13px] text-fg-2">
            <Switch checked={!draft.greeting_interruptible} onChange={(v) => update({ greeting_interruptible: !v })} label="Cannot be interrupted" />
            Caller cannot interrupt this line
          </label>
        )}
      </section>

      <OptimizeDialog open={optimizing} onOpenChange={setOptimizing} draft={draft} update={update} />
    </div>
  )
}
