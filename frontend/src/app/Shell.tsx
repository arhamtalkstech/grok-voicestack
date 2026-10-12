import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { Moon, Search, Settings, Sun } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { useLive } from '../audio/live'
import { Button, Dialog, IconButton, Input, Kbd, cx } from '../components/ui'
import { LiveDock } from '../features/live/LiveDock'
import { useAgents } from '../lib/queries'
import { useApp } from '../lib/store'

const NAV = [
  { to: '/', label: 'Landscape', end: true },
  { to: '/agents', label: 'Agents' },
  { to: '/conversations', label: 'Conversations' },
  { to: '/knowledge', label: 'Knowledge' },
  { to: '/integrations', label: 'Integrations' },
  { to: '/telephony', label: 'Telephony' },
]

function Wordmark() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5" aria-label="Voice Stack home">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M5 16h3M11 10v12M16 5v22M21 9v14M26 16h1" />
        </g>
      </svg>
      <span className="display whitespace-nowrap text-[17px] font-[450] tracking-[-0.02em]">Voice Stack</span>
    </NavLink>
  )
}

function CallButton() {
  const status = useLive((s) => s.status)
  const openDock = useApp((s) => s.openDock)
  const dockOpen = useApp((s) => s.dock.open)
  const live = status === 'live' || status === 'connecting'
  return (
    <Button variant={live ? 'secondary' : 'primary'} size="sm" onClick={() => openDock()} aria-pressed={dockOpen} className="min-w-[104px]">
      {live ? (
        <>
          <span className="live-dot" /> In call
        </>
      ) : (
        'Start call'
      )}
    </Button>
  )
}

function Palette() {
  const open = useApp((s) => s.palette)
  const setOpen = useApp((s) => s.setPalette)
  const openDock = useApp((s) => s.openDock)
  const navigate = useNavigate()
  const { data: agents } = useAgents()
  const [q, setQ] = useState('')
  const items = [
    ...NAV.map((n) => ({ label: n.label, hint: 'Page', run: () => navigate(n.to) })),
    { label: 'Settings', hint: 'Page', run: () => navigate('/settings') },
    ...(agents ?? []).map((a) => ({ label: a.name, hint: 'Agent', run: () => navigate(`/agents/${a.id}`) })),
    ...(agents ?? []).map((a) => ({ label: `Talk to ${a.name}`, hint: 'Call', run: () => openDock({ agentId: a.id }) })),
  ].filter((i) => i.label.toLowerCase().includes(q.toLowerCase()))
  const [active, setActive] = useState(0)
  useEffect(() => {
    setActive(0)
  }, [q])
  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); setQ('') }} title="Go to">
      <Input
        autoFocus
        placeholder="Pages, agents, actions"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
          if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          if (e.key === 'Enter' && items[active]) { items[active].run(); setOpen(false); setQ('') }
        }}
      />
      <ul className="mt-3 flex max-h-80 flex-col overflow-y-auto" role="listbox">
        {items.map((item, i) => (
          <li key={`${item.hint}-${item.label}`}>
            <button
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={() => { item.run(); setOpen(false); setQ('') }}
              className={cx('flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm', i === active ? 'bg-l3 text-fg' : 'text-fg-2')}
            >
              {item.label}
              <span className="eyebrow">{item.hint}</span>
            </button>
          </li>
        ))}
        {!items.length && <li className="px-3 py-6 text-center text-sm text-fg-3">Nothing matches “{q}”.</li>}
      </ul>
    </Dialog>
  )
}

function SignIn() {
  const [open, setOpen] = useState(false)
  const [token, setToken] = useState('')
  const setAdminToken = useApp((s) => s.setAdminToken)
  useEffect(() => {
    const onUnauthorized = () => setOpen(true)
    window.addEventListener('vs:unauthorized', onUnauthorized)
    return () => window.removeEventListener('vs:unauthorized', onUnauthorized)
  }, [])
  return (
    <Dialog open={open} onOpenChange={setOpen} title="Sign in" description="This instance requires the admin token (AUTH_MODE=token).">
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          setAdminToken(token.trim())
          setOpen(false)
          window.location.reload()
        }}
      >
        <Input type="password" autoFocus placeholder="Admin token" value={token} onChange={(e) => setToken(e.target.value)} />
        <Button variant="primary" type="submit" disabled={!token.trim()}>
          Sign in
        </Button>
      </form>
    </Dialog>
  )
}

export function Shell() {
  const dock = useApp((s) => s.dock)
  const theme = useApp((s) => s.theme)
  const setTheme = useApp((s) => s.setTheme)
  const setPalette = useApp((s) => s.setPalette)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPalette])

  return (
    <TooltipPrimitive.Provider>
      <div className="flex h-full flex-col">
        <header className="sticky top-0 z-30 grid h-[var(--topbar)] shrink-0 grid-cols-[1fr_auto_1fr] items-center border-b border-line bg-bg/85 px-4 backdrop-blur-md md:px-6">
          <Wordmark />
          <nav aria-label="Primary" className="hidden items-center gap-1 lg:flex">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  cx('rounded-pill px-3 py-1.5 text-[14px] transition-colors', isActive ? 'bg-l2 text-fg' : 'text-fg-2 hover:text-fg')
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center justify-end gap-1.5">
            <button
              onClick={() => setPalette(true)}
              className="hidden h-8 items-center gap-2 rounded-pill border border-line-2 px-3 text-[13px] text-fg-3 transition-colors hover:border-line-strong hover:text-fg-2 md:flex"
            >
              <Search className="size-3.5" /> Search <Kbd>⌘K</Kbd>
            </button>
            <IconButton label={theme === 'dark' ? 'Light theme' : 'Dark theme'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </IconButton>
            <NavLink to="/settings" aria-label="Settings" className={({ isActive }) => cx('inline-flex size-8 items-center justify-center rounded-pill hover:bg-l2', isActive ? 'text-fg' : 'text-fg-2')}>
              <Settings className="size-4" />
            </NavLink>
            <CallButton />
          </div>
        </header>
        <nav aria-label="Primary mobile" className="flex gap-1 overflow-x-auto border-b border-line px-3 py-2 lg:hidden">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cx('shrink-0 rounded-pill px-3 py-1 text-[13px]', isActive ? 'bg-l2 text-fg' : 'text-fg-2')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 overflow-hidden">
            <Outlet />
          </main>
          <AnimatePresence initial={false}>
            {dock.open && (
              <motion.aside
                key="dock"
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 'auto', opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
                className={cx(
                  'fixed inset-0 z-40 overflow-hidden border-l border-line bg-bg md:static md:inset-auto md:z-auto',
                  dock.expanded ? 'md:w-[min(56rem,60vw)]' : 'md:w-[var(--dock)]',
                )}
                aria-label="Live preview"
              >
                <LiveDock />
              </motion.aside>
            )}
          </AnimatePresence>
        </div>
      </div>
      <Palette />
      <SignIn />
    </TooltipPrimitive.Provider>
  )
}
