export type Severity = 'error' | 'warning' | 'info'

export interface Finding {
  rule: string
  severity: Severity
  message: string
  section?: string | null
  quote?: string | null
  guide?: string | null
}

export interface Lint {
  score: number
  findings: Finding[]
}

export type SectionKey = 'role' | 'objective' | 'flow' | 'guardrails' | 'style' | 'critical'

export interface Agent {
  id: string
  slug: string
  name: string
  description: string
  prompt_mode: 'sections' | 'raw'
  prompt_sections: Partial<Record<SectionKey, string>>
  raw_prompt: string
  key_facts: string
  greeting: string
  greeting_mode: 'model' | 'verbatim' | 'none'
  greeting_interruptible: boolean
  voice_id: string
  speed: number
  reasoning_effort: 'high' | 'none'
  language_hint: string | null
  keyterms: string[]
  replace_map: Record<string, string>
  idle_timeout_ms: number | null
  builtin_tools: {
    web_search?: { enabled?: boolean; allowed_domains?: string[]; excluded_domains?: string[]; location?: Record<string, string> }
    x_search?: { enabled?: boolean; allowed_x_handles?: string[]; excluded_x_handles?: string[]; from_date?: string; to_date?: string }
  }
  tool_ids: string[]
  mcp_ids: string[]
  knowledge_ids: string[]
  transfer_target_ids: string[]
  allow_end_call: boolean
  position: { x?: number; y?: number }
  is_entry: boolean
  published_version: number | null
  draft_changed: boolean
  lint: Lint
  created_at: string
  updated_at: string
}

export interface ContextField {
  name: string
  type: 'string' | 'number' | 'integer' | 'boolean'
  description: string
  required: boolean
}

export interface Edge {
  id: string
  source_id: string
  target_id: string
  description: string
  context_fields: ContextField[]
  handoff_greeting: string
  voice_policy: 'switch' | 'keep'
}

export interface LandscapeAgent {
  id: string
  slug: string
  name: string
  description: string
  voice_id: string
  speed: number
  is_entry: boolean
  position: { x?: number; y?: number }
  published_version: number | null
  tools: string[]
  mcps: string[]
  knowledge: string[]
  builtin: string[]
  transfers: number
}

export interface Landscape {
  agents: LandscapeAgent[]
  edges: Edge[]
  entry_points: { kind: 'phone'; id: string; label: string; name: string; agent_id: string | null }[]
}

export interface Tool {
  id: string
  name: string
  kind: 'http' | 'plugin'
  description: string
  parameters: Record<string, unknown>
  config: Record<string, unknown>
  preamble: string
  requires_confirmation: boolean
  enabled: boolean
}

export interface McpServer {
  id: string
  label: string
  description: string
  mode: 'xai' | 'managed'
  transport: 'streamable_http' | 'sse' | 'stdio'
  url: string
  command: string
  args: string[]
  allowed_tools: string[]
  authorization_secret: string | null
  header_secrets: Record<string, string>
  enabled: boolean
}

export interface KnowledgeDoc {
  id: string
  filename: string
  size: number
  status: 'pending' | 'indexing' | 'ready' | 'error'
  chunk_count: number
  error: string
  created_at: string
}

export interface KnowledgeBase {
  id: string
  name: string
  slug: string
  description: string
  mode: 'local' | 'collections'
  collection_id: string | null
  top_k: number
  documents: KnowledgeDoc[]
}

export interface TransferTarget {
  id: string
  name: string
  uri: string
  description: string
}

export interface Voice {
  voice_id: string
  name?: string
  description?: string
  gender?: string
  tone?: string
  language?: string
  accent?: string
  [k: string]: unknown
}

export interface Turn {
  id: string
  seq: number
  kind: 'user' | 'assistant' | 'tool' | 'handoff' | 'system' | 'dtmf'
  agent_id: string | null
  text: string
  data: Record<string, unknown>
  created_at: string
}

export interface ConversationSummary {
  id: string
  channel: 'web' | 'sip'
  status: 'live' | 'ended' | 'error'
  entry_agent_id: string | null
  last_agent_id: string | null
  agents_visited: string[]
  from_number: string | null
  to_number: string | null
  summary: string
  disposition: string
  started_at: string
  ended_at: string | null
  turn_count: number
  contact: string | null
  meta: Record<string, unknown>
}

export interface ConversationDetail extends ConversationSummary {
  turns: Turn[]
  agents: Record<string, { id: string; slug: string; name: string }>
  extracted: Record<string, string>
  resumed_from_id: string | null
  resume_chain: string[]
}

export interface PhoneNumber {
  id: string
  e164: string
  name: string
  xai_phone_number_id: string | null
  sip_host: string
  sip_uri: string
  sip_auth: { username?: string | null; allowed_addresses?: string[] }
  entry_agent_id: string | null
  use_published: boolean
  greeting_disclosure: string
  has_signing_secret: boolean
  created_at: string
}

export interface CredentialStatus {
  source: 'workspace' | 'env' | null
  last4: string | null
  validated_at: string | null
}
