/**
 * Voiceprint geometry: a deterministic radial line glyph per agent.
 *
 * Shape = concentric closed curves r(θ) = R·(1 + Σ aₖ·sin(fₖθ + φₖ + ring·twist)).
 * Frequencies are integers so every curve closes. Morphing blends two term sets by weight, which
 * keeps the curve continuous for every t in [0, 1].
 */

export interface Seed {
  voice: string
  name: string
  speed?: number
}

export interface Term {
  f: number
  a: number
  p: number
}

export interface Print {
  terms: Term[]
  rings: number
  twist: number
  spacing: number
}

function hash(text: string): number {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function rng(seed: number) {
  let s = seed
  return () => {
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function makePrint(seed: Seed): Print {
  const rand = rng(hash(`${seed.voice.toLowerCase()}|${seed.name}`))
  const speed = seed.speed ?? 1
  const count = 3 + Math.floor(rand() * 3)
  const used = new Set<number>()
  const terms: Term[] = []
  while (terms.length < count) {
    const f = 2 + Math.floor(rand() * 9)
    if (used.has(f)) continue
    used.add(f)
    terms.push({ f, a: 0.025 + rand() * 0.07, p: rand() * Math.PI * 2 })
  }
  return { terms, rings: 4 + Math.floor(rand() * 2), twist: 0.25 + rand() * 0.5, spacing: 0.15 + (speed - 0.7) * 0.06 }
}

export function radius(print: Print, theta: number, ring: number, gain = 1, phase = 0): number {
  let sum = 0
  for (const t of print.terms) sum += t.a * gain * Math.sin(t.f * theta + t.p + ring * print.twist + phase)
  return 1 + sum
}

export function blendedRadius(a: Print, b: Print, t: number, theta: number, ring: number, gain = 1, phase = 0): number {
  return (1 - t) * radius(a, theta, ring, gain, phase) + t * radius(b, theta, ring, gain, phase)
}

export function ringPath(print: Print, ring: number, size: number, steps = 96): string {
  const c = size / 2
  const base = (size / 2) * (1 - print.spacing * ring) * 0.86
  let d = ''
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * Math.PI * 2
    const r = base * radius(print, theta, ring)
    const x = c + r * Math.cos(theta)
    const y = c + r * Math.sin(theta)
    d += `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
  }
  return d + 'Z'
}
