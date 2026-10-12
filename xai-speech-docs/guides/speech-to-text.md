<!-- Source: https://docs.x.ai/developers/model-capabilities/audio/speech-to-text (markdown: https://docs.x.ai/developers/model-capabilities/audio/speech-to-text.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Model Capabilities

# Speech to Text

Transcribe audio files into text with a single API call, or stream audio in real time over WebSocket. The API supports 12 audio formats, word-level timestamps, multichannel transcription, and text formatting.

## Quick Start

Transcribe an audio file with a single API call:

```bash
curl -X POST https://api.x.ai/v1/stt \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F model=grok-voice-transcribe-2.0 \
  -F format=true \
  -F language=en \
  -F "keyterm=Understand The Universe" \
  -F file=@audio.mp3
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

response = requests.post(
    "https://api.x.ai/v1/stt",
    headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
    files={"file": ("audio.mp3", open("audio.mp3", "rb"), "audio/mpeg")},
    data=[
        ("model", "grok-voice-transcribe-2.0"),
        ("format", "true"),
        ("language", "en"),
        ("keyterm", "Understand The Universe"),
    ],
)
response.raise_for_status()

result = response.json()
print(result["text"])
print(f"Duration: {result['duration']}s")
for word in result.get("words", []):
    print(f"  {word['start']:.2f}s - {word['end']:.2f}s: {word['text']}")
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";

const formData = new FormData();
formData.append("model", "grok-voice-transcribe-2.0");
formData.append("format", "true");
formData.append("language", "en");
formData.append("keyterm", "Understand The Universe");
formData.append("file", new Blob([fs.readFileSync("audio.mp3")]), "audio.mp3");

const response = await fetch("https://api.x.ai/v1/stt", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.XAI_API_KEY}`,
  },
  body: formData,
});

if (!response.ok) throw new Error(`STT error ${response.status}`);

