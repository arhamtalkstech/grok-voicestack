<!-- Source: https://docs.x.ai/developers/rest-api-reference/inference/speech-to-text (markdown: https://docs.x.ai/developers/rest-api-reference/inference/speech-to-text.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Inference API

# Voice

***

## POST /v1/stt

Transcribe an audio file to text.

### Request Body

* `file` (string) — Audio file to transcribe. Maximum size: 500 MB. Supported container formats (auto-detected): \`wav\`, \`mp3\`, \`ogg\`, \`opus\`, \`flac\`, \`aac\`, \`mp4\`, \`m4a\`, \`mkv\` (MP3/AAC/FLAC codecs only). Supported raw formats (requires \`audio\_format\` and \`sample\_rate\`): \`pcm\`, \`mulaw\`, \`alaw\`. Must be the last field in the multipart form.

* `url` (string) — URL of an audio file to download and transcribe (server-side). Either \`file\` or \`url\` must be provided.

* `audio_format` ("pcm" | "mulaw" | "alaw" | "wav" | "mp3" | "ogg" | "opus" | "flac" | "aac" | "mp4" | "m4a" | "mkv") — Audio format hint. \*\*Only required for raw/headerless formats\*\* (\`pcm\`, \`mulaw\`, \`alaw\`). For container formats (MP3, WAV, OGG, etc.) the server auto-detects the format from the file header — do not set this field.

* `sample_rate` ("8000" | "16000" | "22050" | "24000" | "44100" | "48000") — Audio sample rate in Hz. \*\*Required when \`audio\_format\` is a raw format\*\* (\`pcm\`, \`mulaw\`, \`alaw\`). Ignored for container formats. Either \`sample\_rate\` or \`sample\_rate\_hertz\` may be used.

* `language` (string) — Language code for the audio (e.g. \`en\`, \`fr\`, \`de\`, \`ja\`). Biases transcription toward that language. When set together with \`format=true\`, enables Inverse Text Normalization — spoken-form numbers, currencies, and units are converted to their written form. Formatting is available for \`ar\`, \`de\`, \`en\`, \`es\`, \`fr\`, \`ja\`, \`pt\`, \`ru\`, \`sv\`, \`vi\`, and \`zh\`.

* `format` ("true" | "false") — When \`true\`, enables text formatting. Requires \`language\` to be set.

* `multichannel` ("true" | "false") — When \`true\`, enables per-channel transcription. Each audio channel is transcribed independently and results are returned in the \`channels\` array.

* `channels` (integer) — Number of audio channels. Required for multichannel raw audio (min 2, max 8). For container formats, the channel count is auto-detected from the file header.

* `diarize` ("true" | "false") — When \`true\`, enables speaker diarization. Each word in the response includes a \`speaker\` field (integer) identifying the detected speaker.

* `keyterm` (array\<string>) — Key terms to bias transcription toward (e.g. product names, proper nouns). Repeat the field for each term (e.g. \`keyterm=Understand+The+Universe\`). Max 100 terms, each up to 50 characters.

* `filler_words` ("true" | "false") — When \`true\`, filler words (e.g. "uh", "um", "er") are included in the transcript. When \`false\` (default), filler words are automatically removed from the transcript text and the \`words\` array.

* `vad_threshold` (number) — Speech-probability threshold for the voice-activity gate (0.0–1.0). Audio segments scoring below the threshold are treated as non-speech and skipped for transcription. Lower values transcribe quieter or noisier speech (e.g. narrowband telephony) but may produce spurious text for background noise; \`0\` disables the gate entirely. Default: \`0.5\`.

### Response Body

* `text` (string, required) — Full transcript text. For multichannel requests, this is a merged transcript across all channels (words interleaved by timestamp).

* `language` (string, required) — Detected language as a BCP-47 code (e.g. \`en\`, \`es-mx\`).

* `duration` (number, required) — Audio duration in seconds (rounded to 2 decimal places).

* `words` (array\<object>) — Word-level segments with timestamps. Omitted when empty.

  * `text` (string, required) — The word text.

  * `start` (number, required) — Word start time in seconds (2 d.p.).

  * `end` (number, required) — Word end time in seconds (2 d.p.).

  * `confidence` (number) — Confidence score (0.0–1.0, entropy-based). Omitted when 0.

  * `speaker` (integer) — Speaker index (0-based). Only present when \`diarize=true\`.

* `channels` (array\<object>) — Per-channel transcripts. Only present when \`multichannel=true\`. Omitted for single-channel audio.

  * `index` (integer, required) — Zero-based channel index in the source audio.

  * `language` (string) — Detected language as a BCP-47 code for this channel (e.g. \`en\`, \`es-mx\`).

  * `text` (string, required) — Full transcript text for this channel.

  * `words` (array\<object>) — Word-level segments with timestamps for this channel.

    * `text` (string, required) — The word text.

    * `start` (number, required) — Word start time in seconds (2 d.p.).

    * `end` (number, required) — Word end time in seconds (2 d.p.).

    * `confidence` (number) — Confidence score (0.0–1.0, entropy-based). Omitted when 0.

    * `speaker` (integer) — Speaker index (0-based). Only present when \`diarize=true\`.

\*\*Response example:\*\*

```json
{
  "text": "The balance is $167,983.15. That is $23.4 kilograms.",
  "language": "en",
  "duration": 8.4,
  "words": [
    {
      "text": "The",
      "start": 0,
      "end": 0.24,
      "confidence": 0.33
    },
    {
      "text": "balance",
      "start": 0.24,
      "end": 0.64,
      "confidence": 0.67
    },
    {
      "text": "is",
      "start": 0.64,
      "end": 0.88,
      "confidence": 0.41
    },
    {
      "text": "$167,983.15.",
      "start": 0.88,
      "end": 4.8,
      "confidence": 0.07
    },
    {
      "text": "That",
      "start": 6.16,
      "end": 6.48,
      "confidence": 0.29
    },
    {
      "text": "is",
      "start": 6.48,
      "end": 6.64,
      "confidence": 0.4
    },
    {
      "text": "$23.4",
      "start": 6.64,
      "end": 7.52,
      "confidence": 0.07
    },
    {
      "text": "kilograms.",
      "start": 7.76,
      "end": 8.4,
      "confidence": 0.09
    }
  ]
}
```

***

## Speech to text - Streaming

WebSocket endpoint: `wss://api.x.ai/v1/stt`

