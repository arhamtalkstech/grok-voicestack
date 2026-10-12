# xAI speech docs

Markdown copies of xAI's public voice documentation from [docs.x.ai](https://docs.x.ai). They cover speech to speech (realtime voice agents), text to speech, speech to text, custom voices, ephemeral tokens, SIP phone calls, and the voice prompting guide. Use them offline, attach them to a coding agent, or upload them to a knowledge base.

Every docs.x.ai page has a markdown version at its URL plus `.md`. For example, `https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech` is available at `https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech.md`.

These pages are xAI's content, copied for reference. They are not covered by this repository's Apache-2.0 license (see [`../NOTICE`](../NOTICE)).

Fetched 2026-10-12. The live docs are the source of truth. To refresh this folder, run:

```bash
./fetch.sh
```

The script downloads each page, adds a source comment on the first line, and rewrites site-relative links (`](/developers/...)`) to absolute `https://docs.x.ai/...` links so they work outside the docs site. The page content is otherwise unchanged. To add a page, add a line to the `PAGES` list in `fetch.sh`.

## Guides

| File | What it covers | Source |
|---|---|---|
| [`guides/voice-overview.md`](guides/voice-overview.md) | All voice APIs at a glance, cookbook and partner integrations | [audio/voice](https://docs.x.ai/developers/model-capabilities/audio/voice) |
| [`guides/speech-to-speech.md`](guides/speech-to-speech.md) | Realtime voice agents over WebSocket: session config, audio formats, turn detection, tools, events | [audio/speech-to-speech](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech) |
| [`guides/speech-to-speech-sip.md`](guides/speech-to-speech-sip.md) | Phone calls over SIP: number registration, webhooks, accept, transfer, hang up | [speech-to-speech/sip](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech/sip) |
| [`guides/speech-to-speech-prompting-guide.md`](guides/speech-to-speech-prompting-guide.md) | How to write system prompts for voice agents | [speech-to-speech/prompting-guide](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech/prompting-guide) |
| [`guides/text-to-speech.md`](guides/text-to-speech.md) | TTS over REST and streaming WebSocket, voices, formats, speech tags | [audio/text-to-speech](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech) |
| [`guides/speech-to-text.md`](guides/speech-to-text.md) | Transcription over REST and streaming WebSocket | [audio/speech-to-text](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text) |
| [`guides/custom-voices.md`](guides/custom-voices.md) | Creating and using custom voices | [audio/custom-voices](https://docs.x.ai/developers/model-capabilities/audio/custom-voices) |
| [`guides/ephemeral-tokens.md`](guides/ephemeral-tokens.md) | Short-lived client secrets for browser and mobile apps | [audio/ephemeral-tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens) |

## Models

| File | Source |
|---|---|
| [`models/speech-to-speech.md`](models/speech-to-speech.md) | [models/speech-to-speech](https://docs.x.ai/developers/models/speech-to-speech) |
| [`models/text-to-speech.md`](models/text-to-speech.md) | [models/text-to-speech](https://docs.x.ai/developers/models/text-to-speech) |
| [`models/speech-to-text.md`](models/speech-to-text.md) | [models/speech-to-text](https://docs.x.ai/developers/models/speech-to-text) |

## API reference

| File | What it covers | Source |
|---|---|---|
| [`api-reference/voice.md`](api-reference/voice.md) | `/v1/realtime/client_secrets`, `/v2/phone-numbers`, the realtime WebSocket, call refer and hangup, `/v1/tts` and TTS streaming, `/v1/tts/voices`, `/v1/stt` and STT streaming, `/v1/custom-voices` | [inference/voice](https://docs.x.ai/developers/rest-api-reference/inference/voice) |
| [`api-reference/speech-to-text.md`](api-reference/speech-to-text.md) | `/v1/stt` and STT streaming | [inference/speech-to-text](https://docs.x.ai/developers/rest-api-reference/inference/speech-to-text) |
| [`specs/voice-realtime.ws.json`](specs/voice-realtime.ws.json) | Machine-readable schema of the realtime WebSocket messages | [voice-realtime.ws.json](https://docs.x.ai/voice-realtime.ws.json) |
| [`specs/tts-streaming.ws.json`](specs/tts-streaming.ws.json) | Machine-readable schema of the TTS streaming WebSocket | [tts-streaming.ws.json](https://docs.x.ai/tts-streaming.ws.json) |
| [`specs/stt-streaming.ws.json`](specs/stt-streaming.ws.json) | Machine-readable schema of the STT streaming WebSocket | [stt-streaming.ws.json](https://docs.x.ai/stt-streaming.ws.json) |

## Cookbook examples

| File | What it builds | Source |
|---|---|---|
| [`cookbook/voice-agent-web.md`](cookbook/voice-agent-web.md) | Browser voice agent over WebSocket | [voice-agent-web](https://docs.x.ai/cookbook/examples/voice-agent-web) |
| [`cookbook/voice-agent-webrtc.md`](cookbook/voice-agent-webrtc.md) | Browser voice agent over WebRTC | [voice-agent-webrtc](https://docs.x.ai/cookbook/examples/voice-agent-webrtc) |
| [`cookbook/voice-agent-phone.md`](cookbook/voice-agent-phone.md) | Phone voice agent | [voice-agent-phone](https://docs.x.ai/cookbook/examples/voice-agent-phone) |
| [`cookbook/voice-agent-mobile.md`](cookbook/voice-agent-mobile.md) | Mobile voice apps | [voice-agent-mobile](https://docs.x.ai/cookbook/examples/voice-agent-mobile) |
| [`cookbook/live-interpreter.md`](cookbook/live-interpreter.md) | Live speech translation | [live-interpreter](https://docs.x.ai/cookbook/examples/live-interpreter) |
| [`cookbook/meeting-to-action-items.md`](cookbook/meeting-to-action-items.md) | Meeting transcription to action items | [meeting-to-action-items](https://docs.x.ai/cookbook/examples/meeting-to-action-items) |
| [`cookbook/podcast-from-a-link.md`](cookbook/podcast-from-a-link.md) | Podcast audio from a web page | [podcast-from-a-link](https://docs.x.ai/cookbook/examples/podcast-from-a-link) |
| [`cookbook/video-dubbing.md`](cookbook/video-dubbing.md) | Dubbing a video into another language | [video-dubbing](https://docs.x.ai/cookbook/examples/video-dubbing) |

## Related docs

These pages are general to the xAI API and apply to voice agents: tools you can give a realtime session, Collections for `file_search`, regions, rate limits, and pricing.

| File | Source |
|---|---|
| [`related/tools-overview.md`](related/tools-overview.md) | [tools/overview](https://docs.x.ai/developers/tools/overview) |
| [`related/function-calling.md`](related/function-calling.md) | [tools/function-calling](https://docs.x.ai/developers/tools/function-calling) |
| [`related/web-search.md`](related/web-search.md) | [tools/web-search](https://docs.x.ai/developers/tools/web-search) |
| [`related/x-search.md`](related/x-search.md) | [tools/x-search](https://docs.x.ai/developers/tools/x-search) |
| [`related/collections-search.md`](related/collections-search.md) | [tools/collections-search](https://docs.x.ai/developers/tools/collections-search) |
| [`related/remote-mcp.md`](related/remote-mcp.md) | [tools/remote-mcp](https://docs.x.ai/developers/tools/remote-mcp) |
| [`related/collections.md`](related/collections.md) | [files/collections](https://docs.x.ai/developers/files/collections) |
| [`related/collections-api.md`](related/collections-api.md) | [files/collections/api](https://docs.x.ai/developers/files/collections/api) |
| [`related/regional-endpoints.md`](related/regional-endpoints.md) | [advanced-api-usage/regions](https://docs.x.ai/developers/advanced-api-usage/regions) |
| [`related/rate-limits.md`](related/rate-limits.md) | [rate-limits](https://docs.x.ai/developers/rate-limits) |
| [`related/pricing.md`](related/pricing.md) | [pricing](https://docs.x.ai/developers/pricing) |

## Finding more pages

The full docs index is at [`https://docs.x.ai/llms.txt`](https://docs.x.ai/llms.txt), and every page is listed in [`https://docs.x.ai/sitemap.xml`](https://docs.x.ai/sitemap.xml). Voice Stack's own notes on behaviors the docs do not cover are in [`../docs/xai-api-notes.md`](../docs/xai-api-notes.md).