const result = await response.json();
console.log(result.text);
console.log(`Duration: ${result.duration}s`);
for (const word of result.words ?? []) {
  console.log(`  ${word.start.toFixed(2)}s - ${word.end.toFixed(2)}s: ${word.text}`);
}
```

Note: The `file` parameter must be provided after all other parameters in the multipart form.

[Get API Key →](https://console.x.ai/team/default/api-keys?campaign=voice-docs-stt\&utm_source=docs\&utm_medium=referral\&utm_campaign=developers-model-capabilities-audio-speech-to-text\&utm_content=api-keys)

[Live Voice Demos](https://x.ai/api/voice)

## Model Selection

Pass `model` on the REST form or as a WebSocket query parameter.

| Model | Description |
|-------|-------------|
| `grok-voice-transcribe-2.0` | Our best transcription model. Default when `model` is omitted. |

## Supported Languages

`grok-voice-transcribe-2.0` transcribes 38+ languages, including every language listed below. It detects the spoken language automatically and follows switches partway through a recording, so `language` is optional. When you know what's being spoken, set `language` to its code and the model leans toward that language when the audio is ambiguous.

| Language | Code | | Language | Code |
|----------|------|-|----------|------|
| Arabic | `ar` | | Italian | `it` |
| Bosnian | `bs` | | Japanese | `ja` |
| Bulgarian | `bg` | | Korean | `ko` |
| Cantonese | `yue` | | Macedonian | `mk` |
| Catalan | `ca` | | Malay | `ms` |
| Chinese (Mandarin) | `zh` | | Norwegian (Bokmål) | `nb` |
| Croatian | `hr` | | Persian | `fa` |
| Czech | `cs` | | Polish | `pl` |
| Danish | `da` | | Portuguese | `pt` |
| Dutch | `nl` | | Romanian | `ro` |
| English | `en` | | Russian | `ru` |
| Filipino | `fil` | | Slovak | `sk` |
| Finnish | `fi` | | Spanish | `es` |
| French | `fr` | | Swedish | `sv` |
| German | `de` | | Thai | `th` |
| Greek | `el` | | Turkish | `tr` |
| Hindi | `hi` | | Ukrainian | `uk` |
| Hungarian | `hu` | | Urdu | `ur` |
| Indonesian | `id` | | Vietnamese | `vi` |

Spanish, Portuguese, and Arabic also accept regional codes. `es` means Mexican Spanish (`es-MX`), `pt` means Brazilian Portuguese (`pt-BR`), and `ar` means Egyptian Arabic (`ar-EG`). Pass `es-ES` or `pt-PT` for the European variants, or `ar-AE` or `ar-SA` for Emirati or Saudi Arabic.

Text formatting (`format=true`) writes spoken numbers, currencies, and units in their written form in Arabic, Chinese (Mandarin), English, French, German, Japanese, Portuguese, Russian, Spanish, Swedish, and Vietnamese. Formatting follows the `language` code, so pass both. In other languages, `format=true` has no effect.

## Request Body

The request uses `multipart/form-data`. Either `file` or `url` must be provided.

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `file` | file | | ✓† | Audio file to transcribe. Max **500 MB**. See [Supported Formats](#supported-audio-formats). Must be the last field in the multipart form. |
| `url` | string | | ✓† | URL of an audio file to download and transcribe (server-side). |
| `model` | string | `grok-voice-transcribe-2.0` | | `grok-voice-transcribe-2.0` (default). |
| `audio_format` | string | | | Format hint for raw/headerless audio: `pcm`, `mulaw`, `alaw`. Container formats are auto-detected — do not set this field for MP3, WAV, etc. |
| `sample_rate` | integer | | | Sample rate in Hz. Only required for raw audio (`pcm`, `mulaw`, `alaw`). Supported: `8000`, `16000`, `22050`, `24000`, `44100`, `48000`. |
| `language` | string | | | Language code (e.g. `en`, `fr`, `de`). Biases transcription toward that language and selects the formatting rules for `format=true`. See [Supported Languages](#supported-languages). |
| `format` | boolean | `false` | | When `true`, enables Inverse Text Normalization — converts spoken numbers/currency to written form (e.g. "one hundred dollars" → "$100"). Requires `language`. See [Supported Languages](#supported-languages) for coverage. |
| `multichannel` | boolean | `false` | | When `true`, transcribes each audio channel independently. Results returned in the `channels` array. |
| `channels` | integer | | | Number of audio channels (2–8). Only required for multichannel raw audio. Auto-detected for container formats. |
| `diarize` | boolean | `false` | | When `true`, enables speaker diarization. Each word in the response includes a `speaker` field (integer) identifying the detected speaker. |
| `keyterm` | string | | | A key term to bias transcription toward (e.g. product names, proper nouns). Repeat the field for multiple terms (e.g. `keyterm=Understand+The+Universe`). Max 100 terms, each up to 50 characters. |
| `filler_words` | boolean | `false` | | When `true`, filler words (e.g. "uh", "um", "er") are included in the transcript. When `false` (default), filler words are automatically removed from the transcript text and the `words` array. |
| `vad_threshold` | number | `0.5` | | Speech-probability threshold for the voice-activity gate (0.0–1.0). Audio segments scoring below the threshold are treated as non-speech and skipped for transcription. Lower values transcribe quieter or noisier speech (e.g. narrowband telephony) but may produce spurious text for background noise. `0` disables the gate. |

† Either `file` or `url` must be provided.

Option fields should precede `file` in the multipart body — for streamable uploads, fields sent after `file` may be ignored.

### Example with text formatting

```bash
curl -X POST https://api.x.ai/v1/stt \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F model=grok-voice-transcribe-2.0 \
  -F format=true \
  -F language=en \
  -F "keyterm=Understand The Universe" \
  -F file=@meeting.mp3
