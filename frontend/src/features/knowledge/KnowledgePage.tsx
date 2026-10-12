import { FileText, Plus, Search, Trash2, UploadCloud } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router'
import { Badge, Button, Dialog, Empty, ErrorNote, Field, IconButton, Input, Select, Textarea, cx } from '../../components/ui'
import { api } from '../../lib/api'
import { del, post, useInvalidate, useKnowledge } from '../../lib/queries'
import type { KnowledgeBase } from '../../lib/types'

function NewKb({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState<'local' | 'collections'>('collections')
  const [collectionId, setCollectionId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalidate = useInvalidate()
  const navigate = useNavigate()
  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const kb = await post<KnowledgeBase>('/api/knowledge', { name, description, mode, collection_id: collectionId.trim() || null })
      invalidate('knowledge')
      onOpenChange(false)
      navigate(`/knowledge/${kb.id}`)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New knowledge base">
      <div className="flex flex-col gap-4">
        <Field label="Name">
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Product manuals" />
        </Field>
        <Field label="Description" hint="Shown to the agent as what this knowledge covers.">
          <Textarea minRows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Where it lives">
          <Select value={mode} onChange={(e) => setMode(e.target.value as 'local' | 'collections')}>
            <option value="collections">xAI Collections: Files API, searched by xAI during calls (recommended)</option>
            <option value="local">In Voice Stack: local LangChain retriever, files never leave this server</option>
          </Select>
        </Field>
        {mode === 'collections' && (
          <Field label="Existing collection ID" hint="Optional. Leave empty and Voice Stack creates a collection with your API key.">
            <Input mono value={collectionId} onChange={(e) => setCollectionId(e.target.value)} placeholder="collection_…" />
          </Field>
        )}
        <ErrorNote error={error} />
        <Button variant="primary" onClick={submit} loading={busy} disabled={!name.trim()}>
          Create
        </Button>
      </div>
    </Dialog>
  )
}

function KbDetail({ kb }: { kb: KnowledgeBase }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<{ text: string; source?: string; page?: number; score?: number }[] | null>(null)
  const [searching, setSearching] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const invalidate = useInvalidate()
  const navigate = useNavigate()
  useEffect(() => {
    setResults(null)
  }, [kb.id])

  const upload = async (files: FileList | File[]) => {
    if (!files.length) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      for (const f of Array.from(files)) form.append('files', f)
      await api(`/api/knowledge/${kb.id}/documents`, { method: 'POST', body: form })
      invalidate('knowledge')
    } catch (e) {
      setError(e)
    } finally {
      setUploading(false)
    }
  }

  const search = async () => {
    setSearching(true)
    setError(null)
    try {
      const r = await post<{ results: typeof results }>(`/api/knowledge/${kb.id}/search`, { query, k: kb.top_k })
      setResults(r.results ?? [])
    } catch (e) {
      setError(e)
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 md:px-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{kb.mode === 'local' ? 'Local · LangChain retriever' : `xAI Collection · ${kb.collection_id ?? 'created on first upload'}`}</p>
          <h1 className="display mt-2 text-[30px]">{kb.name}</h1>
          {kb.description && <p className="mt-1 text-[13px] text-fg-3">{kb.description}</p>}
        </div>
        <Button
          size="sm"
          variant="danger"
          icon={<Trash2 className="size-3.5" />}
          onClick={async () => {
            if (!confirm(`Delete ${kb.name} and its indexed chunks?`)) return
            await del(`/api/knowledge/${kb.id}`)
            invalidate('knowledge')
            navigate('/knowledge')
          }}
        >
          Delete
        </Button>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          void upload(e.dataTransfer.files)
        }}
        className={cx('mt-8 flex flex-col items-center gap-3 rounded-3xl border border-dashed px-6 py-10 text-center transition-colors', dragging ? 'border-fg bg-l2' : 'border-line-2')}
      >
        <UploadCloud className="size-6 text-fg-3" />
        <p className="text-[14px]">Drop files here</p>
        <p className="text-xs text-fg-3">PDF, DOCX, Markdown, text, HTML, CSV, or JSON. Up to 50 MB each.</p>
        <input ref={input} type="file" multiple className="hidden" onChange={(e) => e.target.files && void upload(e.target.files)} />
        <Button size="sm" onClick={() => input.current?.click()} loading={uploading}>
          Choose files
        </Button>
      </div>
      <ErrorNote error={error} />

      <div className="mt-8">
        <p className="eyebrow mb-2">Documents</p>
        {kb.documents.length === 0 ? (
          <p className="text-[13px] text-fg-3">Nothing uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-line rounded-2xl border border-line">
            {kb.documents.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-4 py-3 text-[13px]">
                <FileText className="size-4 shrink-0 text-fg-3" />
                <span className="min-w-0 flex-1 truncate">{d.filename}</span>
                <span className="hidden font-mono text-[11px] text-fg-3 sm:inline">{(d.size / 1024).toFixed(0)} KB</span>
                {d.status === 'ready' ? (
                  <Badge tone="success">{d.chunk_count} chunks</Badge>
                ) : d.status === 'error' ? (
                  <Badge tone="danger">failed</Badge>
                ) : (
                  <span className="shimmer font-mono text-[11px]">{d.status}</span>
                )}
                <IconButton
                  label={`Delete ${d.filename}`}
                  onClick={async () => {
                    await del(`/api/knowledge/${kb.id}/documents/${d.id}`)
                    invalidate('knowledge')
                  }}
                >
                  <Trash2 className="size-3.5" />
                </IconButton>
                {d.error && <span className="sr-only">{d.error}</span>}
              </li>
            ))}
          </ul>
        )}
        {kb.documents.filter((d) => d.error).map((d) => (
          <p key={d.id} className="mt-2 text-xs text-danger">
            {d.filename}: {d.error}
          </p>
        ))}
        {kb.documents.some((d) => d.status === 'indexing') && (
          <p className="mt-2 text-xs text-fg-3">
            {kb.mode === 'local' ? 'The first upload downloads the local embedding model, which can take a minute.' : 'xAI is chunking and embedding the file. It is searchable once marked ready.'}
          </p>
        )}
      </div>

      <div className="mt-10">
        <p className="eyebrow mb-2">Try a search</p>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            void search()
          }}
        >
          <Input placeholder="Ask what a caller would ask" value={query} onChange={(e) => setQuery(e.target.value)} />
          <Button type="submit" icon={<Search className="size-3.5" />} loading={searching} disabled={!query.trim()}>
            Search
          </Button>
        </form>
        {results && (
          <ol className="mt-4 flex flex-col gap-2">
            {results.length === 0 && <p className="text-[13px] text-fg-3">No passages matched.</p>}
            {results.map((r, i) => (
              <li key={i} className="rounded-2xl border border-line bg-l1 p-4">
                <p className="font-mono text-[11px] text-fg-3">
                  {r.source}
                  {r.page ? ` · page ${r.page}` : ''}
                  {r.score != null ? ` · score ${r.score}` : ''}
                </p>
                <p className="mt-2 line-clamp-6 whitespace-pre-wrap text-[13px] leading-relaxed text-fg-2">{r.text}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

export function KnowledgePage() {
  const { kbId } = useParams()
  const { data: kbs, error } = useKnowledge()
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  useEffect(() => {
    if (!kbId && kbs?.length) navigate(`/knowledge/${kbs[0].id}`, { replace: true })
  }, [kbId, kbs, navigate])
  const kb = kbs?.find((k) => k.id === kbId)
  return (
    <div className="flex h-full">
      <aside className="scroll-thin hidden w-[var(--rail)] shrink-0 overflow-y-auto border-r border-line px-3 py-5 md:block">
        <div className="mb-2 flex items-center justify-between px-2">
          <p className="eyebrow">Knowledge bases</p>
          <IconButton label="New knowledge base" onClick={() => setCreating(true)}>
            <Plus className="size-4" />
          </IconButton>
        </div>
        <nav className="flex flex-col gap-0.5">
          {kbs?.map((k) => (
            <NavLink key={k.id} to={`/knowledge/${k.id}`} className={({ isActive }) => cx('flex items-center justify-between rounded-lg px-2 py-1.5 text-[14px]', isActive ? 'bg-l2 text-fg' : 'text-fg-2 hover:text-fg')}>
              <span className="truncate">{k.name}</span>
              <span className="font-mono text-[11px] text-fg-4">{k.documents.length}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="scroll-thin min-w-0 flex-1 overflow-y-auto">
        <ErrorNote error={error} />
        {kb ? (
          <KbDetail kb={kb} />
        ) : (
          <div className="flex h-full items-center justify-center p-8">
            <Empty title="No knowledge bases" action={<Button variant="primary" onClick={() => setCreating(true)}>New knowledge base</Button>}>
              Give agents documents to answer from: manuals, policies, FAQs.
            </Empty>
          </div>
        )}
      </div>
      <NewKb open={creating} onOpenChange={setCreating} />
    </div>
  )
}
