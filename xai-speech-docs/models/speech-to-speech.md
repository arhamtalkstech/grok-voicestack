<!-- Source: https://docs.x.ai/developers/models/speech-to-speech (markdown: https://docs.x.ai/developers/models/speech-to-speech.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Models

# Speech to Speech

The Speech to Speech API enables real-time voice conversations over WebSocket, billed per minute plus a flat fee per text input message. Supports function calling with web search, X search, collections, MCP, and custom functions.

## At a glance

| | Details |
|---|---|
| **Modalities** | Text, Audio → Text, Audio |
| **Audio pricing** |  / minute or  / hour |
| **Text Input pricing** |  / message |
| **Region** | us-east-1 |

## Pricing

The Speech to Speech API charges based on duration and text events sent without audio.

| | Details |
|---|---|
| **Audio** |  / minute or  / hour |
| **Text Input** |  per `conversation.item.create` event |

> [!NOTE]
>
> Sessions using the default `server_vad` turn detection are billed for session duration. Push-to-talk sessions are billed only for audio sent and received.

### What counts as a text input message

Every `conversation.item.create` event you send from the client is billed at , with two exceptions:

* `function_call_output` items (server-requested tool results) are not billed.
* Items whose content is `input_audio` or `audio` are billed by the audio meter instead.

`response.create` is not billed as a text input. It only asks the model to produce the next turn; any audio the model generates in that turn is billed under the audio meter above.

## Rate Limits

| | Details |
|---|---:|
| **Concurrent sessions** |  per team |
| **Max session duration** | 120 minutes |

## Capabilities

* Function calling
* Web search
* X search
* Collections search
* Remote MCP tools

## Availability

| | Details |
|---|---|
| **Cluster** | us-east-1 |

## Documentation

* [Speech to Speech Guide](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech) — Getting started with real-time voice conversations
* [API Reference](https://docs.x.ai/developers/rest-api-reference/inference/voice) — WebSocket endpoint reference
* [Pricing](https://docs.x.ai/developers/pricing#voice-api-pricing) — Full pricing overview
