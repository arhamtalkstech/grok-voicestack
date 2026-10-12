import { create } from 'zustand'

type Theme = 'dark' | 'light'

interface AppState {
  /** Session-only xAI key: held in memory, sent per request, never persisted. */
  sessionKey: string | null
  setSessionKey: (key: string | null) => void
  adminToken: string | null
  setAdminToken: (token: string | null) => void
  theme: Theme
  setTheme: (theme: Theme) => void
  dock: { open: boolean; agentId?: string; resumeId?: string; expanded: boolean }
  openDock: (opts?: { agentId?: string; resumeId?: string }) => void
  closeDock: () => void
  toggleDockExpanded: () => void
  palette: boolean
  setPalette: (open: boolean) => void
}

const storedTheme = (localStorage.getItem('vs-theme') as Theme | null) ?? 'dark'
document.documentElement.dataset.theme = storedTheme

export const useApp = create<AppState>((set) => ({
  sessionKey: null,
  setSessionKey: (sessionKey) => set({ sessionKey }),
  adminToken: localStorage.getItem('vs-admin-token'),
  setAdminToken: (adminToken) => {
    if (adminToken) localStorage.setItem('vs-admin-token', adminToken)
    else localStorage.removeItem('vs-admin-token')
    set({ adminToken })
  },
  theme: storedTheme,
  setTheme: (theme) => {
    localStorage.setItem('vs-theme', theme)
    document.documentElement.dataset.theme = theme
    set({ theme })
  },
  dock: { open: false, expanded: false },
  openDock: (opts) => set((s) => ({ dock: { ...s.dock, open: true, agentId: opts?.agentId ?? s.dock.agentId, resumeId: opts?.resumeId } })),
  closeDock: () => set((s) => ({ dock: { ...s.dock, open: false, resumeId: undefined } })),
  toggleDockExpanded: () => set((s) => ({ dock: { ...s.dock, expanded: !s.dock.expanded } })),
  palette: false,
  setPalette: (palette) => set({ palette }),
}))
