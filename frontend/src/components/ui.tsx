import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as SliderPrimitive from '@radix-ui/react-slider'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import clsx from 'clsx'
import { Loader2, X } from 'lucide-react'
import {
  forwardRef,
  useEffect,
  useLayoutEffect,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

export const cx = clsx

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md'; loading?: boolean; icon?: ReactNode }
>(function Button({ variant = 'secondary', size = 'md', loading, icon, className, children, disabled, ...props }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        'inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-pill font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45',
        size === 'sm' ? 'h-8 px-3 text-[13px]' : 'h-10 px-4 text-sm',
        variant === 'primary' && 'bg-btn text-btn-fg hover:opacity-90',
        variant === 'secondary' && 'bg-btn-2 text-fg hover:bg-btn-2-hover',
        variant === 'ghost' && 'text-fg-2 hover:bg-l2 hover:text-fg',
        variant === 'outline' && 'border border-line-2 text-fg hover:border-line-strong',
        variant === 'danger' && 'bg-btn-2 text-danger hover:bg-btn-2-hover',
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
})

export function IconButton({ label, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <Tip label={label}>
      <button
        aria-label={label}
        className={cx('inline-flex size-8 items-center justify-center rounded-pill text-fg-2 transition-colors hover:bg-l2 hover:text-fg', className)}
        {...props}
      >
        {children}
      </button>
    </Tip>
  )
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { mono?: boolean }>(function Input(
  { className, mono, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cx(
        'h-9 w-full rounded-lg border border-line-2 bg-inset px-3 text-sm text-fg placeholder:text-fg-4 transition-colors focus:border-line-strong focus:outline-none',
        mono && 'font-mono text-[13px]',
        className,
      )}
      {...props}
    />
  )
})

export function Textarea({
  className,
  mono,
  autoGrow = true,
  minRows = 3,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { mono?: boolean; autoGrow?: boolean; minRows?: number }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || !autoGrow) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [props.value, autoGrow])
  return (
    <textarea
      ref={ref}
      rows={minRows}
      className={cx(
        'w-full resize-none rounded-lg border border-line-2 bg-inset px-3 py-2.5 text-sm leading-relaxed text-fg placeholder:text-fg-4 transition-colors focus:border-line-strong focus:outline-none',
        mono && 'font-mono text-[12.5px]',
        className,
      )}
      {...props}
    />
  )
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cx(
        'h-9 w-full appearance-none rounded-lg border border-line-2 bg-inset bg-[length:12px] bg-[right_10px_center] bg-no-repeat px-3 pr-8 text-sm text-fg focus:border-line-strong focus:outline-none',
        "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23787878' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export function Field({
  label,
  hint,
  error,
  children,
  className,
  action,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
  className?: string
  action?: ReactNode
}) {
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label className="text-[13px] font-medium text-fg">{label}</label>
        {action}
      </div>
      {children}
      {hint && !error && <p className="text-xs leading-relaxed text-fg-3">{hint}</p>}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <SwitchPrimitive.Root
      checked={checked}
      onCheckedChange={onChange}
      aria-label={label}
      className="relative h-5 w-9 shrink-0 rounded-pill border border-line-2 bg-l3 transition-colors data-[state=checked]:border-transparent data-[state=checked]:bg-fg"
    >
      <SwitchPrimitive.Thumb className="block size-4 translate-x-0.5 rounded-pill bg-fg-2 transition-transform data-[state=checked]:translate-x-[17px] data-[state=checked]:bg-bg" />
    </SwitchPrimitive.Root>
  )
}

export function Slider({
  value,
  min,
  max,
  step,
  onChange,
  onCommit,
  label,
}: {
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  onCommit?: (v: number) => void
  label: string
}) {
  return (
    <SliderPrimitive.Root
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={([v]) => onChange(v)}
      onValueCommit={([v]) => onCommit?.(v)}
      className="relative flex h-5 w-full touch-none select-none items-center"
    >
      <SliderPrimitive.Track className="relative h-1 grow rounded-pill bg-l4">
        <SliderPrimitive.Range className="absolute h-full rounded-pill bg-fg" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb aria-label={label} className="block size-4 rounded-pill border-2 border-bg bg-fg shadow focus-visible:outline-2 focus-visible:outline-fg" />
    </SliderPrimitive.Root>
  )
}