Real-time streaming speech-to-text via WebSocket. Stream raw audio as binary frames and receive JSON transcript events as the audio is processed. Configuration is done via query parameters at connection time. The default is grok-voice-transcribe-2.0.

Full schemas and examples: [`/stt-streaming.ws.json`](https://docs.x.ai/stt-streaming.ws.json)

### Query Parameters

* `sample_rate` (integer, optional, default: 16000) — Audio sample rate in Hz. Supported values: \`8000\`, \`16000\`, \`22050\`, \`24000\`, \`44100\`, \`48000\`. Ignored with \`encoding=opus\` — Opus packets are sample-rate-agnostic.

* `encoding` (string, optional, default: pcm) — Audio encoding format. \`pcm\` — signed 16-bit little-endian (2 bytes/sample). \`mulaw\` — G.711 µ-law (1 byte/sample). \`alaw\` — G.711 A-law (1 byte/sample). \`opus\` — raw Opus packets, one packet per binary WebSocket frame, mono only.

* `interim_results` (boolean, optional, default: false) — When \`true\`, the server emits partial transcript events (\`is\_final=false\`) approximately every 500 ms while audio is being processed. When \`false\` (default), only finalized results are sent.

* `endpointing` (integer, optional, default: 400) — Silence duration in milliseconds before the server fires a \`speech\_final=true\` event, indicating the speaker stopped talking. Range: 0–5000. Set to \`0\` for no delay (fire on any VAD silence boundary). Default: 400ms.

* `language` (string, optional, default: ) — Language code (e.g. \`en\`, \`fr\`, \`de\`, \`ja\`). Biases transcription toward that language and selects the formatting rules for \`format=true\`. See Supported Languages on the Speech to Text page.

* `format` (boolean, optional, default: false) — When \`true\`, enables Inverse Text Normalization — spoken-form numbers, currencies, and units are converted to their written form. Requires \`language\`; available for \`ar\`, \`de\`, \`en\`, \`es\`, \`fr\`, \`ja\`, \`pt\`, \`ru\`, \`sv\`, \`vi\`, and \`zh\`.

* `model` (string, optional, default: grok-voice-transcribe-2.0) — \`grok-voice-transcribe-2.0\` (default).

* `multichannel` (boolean, optional, default: false) — When \`true\`, enables per-channel transcription for interleaved multichannel audio. Requires \`channels\` to be set to ≥ 2. Not supported with \`encoding=opus\`.

* `channels` (integer, optional, default: 1) — Number of interleaved audio channels. Required when \`multichannel=true\`. Min: 2, Max: 8.

* `diarize` (boolean, optional, default: false) — When \`true\`, enables speaker diarization. Words in \`transcript.partial\` and \`transcript.done\` events include a \`speaker\` field (integer) identifying the detected speaker.

* `keyterm` (string (repeatable), optional) — A key term to bias transcription toward (e.g. product names, proper nouns). Repeat the parameter for each term (e.g. \`keyterm=Understand+The+Universe\`). Max 100 terms, each up to 50 characters.

* `filler_words` (boolean, optional, default: false) — When \`true\`, filler words (e.g. \`uh\`, \`um\`, \`er\`) are included in the transcript. When \`false\` (default), filler words are automatically removed from the transcript text and the \`words\` array.

* `smart_turn` (number, optional) — Enable Smart Turn end-of-turn detection. Set to a confidence threshold between \`0.0\` and \`1.0\`. When the model's end-of-turn probability exceeds this threshold at a VAD silence boundary, \`speech\_final\` fires immediately. When confidence is below the threshold, \`speech\_final\` is suppressed and the event is demoted to \`chunk\_final\`. Every \`transcript.partial\` event includes an \`end\_of\_turn\_confidence\` field (0.0–1.0) when Smart Turn is enabled. Example: \`smart\_turn=0.7\`.

* `smart_turn_timeout` (integer, optional) — Maximum silence duration in milliseconds before forcing \`speech\_final\`, even when the Smart Turn model predicts the speaker hasn't finished. Acts as a safety net to prevent sessions from hanging during extended silence. Only applies when \`smart\_turn\` is enabled. Range: 1–5000. Example: \`smart\_turn\_timeout=3000\`.

* `vad_threshold` (number, optional, default: 0.08) — Speech-probability threshold for the voice-activity gate (0.0–1.0). Audio in chunks scoring below the threshold is treated as non-speech and skipped for transcription. Lower values transcribe quieter or noisier speech (e.g. narrowband telephony) but may produce spurious text for background noise; \`0\` disables the gate entirely. Does not affect endpointing or \`speech\_final\` timing. Default: \`0.08\`.

### Client Messages

* `Binary frame (audio)` — Send raw audio as binary WebSocket frames in the encoding specified by the \`encoding\` query parameter. Audio should be streamed in real-time-paced chunks (e.g. 100 ms at a time). No base64 encoding — send raw bytes directly. With \`encoding=opus\`, each binary frame must contain exactly one raw Opus packet — never concatenate packets or split one across frames. An undecodable frame sends an \`error\` event and closes the session.

* `finalize` — Force the current utterance to finalize as \`speech\_final\` immediately, without waiting for VAD endpointing or Smart Turn. The session stays open so you can continue streaming audio. Accepts \`finalize\` or \`Finalize\` as the type value. When \`multichannel=true\`, optional \`channel\` (0-based) limits the finalize to that channel; omit \`channel\` to finalize every channel.

* `audio.done` — Signal that all audio has been sent. The server flushes any remaining buffered audio, emits final transcript events, and sends a \`transcript.done\` event. The connection closes after \`transcript.done\`.

### Server Messages

* `transcript.created` — Sent immediately after the WebSocket connection is established and the server is ready to receive audio. \*\*Wait for this event before sending audio\*\* — the server needs to initialize its ASR backend.

* `transcript.partial` — A transcript result for a portion of the audio stream. Two boolean fields convey state: interim (\`is\_final=false\`) means text may still change, chunk final (\`is\_final=true\`, \`speech\_final=false\`) means the chunk is locked, and utterance final (\`is\_final=true\`, \`speech\_final=true\`) means the speaker stopped talking.

* `transcript.done` — Final transcript after \`audio.done\`. \`duration\` always present. One per channel when \`multichannel=true\`. Connection closes after this event.

* `error` — An error occurred during the session. Most errors (pipeline failures, stream timeouts, undecodable audio frames) close the connection. Only client message parse errors keep the connection open.

### Example Message Flow

1. `transcript.created` (server)

2. `Binary frame (audio)` (client)

3. `Binary frame (audio)` (client)

4. `transcript.partial` (server)

5. `Binary frame (audio)` (client)

6. `transcript.partial` (server)

7. `Binary frame (audio)` (client)

8. `transcript.partial` (server)

9. `audio.done` (client)

10. `transcript.done` (server)
