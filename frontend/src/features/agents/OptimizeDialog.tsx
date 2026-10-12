import { diffWords } from 'diff'
import { Check } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Dialog, ErrorNote, Field, Textarea, cx } from '../../components/ui'
import { post } from '../../lib/queries'
import type { Lint, SectionKey } from '../../lib/types'
import type { Draft, Update } from './AgentsPage'
import { SECTIONS } from './PromptTab'

interface Variant {
  sections: Record<SectionKey, string>
  changes: { section: SectionKey; change: string; reason: string }[]
  lint_after: Lint
  warnings: string[]
}

interface Result {
  mode: string
  before: { sections: Partial<Record<SectionKey, string>>; lint: Lint }
  critique: { quote: string; problem: string; guide_rule: string }[]
  variants: Variant[]
  attempts: number
  guide_source: string
}

const MODES = [
  { id: 'align', label: 'Align with guide', hint: "Restructure and tighten the prompt to follow xAI's prompting guide." },
  { id: 'fix_issue', label: 'Fix an issue', hint: 'Describe what goes wrong in calls. Returns 2–3 variants.' },
  { id: 'simplify', label: 'Simplify', hint: 'Shorten a long prompt and remove workarounds while keeping behavior.' },
] as const

function Diff({ before, after }: { before: string; after: string }) {
  const parts = diffWords(before, after)
  return (
    <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed">
      {parts.map((p, i) => (
        <span key={i} className={cx(p.added && 'rounded bg-success/15 text-success', p.removed && 'rounded bg-danger/10 text-danger line-through decoration-danger/50')}>
          {p.value}
        </span>
      ))}
    </p>
  )
}

export function OptimizeDialog({ open, onOpenChange, draft, update }: { open: boolean; onOpenChange: (v: boolean) => void; draft: Draft; update: Update }) {
  const [mode, setMode] = useState<(typeof MODES)[number]['id']>('align')
  const [issue, setIssue] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [variant, setVariant] = useState(0)
  const [accepted, setAccepted] = useState<Set<SectionKey>>(new Set())
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    setAccepted(new Set())
    try {
      const body = { mode, issue, prompt_mode: draft.prompt_mode, prompt_sections: draft.prompt_sections, raw_prompt: draft.raw_prompt, key_facts: draft.key_facts, language_hint: draft.language_hint }
      setResult(await post<Result>(`/api/agents/${draft.id}/prompt/optimize`, body))
      setVariant(0)
    } catch (e) {
      setError(e)
    } finally {
      setRunning(false)
    }
  }

  const v = result?.variants[variant]
  const apply = (keys: SectionKey[]) => {
    if (!v) return
    const next = { ...(draft.prompt_mode === 'sections' ? draft.prompt_sections : result?.before.sections ?? {}) }
    for (const k of keys) next[k] = v.sections[k]
    update({ prompt_mode: 'sections', prompt_sections: next })
    setAccepted((s) => new Set([...s, ...keys]))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Optimise with the prompting guide" description="Grok rewrites this prompt against xAI's speech-to-speech prompting guide. Facts, URLs, and tool names are checked so nothing is invented or dropped.">
      <div className="flex flex-col gap-5">
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup">
          {MODES.map((m) => (
            <button
              key={m.id}
              role="radio"
              aria-checked={mode === m.id}
              onClick={() => setMode(m.id)}
              className={cx('rounded-2xl border p-3 text-left transition-colors', mode === m.id ? 'border-fg/50 bg-l2' : 'border-line hover:border-line-2')}
            >
              <p className="text-[13.5px] font-medium">{m.label}</p>
              <p className="mt-1 text-xs leading-relaxed text-fg-3">{m.hint}</p>
            </button>
          ))}
        </div>
        {mode === 'fix_issue' && (
          <Field label="What goes wrong?">
            <Textarea minRows={2} value={issue} onChange={(e) => setIssue(e.target.value)} placeholder="It reads order numbers too fast and callers ask it to repeat them." />
          </Field>
        )}
        <div className="flex items-center gap-3">
          <Button variant="primary" onClick={run} loading={running} disabled={mode === 'fix_issue' && !issue.trim()}>
            {result ? 'Run again' : 'Optimise'}
          </Button>
          {running && <span className="shimmer text-[13px]">Checking the prompt, critiquing, rewriting, validating…</span>}
        </div>
        <ErrorNote error={error} />

        {result && v && (
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-l1 p-4">
              <div>
                <p className="eyebrow">Prompt check</p>
                <p className="mt-1 font-mono text-[15px]">
                  {result.before.lint.score} <span className="text-fg-3">→</span> <span className="text-success">{v.lint_after.score}</span>
                </p>
              </div>
              <div className="ml-4">
                <p className="eyebrow">Critique</p>
                <p className="mt-1 text-[13px]">{result.critique.length} issues found</p>
              </div>
              {result.variants.length > 1 && (
                <div className="ml-auto flex gap-1">
                  {result.variants.map((_, i) => (
                    <Button key={i} size="sm" variant={i === variant ? 'primary' : 'secondary'} onClick={() => { setVariant(i); setAccepted(new Set()) }}>
                      Variant {i + 1}
                    </Button>
                  ))}
                </div>
              )}
              <Button size="sm" className={result.variants.length > 1 ? '' : 'ml-auto'} onClick={() => apply(SECTIONS.map((s) => s.key))}>
                Accept all
              </Button>
            </div>
            {v.warnings.map((w) => (
              <p key={w} className="text-[12.5px] text-warn">
                {w}
              </p>
            ))}
            {result.critique.length > 0 && (
              <details className="rounded-2xl border border-line p-4">
                <summary className="cursor-pointer text-[13px] font-medium">What the critique found</summary>
                <ul className="mt-3 flex flex-col gap-2 text-[12.5px]">
                  {result.critique.map((c, i) => (
                    <li key={i}>
                      <span className="font-mono text-fg-3">“{c.quote}”</span> — {c.problem} <span className="text-fg-4">({c.guide_rule})</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {SECTIONS.map((s) => {
              const before = (result.before.sections[s.key] ?? '').trim()
              const after = (v.sections[s.key] ?? '').trim()
              if (!before && !after) return null
              const changes = v.changes.filter((c) => c.section === s.key)
              const same = before === after
              return (
                <div key={s.key} className="rounded-2xl border border-line">
                  <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
                    <p className="font-mono text-[12px] text-fg-2">## {s.title}</p>
                    {same ? (
                      <Badge>unchanged</Badge>
                    ) : accepted.has(s.key) ? (
                      <Badge tone="success">
                        <Check className="size-3" /> accepted
                      </Badge>
                    ) : (
                      <Button size="sm" onClick={() => apply([s.key])}>
                        Accept
                      </Button>
                    )}
                  </div>
                  {!same && (
                    <div className="grid gap-4 p-4 md:grid-cols-[1fr_220px]">
                      <Diff before={before} after={after} />
                      <ul className="flex flex-col gap-2 text-[12px] text-fg-3">
                        {changes.map((c, i) => (
                          <li key={i}>
                            <span className="text-fg-2">{c.change}</span>
                            <span className="block text-fg-4">{c.reason}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            })}
            <p className="text-[11px] text-fg-4">{result.guide_source.replace(/<!--|-->/g, '').trim()}</p>
          </div>
        )}
      </div>
    </Dialog>
  )
}
