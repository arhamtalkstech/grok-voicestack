export const SAMPLE_RATE = 24000

export function base64ToInt16(b64: string): Int16Array {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2))
}

export function bytesToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(bin)
}

function rms(analyser: AnalyserNode, scratch: Float32Array<ArrayBuffer>): number {
  analyser.getFloatTimeDomainData(scratch)
  let sum = 0
  for (let i = 0; i < scratch.length; i++) sum += scratch[i] * scratch[i]
  return Math.sqrt(sum / scratch.length)
}

/** Mic capture and assistant playback at 24 kHz PCM16, with level meters. */
export class AudioEngine {
  ctx: AudioContext | null = null
  private stream: MediaStream | null = null
  private capture: AudioWorkletNode | null = null
  private playback: AudioWorkletNode | null = null
  private outAnalyser: AnalyserNode | null = null
  private micAnalyser: AnalyserNode | null = null
  private scratch = new Float32Array(1024)
  playing = false
  played = 0
  queued = 0
  muted = false
  onPcm: (pcm: ArrayBuffer) => void = () => {}
  onPlayback: (playing: boolean) => void = () => {}

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE, latencyHint: 'interactive' })
    this.ctx = ctx
    await ctx.audioWorklet.addModule('/worklets/capture.js')
    await ctx.audioWorklet.addModule('/worklets/playback.js')

    const source = ctx.createMediaStreamSource(this.stream)
    this.micAnalyser = ctx.createAnalyser()
    this.micAnalyser.fftSize = 1024
    source.connect(this.micAnalyser)
    this.capture = new AudioWorkletNode(ctx, 'vs-capture')
    source.connect(this.capture)
    const sink = ctx.createGain()
    sink.gain.value = 0
    this.capture.connect(sink).connect(ctx.destination)
    this.capture.port.onmessage = (e) => {
      if (!this.muted) this.onPcm(e.data.pcm as ArrayBuffer)
    }

    this.playback = new AudioWorkletNode(ctx, 'vs-playback', { outputChannelCount: [1] })
    this.outAnalyser = ctx.createAnalyser()
    this.outAnalyser.fftSize = 1024
    this.playback.connect(this.outAnalyser).connect(ctx.destination)
    this.playback.port.onmessage = (e) => {
      const d = e.data
      this.played = d.played
      if (d.type === 'state') {
        this.playing = d.playing
        this.onPlayback(d.playing)
      }
    }
    if (ctx.state === 'suspended') await ctx.resume()
  }

  push(pcm: Int16Array): void {
    if (!this.playback) return
    this.queued += pcm.length
    if (!this.playing) {
      this.playing = true
      this.onPlayback(true)
    }
    const copy = pcm.slice()
    this.playback.port.postMessage({ type: 'push', pcm: copy.buffer }, [copy.buffer])
  }

  clear(): void {
    this.playback?.port.postMessage({ type: 'clear' })
    this.queued = this.played
  }

  outLevel = (): number => (this.outAnalyser ? rms(this.outAnalyser, this.scratch) : 0)
  micLevel = (): number => (this.micAnalyser && !this.muted ? rms(this.micAnalyser, this.scratch) : 0)

  async stop(): Promise<void> {
    this.stream?.getTracks().forEach((t) => t.stop())
    this.capture?.disconnect()
    this.playback?.disconnect()
    if (this.ctx && this.ctx.state !== 'closed') await this.ctx.close()
    this.ctx = null
  }
}