```

The `file` parameter must be provided after all other parameters in the multipart form.

## Response

The response includes the full transcript, audio duration, and word-level timestamps.

```json
{
  "text": "The balance is $167,983.15.",
  "language": "en",
  "duration": 3.45,
  "words": [
    { "text": "The", "start": 0.24, "end": 0.48 },
    { "text": "balance", "start": 0.48, "end": 0.96 },
    { "text": "is", "start": 0.96, "end": 1.12 },
    { "text": "$167,983.15.", "start": 1.12, "end": 3.20 }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Full transcript text. |
| `language` | string | Detected language as a BCP-47 code (e.g. `en`, `es-mx`). |
| `duration` | number | Audio duration in seconds (2 d.p.). |
| `words` | array | Word-level segments with `text`, `start`, `end`, and `speaker` (integer, only when `diarize=true`). |
| `channels` | array | Per-channel transcripts (only when `multichannel=true`). Each entry has `index`, `text`, and `words`. |

## Supported Audio Formats

### Container formats (auto-detected)

| Format | Extension | Description |
|--------|-----------|-------------|
| WAV | `.wav` | Waveform Audio — lossless, best quality input |
| MP3 | `.mp3` | MPEG Audio Layer 3 — widely supported |
| OGG | `.ogg` | Ogg container — open format |
| Opus | `.opus` | Opus codec — low-latency, high quality |
| FLAC | `.flac` | Free Lossless Audio Codec — lossless compression |
| AAC | `.aac` | Advanced Audio Coding |
| MP4 | `.mp4` | MPEG-4 container |
| M4A | `.m4a` | MPEG-4 Audio — Apple ecosystem standard |
| MKV | `.mkv` | Matroska container — supports MP3, AAC, and FLAC audio codecs |

### Raw formats (require `audio_format` and `sample_rate`)

| Format | `audio_format` value | Description |
|--------|---------------------|-------------|
| PCM | `pcm` | Signed 16-bit little-endian (2 bytes/sample) |
| µ-law | `mulaw` | G.711 µ-law (1 byte/sample) |
| A-law | `alaw` | G.711 A-law (1 byte/sample) |

### Limits

* **Max file size:** 500 MB
* **Channels:** Mono, stereo, or up to 8 channels (with `multichannel=true`)
* **Sample rates:** 8000, 16000, 22050, 24000, 44100, 48000 Hz

## Streaming Speech-to-Text (WebSocket)

For real-time transcription, use the WebSocket API at `wss://api.x.ai/v1/stt`. The client streams raw audio as binary WebSocket frames and receives JSON transcript events as the audio is processed.

**Endpoint:** `wss://api.x.ai/v1/stt`

Configuration is done via URL query parameters — no setup message required. Audio is sent as raw binary frames (no base64 encoding).

> [!NOTE]
>
> **Never expose your API key in client-side code.** Always proxy WebSocket connections through your backend.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_rate` | integer | `16000` | Audio sample rate in Hz. Ignored for `encoding=opus` — Opus packets are sample-rate-agnostic. |
| `encoding` | string | `pcm` | Audio encoding: `pcm`, `mulaw`, `alaw`, or `opus`. See [Opus Streaming](#opus-streaming). |
| `interim_results` | boolean | `false` | When `true`, emit partial transcripts `is_final=false` every ~500 ms. |
| `endpointing` | integer | `400` | Silence duration (ms) before utterance-final event. Range: 0–5000. `0` = fire on any VAD silence boundary. |
| `language` | string | | Language code (e.g. `en`, `fr`, `de`). Biases transcription toward that language and selects the formatting rules for `format=true`. See [Supported Languages](#supported-languages). |
| `format` | boolean | `false` | When `true`, converts spoken numbers, currencies, and units to written form. Requires `language`. See [Supported Languages](#supported-languages) for coverage. |
| `model` | string | `grok-voice-transcribe-2.0` | `grok-voice-transcribe-2.0` (default). |
| `diarize` | boolean | | When `true`, enables speaker diarization. Words include a `speaker` field identifying the detected speaker. |
| `filler_words` | boolean | `false` | When `true`, filler words (e.g. `uh`, `um`, `er`) are included in the transcript. When `false` (default), filler words are automatically removed. |
| `multichannel` | boolean | `false` | Per-channel transcription. Requires `channels` ≥ 2. Not supported with `encoding=opus`. |
| `channels` | integer | `1` | Number of interleaved audio channels (max 8). |
| `keyterm` | string | | A key term to bias transcription toward (e.g. product names, proper nouns). Repeat the parameter for multiple terms (e.g. `keyterm=Understand+The+Universe`). Max 100 terms, each up to 50 characters. |
| `smart_turn` | number | | End-of-turn detection threshold (0.0–1.0). When set, enables Smart Turn — an ML model predicts whether the speaker has finished their thought at each silence boundary. See [Smart Turn](#smart-turn). |
| `smart_turn_timeout` | integer | | Maximum silence duration (ms) before forcing `speech_final`, even when the Smart Turn model predicts the speaker hasn't finished. Range: 1–5000. Only applies when `smart_turn` is enabled. See [Smart Turn](#smart-turn). |
| `vad_threshold` | number | `0.08` | Speech-probability threshold for the voice-activity gate (0.0–1.0). Audio in chunks scoring below the threshold is treated as non-speech and skipped for transcription. Lower values transcribe quieter or noisier speech (e.g. narrowband telephony) but may produce spurious text for background noise. `0` disables the gate. Does not affect endpointing or `speech_final` timing. |

### Server Events

| Event | Description |
|-------|-------------|
| `transcript.created` | Server ready — wait for this before sending audio. |
| `transcript.partial` | Transcript result with `text`, `words`, `is_final`, `speech_final`, `start`, `duration`. Includes `channel_index` when `multichannel=true`. Includes `end_of_turn_confidence` when `smart_turn` is enabled. |
| `transcript.done` | Final transcript after `audio.done`. `duration` always present. Includes `channel_index` when `multichannel=true` — one event sent per channel. Connection closes after this. |
| `error` | Error with `message` field. Most errors (including undecodable audio frames) close the connection; client message parse errors keep it open. |

The `transcript.partial` event uses `is_final` and `speech_final` to convey three states:

| `is_final` | `speech_final` | Meaning |
|:---:|:---:|---|
| `false` | `false` | **Interim** — text may change (only when `interim_results=true`) |
| `true` | `false` | **Chunk final** — text locked, ~3s of speech finalized. When `smart_turn` is enabled, silence pauses where the model's confidence is below the threshold are demoted to chunk final instead of utterance final. |
| `true` | `true` | **Utterance final** — speaker stopped, complete stitched utterance. When `smart_turn` is enabled, only fires when the model's end-of-turn confidence exceeds the threshold, or when `smart_turn_timeout` is exceeded. |

### Client Messages

* **Binary frames** — raw audio in the specified encoding (streamed in real-time-paced chunks, e.g. 100 ms). With `encoding=opus`, each binary frame must contain exactly one Opus packet — see [Opus Streaming](#opus-streaming).
* **`{"type": "finalize"}`** — force the current utterance to finalize as `speech_final` immediately for PTT
* **`{"type": "audio.done"}`** — signal end of audio, triggers `transcript.done`

`transcript.done` tells the server no more audio will be sent and to flush the remaining transcript and close the websocket.

**Push-to-talk example** (finalize on button release, then continue the session):

```json
{"type": "Finalize"}
```

**Per-channel finalize** (multichannel only — e.g. agent on channel 0):

```json
{"type": "Finalize", "channel": 0}
```

### Opus Streaming

Set `encoding=opus` to stream compressed audio instead of raw PCM — roughly 4 KB/s versus 48 KB/s for PCM16 at 24 kHz, with no client-side resampling.

**How it works:**

* Send **exactly one raw Opus packet per binary WebSocket frame**. Opus packets don't mark their own boundaries — the WebSocket framing does — so never concatenate packets or split one across frames.
* Omit `sample_rate` — Opus packets don't carry one, and the parameter is ignored for this encoding. Encode at whatever rate your audio source produces.
* `multichannel` is not supported with Opus — mono only.
* Send raw packets, not containers. To transcribe an Ogg-Opus or WebM file, use the [batch endpoint](#supported-audio-formats) instead — it auto-detects containers.
* If a frame can't be decoded, the server sends an `error` event and closes the session. Misframed packets often decode as noise rather than an error, so double-check that your encoder emits one whole packet per frame.

**Example URL:**

```
wss://api.x.ai/v1/stt?model=grok-voice-transcribe-2.0&encoding=opus&interim_results=true
```

**Typical use case:** Dictation and live transcription from mobile or other bandwidth-constrained clients, where streaming raw PCM is wasteful. Most platform audio APIs and WebRTC stacks produce Opus packets natively.

### Multichannel Streaming

When `multichannel=true` and `channels` ≥ 2, the server transcribes each audio channel independently. Send interleaved multichannel PCM (e.g. L,R,L,R,… for stereo) as binary frames, and the server de-interleaves and processes each channel in parallel.

**How it works:**

* `transcript.created` is sent once (session-level — no `channel_index`).
* `transcript.partial` events include a `channel_index` field (0-based) identifying the source channel. Events from different channels arrive interleaved.
* `transcript.done` is sent **once per channel** after `audio.done`, each with its own `channel_index`.
* Client `Finalize` without `channel` finalizes every channel at once; `{"type": "Finalize", "channel": N}` finalizes only channel `N` (0-based).
* Chunk sizes should account for all channels — e.g. for stereo PCM16 at 16 kHz, 100 ms = 6,400 bytes (3,200 per channel × 2 channels).

**Example URL:**

```
wss://api.x.ai/v1/stt?model=grok-voice-transcribe-2.0&sample_rate=16000&encoding=pcm&multichannel=true&channels=2&interim_results=true
```

**Typical use case:** Call center recordings with agent on channel 0 and customer on channel 1, enabling per-speaker transcription without requiring speaker diarization.

### Smart Turn

Smart Turn uses a lightweight ML model to predict whether the speaker has finished their thought during silence pauses, reducing false endpointing on mid-sentence pauses (e.g. while dictating numbers or thinking between clauses).

**How it works:**

* When enabled via `smart_turn=<threshold>`, the model evaluates accumulated audio at each VAD silence boundary.
* If the end-of-turn confidence exceeds the threshold, `speech_final=true` fires normally.
* If confidence is below the threshold, the event is demoted to `chunk_final` (`is_final=true`, `speech_final=false`) — the transcript text is locked but the utterance continues.
* Every `transcript.partial` event includes an `end_of_turn_confidence` field (0.0–1.0) when Smart Turn is enabled.
* During active speech, `end_of_turn_confidence` is `0.0` (the model only runs at silence boundaries).

| Threshold | Behavior |
|-----------|----------|
| `0.5` | Balanced — catches most natural turn endings |
| `0.7` | Conservative — requires higher confidence to end a turn, better for dictation and number sequences |
| `0.9` | Very conservative — only ends on highly confident turn completions |

**Silence timeout (`smart_turn_timeout`):**

When Smart Turn is enabled, the model has full control over when `speech_final` fires. To prevent sessions from hanging during extended silence (e.g. the user walks away), set `smart_turn_timeout` to a maximum silence duration in milliseconds (1–5000). If the model keeps predicting "not done" for longer than this duration, `speech_final` fires anyway as a safety net.

```
wss://api.x.ai/v1/stt?model=grok-voice-transcribe-2.0&sample_rate=16000&encoding=pcm&interim_results=true&smart_turn=0.7&smart_turn_timeout=3000
```

Without `smart_turn_timeout`, the model has unlimited control — `speech_final` only fires when confidence exceeds the threshold.

**Example event with Smart Turn enabled:**

```json
{
  "type": "transcript.partial",
  "text": "I will buy two of those, please.",
  "words": [...],
  "is_final": true,
  "speech_final": true,
  "start": 0.0,
  "duration": 2.4,
  "end_of_turn_confidence": 0.983
}
```

**Typical use case:** Voice assistants and conversational AI where you want to avoid cutting the user off mid-sentence. Without Smart Turn, a brief pause while dictating a phone number or thinking between clauses triggers `speech_final`. With Smart Turn, the model holds off until it detects a natural turn ending (confidence 0.95+) while correctly suppressing during mid-sentence pauses (confidence ~0.005).

### Full Example

```python customLanguage="pythonWithoutSDK"
import asyncio
import json
import os

import websockets

API_KEY = os.environ["XAI_API_KEY"]
WS_URL = "wss://api.x.ai/v1/stt?model=grok-voice-transcribe-2.0&sample_rate=16000&encoding=pcm&interim_results=true&language=en&keyterm=Understand+The+Universe"

async def transcribe_stream(audio_file: str):
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with websockets.connect(WS_URL, additional_headers=headers) as ws:
        # Wait for server ready signal
        msg = json.loads(await ws.recv())
        assert msg["type"] == "transcript.created"
        print("Server ready")

        # Read raw PCM from a WAV file (skip 44-byte header)
        with open(audio_file, "rb") as f:
            f.read(44)  # Skip WAV header
            chunk_size = 16000 * 2 // 10  # 100ms of PCM16 at 16kHz

            while chunk := f.read(chunk_size):
                await ws.send(chunk)  # Send raw binary — no base64
                await asyncio.sleep(0.1)

        # Signal end of audio
        await ws.send(json.dumps({"type": "audio.done"}))

        # Collect events until transcript.done
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "transcript.partial":
                prefix = "FINAL" if event["is_final"] else "partial"
                print(f"[{prefix}] {event['text']}")
            elif event["type"] == "transcript.done":
                print(f"\nFull transcript: {event['text']}")
                print(f"Duration: {event['duration']}s")
                break

asyncio.run(transcribe_stream("audio.wav"))
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";
import WebSocket from "ws";

const apiKey = process.env.XAI_API_KEY;
const url = "wss://api.x.ai/v1/stt?model=grok-voice-transcribe-2.0&sample_rate=16000&encoding=pcm&interim_results=true&language=en&keyterm=Understand+The+Universe";

const ws = new WebSocket(url, { headers: { Authorization: `Bearer ${apiKey}` } });

ws.on("open", () => console.log("Connected"));

ws.on("message", (data) => {
  const event = JSON.parse(data);
  switch (event.type) {
    case "transcript.created":
      console.log("Server ready — streaming audio...");
      // Read WAV file, skip 44-byte header, send 100ms chunks
      const audio = fs.readFileSync("audio.wav").slice(44);
      const chunkSize = 3200; // 100ms at 16kHz, 16-bit
      let offset = 0;
      const interval = setInterval(() => {
        if (offset >= audio.length) {
          clearInterval(interval);
          ws.send(JSON.stringify({ type: "audio.done" }));
          return;
        }
        ws.send(audio.slice(offset, offset + chunkSize));
        offset += chunkSize;
      }, 100);
      break;
    case "transcript.partial":
      const prefix = event.is_final ? "FINAL" : "partial";
      console.log(`[${prefix}] ${event.text}`);
      break;
    case "transcript.done":
      console.log(`\nFull transcript: ${event.text}`);
      console.log(`Duration: ${event.duration}s`);
      ws.close();
      break;
  }
});
```

### Use Cases

* **Live captions** — Real-time subtitles for video calls, meetings, and live streams
* **Voice assistants** — Transcribe user speech for natural language understanding pipelines
* **Call centers** — Real-time agent assistance with multichannel per-speaker transcription
* **Accessibility** — Live transcription for hearing-impaired users
* **Voice commands** — Low-latency speech-to-action for hands-free interfaces

### Tips for Streaming STT

* **Use 16 kHz sample rate with PCM encoding** (`sample_rate=16000&encoding=pcm`) — this is the model's native rate and avoids resampling on the server
* **Enable `interim_results`** for responsive UX — show transcription as the user speaks
* **Add `format=true` with `language`** (e.g. `language=en&format=true`) to write numbers and currencies in their standard form
* **Send 100 ms audio chunks** (3,200 bytes at 16 kHz PCM16) for a good balance of latency and efficiency
* **Use `encoding=opus` on bandwidth-constrained clients** — ~4 KB/s versus 48 KB/s for raw PCM at 24 kHz. See [Opus Streaming](#opus-streaming)
* **Wait for `transcript.created`** before sending audio — the server needs to initialize its ASR backend

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `200` | Success | Transcription in the response body |
| `400` | Bad request | Missing `file`/`url`, unsupported format, missing `sample_rate` for raw audio, `format=true` without `language` |
| `401` | Unauthorized | API key is missing or invalid |
| `413` | Payload too large | File exceeds 500 MB |
| `429` | Rate limited | Back off and retry with exponential delay |
| `502` | Bad gateway | URL download failed (when using `url`) |
| `503` | Service unavailable | Backend not available — retry |

## Related

* [Voice Overview](https://docs.x.ai/developers/model-capabilities/audio/voice) — Overview of all SpaceXAI voice capabilities
* [Text to Speech](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech) — Convert text to speech
* [API Reference — Speech to text](https://docs.x.ai/developers/rest-api-reference/inference/voice#speech-to-text---rest) — Full REST endpoint specification
* [API Reference — Streaming](https://docs.x.ai/developers/rest-api-reference/inference/voice#speech-to-text---streaming) — WebSocket streaming specification
