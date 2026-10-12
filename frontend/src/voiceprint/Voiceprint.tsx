import { useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef } from 'react'
import { blendedRadius, makePrint, ringPath, type Print, type Seed } from './geometry'

/** Static glyph for lists, graph nodes, and transcript chips. */
export function Voiceprint({ seed, size = 40, live = false, className }: { seed: Seed; size?: number; live?: boolean; className?: string }) {
  const print = useMemo(() => makePrint(seed), [seed])
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={className} aria-hidden>
      {Array.from({ length: print.rings }, (_, ring) => (
        <path
          key={ring}
          d={ringPath(print, ring, size)}
          fill="none"
          stroke={live && ring === 0 ? 'var(--live)' : 'var(--fg)'}
          strokeOpacity={live && ring === 0 ? 1 : 0.85 - ring * 0.16}
          strokeWidth={size > 80 ? 1.25 : 1}
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  )
}

/**
 * Animated glyph for the live dock: amplitude follows real audio, and changing `seed` morphs the
 * previous agent's shape into the new one (the handoff moment).
 */
export function LiveVoiceprint({
  seed,
  size = 220,
  getLevel,
  speaking,
}: {
  seed: Seed
  size?: number
  getLevel: () => number
  speaking: boolean
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const reduce = useReducedMotion()
  const target = useMemo(() => makePrint(seed), [seed])
  const state = useRef<{ from: Print; to: Print; started: number; level: number }>({ from: target, to: target, started: 0, level: 0 })
  const speakingRef = useRef(speaking)
  speakingRef.current = speaking

  useEffect(() => {
    const s = state.current
    if (s.to !== target) {
      s.from = s.to
      s.to = target
      s.started = performance.now()
    }
  }, [target])

  useEffect(() => {
    const el = canvas.current
    if (!el) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    el.width = size * dpr
    el.height = size * dpr
    const ctx = el.getContext('2d')!
    let frame = 0
    const styles = getComputedStyle(document.documentElement)
    const draw = (now: number) => {
      const s = state.current
      const fg = styles.getPropertyValue('--fg').trim() || '#f9f9f9'
      const live = styles.getPropertyValue('--live').trim() || '#f26b1d'
      const t = reduce ? 1 : Math.min(1, (now - s.started) / 900)
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
      const raw = Math.min(1, getLevel() * 3.2)
      s.level += (raw - s.level) * (raw > s.level ? 0.35 : 0.08)
      const gain = 1 + s.level * 3.2
      const phase = reduce ? 0 : now / 2400
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, size, size)
      const c = size / 2
      const rings = Math.max(s.from.rings, s.to.rings)
      for (let ring = 0; ring < rings; ring++) {
        const spacing = (1 - ease) * s.from.spacing + ease * s.to.spacing
        const base = (size / 2) * (1 - spacing * ring) * 0.84
        ctx.beginPath()
        const steps = 160
        for (let i = 0; i <= steps; i++) {
          const theta = (i / steps) * Math.PI * 2
          const r = base * blendedRadius(s.from, s.to, ease, theta, ring, gain, phase * (ring % 2 ? -1 : 1))
          const x = c + r * Math.cos(theta)
          const y = c + r * Math.sin(theta)
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.closePath()
        const accent = speakingRef.current && ring === 0
        ctx.strokeStyle = accent ? live : fg
        ctx.globalAlpha = accent ? 0.95 : Math.max(0.12, 0.8 - ring * 0.15)
        ctx.lineWidth = accent ? 1.6 : 1.1
        ctx.stroke()
      }
      ctx.globalAlpha = 1
      frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [size, getLevel, reduce])

  return <canvas ref={canvas} style={{ width: size, height: size }} aria-hidden />
}
