<!-- Source: https://docs.x.ai/developers/models/speech-to-text (markdown: https://docs.x.ai/developers/models/speech-to-text.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Models

# Speech to Text

The Speech to Text API transcribes audio into text. The default model is `grok-voice-transcribe-2.0`. Use the REST endpoint for file-based batch transcription, or the streaming endpoint for real-time low-latency transcription.

## At a glance

| | Details |
|---|---|
| **Modalities** | Audio → Text |
| **REST pricing** |  / hr |
| **Streaming pricing** |  / hr |
| **Region** | us-east-1 |

## Pricing

| | Details |
|---|---:|
| **REST (per hour)** |  / hr |
| **Streaming (per hour)** |  / hr |

## Rate Limits

| | REST | Streaming |
|---|---:|---:|
| **RPS** (Requests per second) |  |  |
| **Concurrent sessions** | — |  per team |

## Capabilities

* REST and streaming transcription
* Multiple audio formats (WAV, MP3, WebM, OGG, M4A)
* [38+ languages](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text#supported-languages) with automatic language detection
* Real-time interim results (streaming)
* Keyterm prompting for domain-specific vocabulary
* Smart Turn end-of-turn detection (streaming) — ML-based prediction of whether the speaker has finished their thought

## Availability

| | Details |
|---|---|
| **Cluster** | us-east-1 |

## Documentation

* [Speech to Text Guide](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text) — Getting started with speech to text
* [Voice Overview](https://docs.x.ai/developers/model-capabilities/audio/voice) — Overview of all voice capabilities
* [Pricing](https://docs.x.ai/developers/pricing#voice-api-pricing) — Full pricing overview
