<!-- Source: https://docs.x.ai/developers/model-capabilities/audio/voice (markdown: https://docs.x.ai/developers/model-capabilities/audio/voice.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Model Capabilities

# Voice Overview

The xAI Voice APIs offer a range of powerful voice capabilities, all powered by Grok, with enterprise-grade reliability and sub-second latency.

## Speech to Speech

Build real-time, speech-to-speech voice agents over WebSockets, with low-latency turn-taking and tool use. For client-side apps, use [Ephemeral Tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens) to connect securely without exposing your API key.

```python customLanguage="pythonWithoutSDK"
import asyncio
import json
import os
import websockets

async def voice_agent():
    async with websockets.connect(
        "wss://api.x.ai/v1/realtime?model=grok-voice-latest",
        additional_headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"}
    ) as ws:
        # Configure voice and enable tools
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": "eve",
                "instructions": "You are a helpful customer support agent.",
                "turn_detection": {"type": "server_vad"},
                "tools": [{"type": "web_search"}]
            }
        }))
        
        # Stream audio and receive responses
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "response.output_audio.delta":
                # Play audio: base64.b64decode(event["delta"])
                pass

asyncio.run(voice_agent())
```

```javascript customLanguage="javascriptWithoutSDK"
import WebSocket from "ws";

const ws = new WebSocket("wss://api.x.ai/v1/realtime?model=grok-voice-latest", {
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
});

ws.on("open", () => {
  // Configure voice and enable tools
  ws.send(JSON.stringify({
    type: "session.update",
    session: {
      voice: "eve",
      instructions: "You are a helpful customer support agent.",
      turn_detection: { type: "server_vad" },
      tools: [{ type: "web_search" }]
    }
  }));
});

ws.on("message", (data) => {
  const event = JSON.parse(data);
  if (event.type === "response.output_audio.delta") {
    // Play audio: Buffer.from(event.delta, "base64")
  }
});

```

