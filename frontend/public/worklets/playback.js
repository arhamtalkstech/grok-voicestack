// Assistant playback: a queue of PCM16 chunks played at the context rate (24 kHz).
// Reports playing/idle transitions and the running count of samples played (for barge-in truncation).
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.queue = []
    this.offset = 0
    this.played = 0
    this.playing = false
    this.tick = 0
    this.port.onmessage = (e) => {
      const d = e.data
      if (d.type === 'push') this.queue.push(new Int16Array(d.pcm))
      else if (d.type === 'clear') {
        this.queue = []
        this.offset = 0
      }
    }
  }

  process(_inputs, outputs) {
    const out = outputs[0][0]
    let i = 0
    while (i < out.length && this.queue.length) {
      const cur = this.queue[0]
      const take = Math.min(out.length - i, cur.length - this.offset)
      for (let j = 0; j < take; j++) out[i + j] = cur[this.offset + j] / 32768
      i += take
      this.offset += take
      this.played += take
      if (this.offset >= cur.length) {
        this.queue.shift()
        this.offset = 0
      }
    }
    for (; i < out.length; i++) out[i] = 0
    const playing = this.queue.length > 0
    if (playing !== this.playing) {
      this.playing = playing
      this.port.postMessage({ type: 'state', playing, played: this.played })
    }
    if (++this.tick % 16 === 0) this.port.postMessage({ type: 'progress', played: this.played })
    return true
  }
}

registerProcessor('vs-playback', PlaybackProcessor)
