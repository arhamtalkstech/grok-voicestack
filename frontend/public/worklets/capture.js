// Mic capture: Float32 at the context rate (24 kHz) -> PCM16 chunks of 100 ms.
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.size = 2400
    this.buf = new Int16Array(this.size)
    this.n = 0
    this.sum = 0
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch) return true
    for (let i = 0; i < ch.length; i++) {
      const s = Math.max(-1, Math.min(1, ch[i]))
      this.sum += s * s
      this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff
      if (this.n === this.size) {
        const level = Math.sqrt(this.sum / this.size)
        this.port.postMessage({ pcm: this.buf.buffer, level }, [this.buf.buffer])
        this.buf = new Int16Array(this.size)
        this.n = 0
        this.sum = 0
      }
    }
    return true
  }
}

registerProcessor('vs-capture', CaptureProcessor)
