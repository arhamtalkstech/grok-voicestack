import fs from 'node:fs'
import path from 'node:path'

/**
 * Generates the caller's voice for the live test with xAI text-to-speech, then pads it with
 * silence so the agent's greeting finishes before the "caller" speaks. Chrome plays this file as
 * the microphone (--use-file-for-fake-audio-capture).
 */
const LINE = "Hi. I'm building a voice agent that answers the phone for my dental clinic. Which voices can I use?"
const LEAD_SILENCE_S = 9

function findChunk(buf: Buffer, id: string): { offset: number; size: number } {
  let offset = 12
  while (offset + 8 <= buf.length) {
    const chunkId = buf.toString('ascii', offset, offset + 4)
    const size = buf.readUInt32LE(offset + 4)
    if (chunkId === id) return { offset: offset + 8, size }
    offset += 8 + size + (size % 2)
  }
  throw new Error(`WAV chunk ${id} not found`)
}

export default async function globalSetup() {
  const key = process.env.XAI_API_KEY
  if (!key) throw new Error('Set XAI_API_KEY to run the live browser test')
  const out = path.resolve('e2e/.cache/caller.wav')
  fs.mkdirSync(path.dirname(out), { recursive: true })
  const res = await fetch('https://api.x.ai/v1/tts', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: LINE, voice_id: 'rex', language: 'en', output_format: { codec: 'wav', sample_rate: 48000 } }),
  })
  if (!res.ok) throw new Error(`TTS failed: ${res.status} ${await res.text()}`)
  const wav = Buffer.from(await res.arrayBuffer())
  const fmt = findChunk(wav, 'fmt ')
  const channels = wav.readUInt16LE(fmt.offset + 2)
  const rate = wav.readUInt32LE(fmt.offset + 4)
  const bits = wav.readUInt16LE(fmt.offset + 14)
  const data = findChunk(wav, 'data')
  const pcm = wav.subarray(data.offset, data.offset + data.size)
  const silence = Buffer.alloc(Math.round(LEAD_SILENCE_S * rate) * channels * (bits / 8))
  const tail = Buffer.alloc(Math.round(20 * rate) * channels * (bits / 8))
  const body = Buffer.concat([silence, pcm, tail])
  const header = Buffer.alloc(44)
  header.write('RIFF', 0)
  header.writeUInt32LE(36 + body.length, 4)
  header.write('WAVE', 8)
  header.write('fmt ', 12)
  header.writeUInt32LE(16, 16)
  header.writeUInt16LE(1, 20)
  header.writeUInt16LE(channels, 22)
  header.writeUInt32LE(rate, 24)
  header.writeUInt32LE((rate * channels * bits) / 8, 28)
  header.writeUInt16LE((channels * bits) / 8, 32)
  header.writeUInt16LE(bits, 34)
  header.write('data', 36)
  header.writeUInt32LE(body.length, 40)
  fs.writeFileSync(out, Buffer.concat([header, body]))
}