**Demo Apps:** [Web Agent](https://github.com/xai-org/xai-cookbook/tree/main/examples/voice-agent-web) · [Twilio Phone Agent](https://github.com/xai-org/xai-cookbook/tree/main/examples/voice-agent-phone) · [WebRTC Agent](https://github.com/xai-org/xai-cookbook/tree/main/examples/voice-agent-webrtc) · [iOS Tester App](https://github.com/xai-org/xai-cookbook/tree/main/examples/voice-agent-mobile/swift)

## Text to Speech

Convert text to spoken audio with a large roster of expressive voices. Inline speech tags (laughter, whispers, pauses) and output formats from high-fidelity MP3 to telephony μ-law. Unary requests or WebSocket streaming.

```bash
curl -X POST https://api.x.ai/v1/tts \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Welcome to xAI. How can I help you today?",
    "voice_id": "eve",
    "language": "en"
  }' \
  --output welcome.mp3
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

response = requests.post(
    "https://api.x.ai/v1/tts",
    headers={
        "Authorization": f"Bearer {os.environ['XAI_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "text": "Welcome to xAI. How can I help you today?",
        "voice_id": "eve",
        "language": "en",
    },
)

with open("welcome.mp3", "wb") as f:
    f.write(response.content)
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";

const response = await fetch("https://api.x.ai/v1/tts", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.XAI_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    text: "Welcome to xAI. How can I help you today?",
    voice_id: "eve",
    language: "en",
  }),
});

const buffer = Buffer.from(await response.arrayBuffer());
fs.writeFileSync("welcome.mp3", buffer);
```

**Real World Examples:** [LiveKit](https://docs.livekit.io/agents/integrations/xai/) · [Pipecat](https://docs.pipecat.ai/server/services/s2s/grok)

## Speech to Text

Transcribe audio files in a single call or stream over WebSocket. The default is `grok-voice-transcribe-2.0`. 12 audio formats, word-level timestamps, multichannel, speaker diarization, Smart Turn end-of-turn detection, and 38+ languages.

```bash
curl -X POST https://api.x.ai/v1/stt \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F model=grok-voice-transcribe-2.0 \
  -F file=@recording.mp3
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

response = requests.post(
    "https://api.x.ai/v1/stt",
    headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
    files={"file": ("recording.mp3", open("recording.mp3", "rb"), "audio/mpeg")},
    data={"model": "grok-voice-transcribe-2.0"},
)

print(response.json()["text"])
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";

const formData = new FormData();
formData.append("model", "grok-voice-transcribe-2.0");
formData.append("file", new Blob([fs.readFileSync("recording.mp3")]), "recording.mp3");

const response = await fetch("https://api.x.ai/v1/stt", {
  method: "POST",
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
  body: formData,
});

const result = await response.json();
console.log(result.text);
```

**Real World Examples:** [Voximplant](https://voximplant.com/products/grok-client)

## Quick Start: Custom Voices

Clone a voice from a short reference clip, then use the resulting `voice_id` anywhere a built-in voice works:

```bash
# 1. Create a custom voice from a reference audio clip (max 120s).
curl -X POST https://api.x.ai/v1/custom-voices \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F "name=Friendly Narrator" \
  -F "language=en" \
  -F "file=@reference.wav;type=audio/wav"

# Response: { "voice_id": "nlbqfwie", ... }

# 2. Use the custom voice for TTS.
curl -X POST https://api.x.ai/v1/tts \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! This is my custom voice.",
    "voice_id": "nlbqfwie",
    "language": "en"
  }' \
  --output custom.mp3
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

# 1. Create a custom voice from a reference audio clip (max 120s).
with open("reference.wav", "rb") as f:
    create = requests.post(
        "https://api.x.ai/v1/custom-voices",
        headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
        files={"file": ("reference.wav", f, "audio/wav")},
        data={"name": "Friendly Narrator", "language": "en"},
    )
voice_id = create.json()["voice_id"]

# 2. Use the custom voice for TTS.
speech = requests.post(
    "https://api.x.ai/v1/tts",
    headers={
        "Authorization": f"Bearer {os.environ['XAI_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "text": "Hello! This is my custom voice.",
        "voice_id": voice_id,
        "language": "en",
    },
)
with open("custom.mp3", "wb") as f:
    f.write(speech.content)
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";

// 1. Create a custom voice from a reference audio clip (max 120s).
const form = new FormData();
form.append("file", new Blob([fs.readFileSync("reference.wav")]), "reference.wav");
form.append("name", "Friendly Narrator");
form.append("language", "en");

const create = await fetch("https://api.x.ai/v1/custom-voices", {
  method: "POST",
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
  body: form,
});
const { voice_id } = await create.json();

// 2. Use the custom voice for TTS.
const speech = await fetch("https://api.x.ai/v1/tts", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.XAI_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    text: "Hello! This is my custom voice.",
    voice_id,
    language: "en",
  }),
});
fs.writeFileSync("custom.mp3", Buffer.from(await speech.arrayBuffer()));
```

The custom `voice_id` also works with the streaming TTS WebSocket and the Speech to Speech realtime API. See the [Custom Voices guide](https://docs.x.ai/developers/model-capabilities/audio/custom-voices) for the full API.

## Voices

When using the Speech to Speech API or Text to Speech, you can choose from the full set of built-in voices. Each has its own personality and tone, and all of them can speak every supported language. Pick the one that best fits your application (`eve` is the default):

### Enterprise Compliance & Security

The xAI Voice APIs are built for production workloads with strict security and compliance requirements. All audio data is processed in real time and never stored or used for training.

* **SOC 2 Type II** — Audited controls for security, availability, and confidentiality

* **HIPAA Eligible** — BAA available for healthcare applications handling PHI

* **GDPR Compliant** — Data processing agreements and EU data residency options

* **Data Residency** — Regional processing for compliance requirements

* **High Availability** — Multi-region infrastructure with custom SLAs for enterprise workloads

* **SSO & RBAC** — SAML SSO, role-based access, and audit logging
