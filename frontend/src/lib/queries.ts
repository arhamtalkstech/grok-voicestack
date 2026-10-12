import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { del, get, patch, post, put } from './api'
import type {
  Agent,
  ConversationDetail,
  ConversationSummary,
  CredentialStatus,
  KnowledgeBase,
  Landscape,
  McpServer,
  PhoneNumber,
  Tool,
  TransferTarget,
  Voice,
} from './types'

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } },
})

export const useAgents = () => useQuery({ queryKey: ['agents'], queryFn: () => get<Agent[]>('/api/agents') })
export const useLandscape = () => useQuery({ queryKey: ['landscape'], queryFn: () => get<Landscape>('/api/landscape') })
export const useTools = () => useQuery({ queryKey: ['tools'], queryFn: () => get<Tool[]>('/api/tools') })
export const usePlugins = () =>
  useQuery({ queryKey: ['plugins'], queryFn: () => get<{ name: string; description: string; parameters: Record<string, unknown> }[]>('/api/plugins') })
export const useMcp = () => useQuery({ queryKey: ['mcp'], queryFn: () => get<McpServer[]>('/api/mcp') })
export const useKnowledge = () =>
  useQuery({
    queryKey: ['knowledge'],
    queryFn: () => get<KnowledgeBase[]>('/api/knowledge'),
    refetchInterval: (q) => (q.state.data?.some((kb) => kb.documents.some((d) => d.status === 'pending' || d.status === 'indexing')) ? 2000 : false),
  })
export const useTargets = () => useQuery({ queryKey: ['targets'], queryFn: () => get<TransferTarget[]>('/api/transfer-targets') })
export const useSecrets = () => useQuery({ queryKey: ['secrets'], queryFn: () => get<{ name: string; last4: string; updated_at: string }[]>('/api/secrets') })
export const useNumbers = () => useQuery({ queryKey: ['numbers'], queryFn: () => get<PhoneNumber[]>('/api/telephony/numbers') })
export const useTelephonyInfo = () =>
  useQuery({
    queryKey: ['telephony-info'],
    queryFn: () =>
      get<{
        public_base_url: string | null
        webhook_url: string | null
        server_key_configured: boolean
        role: string
        sip_host: string
        recent_webhooks: { id: string; event_type: string; status: string; received_at: string }[]
      }>('/api/telephony/info'),
  })
export const useCredentials = () =>
  useQuery({
    queryKey: ['credentials'],
    queryFn: () => get<{ xai_api_key: CredentialStatus }>('/api/settings/credentials'),
  })
export const useAppSettings = () =>
  useQuery({
    queryKey: ['app-settings'],
    queryFn: () =>
      get<{
        version: string
        auth_mode: string
        role: string
        voice_model: string
        text_model: string
        optimizer_model: string
        optimizer_reasoning_effort: string
        handoff_voice_mode: string
        public_base_url: string | null
        database: string
        embeddings_provider: string
        embeddings_model: string
      }>('/api/settings/app'),
    staleTime: 60_000,
  })

export function useVoices(enabled = true) {
  return useQuery({
    queryKey: ['voices'],
    queryFn: () => get<{ builtin: Voice[]; custom: Voice[]; custom_error: string | null; custom_notice: string }>('/api/voices'),
    enabled,
    staleTime: 300_000,
    retry: false,
  })
}

export const useConversations = (params: Record<string, string>) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  return useQuery({
    queryKey: ['conversations', qs],
    queryFn: () => get<{ total: number; items: ConversationSummary[] }>(`/api/conversations?${qs}`),
    refetchInterval: 5000,
  })
}

export const useConversation = (id?: string) =>
  useQuery({
    queryKey: ['conversation', id],
    queryFn: () => get<ConversationDetail>(`/api/conversations/${id}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const c = q.state.data
      if (!c) return false
      if (c.status === 'live') return 2000
      // The post-call summary lands a few seconds after the call ends.
      const recentlyEnded = c.ended_at && Date.now() - new Date(c.ended_at).getTime() < 120_000
      return c.status === 'ended' && !c.summary && recentlyEnded ? 2000 : false
    },
  })

export const useConversationState = (id?: string) =>
  useQuery({
    queryKey: ['conversation-state', id],
    queryFn: () =>
      get<{
        active_agent: string | null
        context: Record<string, unknown>
        handoffs: Record<string, unknown>[]
        call_summary: Record<string, unknown> | null
        message_count: number
        checkpoint_id: string | null
      }>(`/api/conversations/${id}/state`),
    enabled: !!id,
  })

export function useSaveAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<Agent> & { id: string }) => patch<Agent>(`/api/agents/${id}`, body),
    onSuccess: (agent) => {
      qc.setQueryData<Agent[]>(['agents'], (list) => list?.map((a) => (a.id === agent.id ? agent : a)))
      qc.invalidateQueries({ queryKey: ['landscape'] })
    },
  })
}

export function useCreateAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Agent>) => post<Agent>('/api/agents', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agents'] })
      qc.invalidateQueries({ queryKey: ['landscape'] })
    },
  })
}

export function useInvalidate() {
  const qc = useQueryClient()
  return (...keys: string[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
}

export { del, get, patch, post, put }
