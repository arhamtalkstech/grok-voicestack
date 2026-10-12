import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, StrictMode, Suspense, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider, useRouteError } from 'react-router'
import { Shell } from './app/Shell'
import { queryClient } from './lib/queries'
import './styles/index.css'

const LandscapePage = lazy(() => import('./features/landscape/LandscapePage').then((m) => ({ default: m.LandscapePage })))
const AgentsPage = lazy(() => import('./features/agents/AgentsPage').then((m) => ({ default: m.AgentsPage })))
const ConversationsPage = lazy(() => import('./features/conversations/ConversationsPage').then((m) => ({ default: m.ConversationsPage })))
const KnowledgePage = lazy(() => import('./features/knowledge/KnowledgePage').then((m) => ({ default: m.KnowledgePage })))
const IntegrationsPage = lazy(() => import('./features/integrations/IntegrationsPage').then((m) => ({ default: m.IntegrationsPage })))
const TelephonyPage = lazy(() => import('./features/telephony/TelephonyPage').then((m) => ({ default: m.TelephonyPage })))
const SettingsPage = lazy(() => import('./features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))

const load = (node: ReactNode) => <Suspense fallback={<div className="p-8 text-[13px] text-fg-3">Loading…</div>}>{node}</Suspense>

function RouteError() {
  const error = useRouteError() as Error | undefined
  return (
    <div className="mx-auto max-w-xl p-10">
      <h1 className="display text-[28px]">Something broke on this page</h1>
      <p className="mt-2 text-[13px] text-fg-3">{error?.message ?? 'Unknown error'}. Reload to try again; your saved work is safe.</p>
      <button className="mt-5 h-9 rounded-pill bg-btn px-4 text-sm text-btn-fg" onClick={() => window.location.reload()}>
        Reload
      </button>
    </div>
  )
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: load(<LandscapePage />) },
      { path: 'agents', element: load(<AgentsPage />) },
      { path: 'agents/:agentId', element: load(<AgentsPage />) },
      { path: 'agents/:agentId/:tab', element: load(<AgentsPage />) },
      { path: 'conversations', element: load(<ConversationsPage />) },
      { path: 'conversations/:conversationId', element: load(<ConversationsPage />) },
      { path: 'knowledge', element: load(<KnowledgePage />) },
      { path: 'knowledge/:kbId', element: load(<KnowledgePage />) },
      { path: 'integrations', element: load(<IntegrationsPage />) },
      { path: 'integrations/:section', element: load(<IntegrationsPage />) },
      { path: 'telephony', element: load(<TelephonyPage />) },
      { path: 'settings', element: load(<SettingsPage />) },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