export function Badge({ children, tone = 'neutral', className }: { children: ReactNode; tone?: 'neutral' | 'live' | 'success' | 'danger' | 'warn' | 'info'; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex h-5 items-center gap-1 rounded-pill border px-2 font-mono text-[11px] leading-none',
        tone === 'neutral' && 'border-line-2 text-fg-2',
        tone === 'live' && 'border-live/40 bg-live-soft text-live',
        tone === 'success' && 'border-success/30 text-success',
        tone === 'danger' && 'border-danger/30 text-danger',
        tone === 'warn' && 'border-warn/30 text-warn',
        tone === 'info' && 'border-info/30 text-info',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Card({ children, className, ...props }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx('rounded-2xl border border-line bg-l1', className)} {...props}>
      {children}
    </div>
  )
}

export function Tip({ label, children, side = 'bottom' }: { label: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right' }) {
  return (
    <TooltipPrimitive.Root delayDuration={300}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 rounded-lg border border-line-2 bg-l3 px-2 py-1 text-xs text-fg shadow-[var(--shadow-pop)]"
        >
          {label}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  wide?: boolean
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px] data-[state=open]:animate-[fadein_150ms_ease-out]" />
        <DialogPrimitive.Content
          className={cx(
            'fixed left-1/2 top-[8vh] z-50 flex max-h-[84vh] w-[calc(100vw-2rem)] -translate-x-1/2 flex-col overflow-hidden rounded-3xl border border-line-2 bg-l1 shadow-[var(--shadow-pop)] focus:outline-none',
            wide ? 'max-w-5xl' : 'max-w-lg',
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
            <div>
              <DialogPrimitive.Title className="text-lg font-medium tracking-tight">{title}</DialogPrimitive.Title>
              {description && <DialogPrimitive.Description className="mt-1 text-[13px] text-fg-3">{description}</DialogPrimitive.Description>}
            </div>
            <DialogPrimitive.Close asChild>
              <button aria-label="Close" className="rounded-pill p-1.5 text-fg-3 hover:bg-l3 hover:text-fg">
                <X className="size-4" />
              </button>
            </DialogPrimitive.Close>
          </div>
          <div className="scroll-thin overflow-y-auto px-6 py-5">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function Empty({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line-2 px-6 py-12 text-center">
      {icon && <div className="text-fg-3">{icon}</div>}
      <p className="text-[15px] font-medium">{title}</p>
      {children && <p className="max-w-sm text-[13px] leading-relaxed text-fg-3">{children}</p>}
      {action}
    </div>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : String(error)
  return <p className="rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-[13px] text-danger">{message}</p>
}

export function SectionTitle({ eyebrow, title, children, action }: { eyebrow?: string; title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h2 className="text-[17px] font-medium tracking-tight">{title}</h2>
        {children && <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-fg-3">{children}</p>}
      </div>
      {action}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded-md border border-line-2 bg-l2 px-1.5 py-0.5 font-mono text-[10px] text-fg-3">{children}</kbd>
}

export function useDebouncedEffect(fn: () => void, deps: unknown[], ms = 600) {
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    const t = setTimeout(fn, ms)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

export function ChipInput({ values, onChange, placeholder, mono }: { values: string[]; onChange: (v: string[]) => void; placeholder?: string; mono?: boolean }) {
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-line-2 bg-inset px-2 py-1.5 focus-within:border-line-strong">
      {values.map((v) => (
        <span key={v} className={cx('inline-flex items-center gap-1 rounded-pill bg-l3 py-0.5 pl-2.5 pr-1 text-xs', mono && 'font-mono')}>
          {v}
          <button aria-label={`Remove ${v}`} className="rounded-pill p-0.5 text-fg-3 hover:text-fg" onClick={() => onChange(values.filter((x) => x !== v))}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        className="min-w-24 flex-1 bg-transparent px-1 text-sm text-fg placeholder:text-fg-4 focus:outline-none"
        placeholder={values.length ? '' : placeholder}
        onKeyDown={(e) => {
          const el = e.currentTarget
          if ((e.key === 'Enter' || e.key === ',') && el.value.trim()) {
            e.preventDefault()
            const next = el.value.trim().replace(/,$/, '')
            if (!values.includes(next)) onChange([...values, next])
            el.value = ''
          } else if (e.key === 'Backspace' && !el.value && values.length) {
            onChange(values.slice(0, -1))
          }
        }}
      />
    </div>
  )
}
