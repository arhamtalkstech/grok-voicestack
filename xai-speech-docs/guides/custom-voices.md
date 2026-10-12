<!-- Source: https://docs.x.ai/developers/model-capabilities/audio/custom-voices (markdown: https://docs.x.ai/developers/model-capabilities/audio/custom-voices.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Model Capabilities

# Custom Voices

Clone a voice from a short reference clip and use it anywhere a built-in voice works. Upload an audio sample and immediately start using it in our TTS and Speech to Speech APIs.

> [!WARNING]
>
> Custom Voices is currently only available in the **United States**, with the exception of **Illinois**.

## How to Use Custom Voices

After creating a voice in the [console](https://console.x.ai/team/default/voice/voice-library?campaign=voice-docs-custom-voices\&utm_source=docs\&utm_medium=referral\&utm_campaign=developers-model-capabilities-audio-custom-voices\&utm_content=voice-library), click the three-dot menu on the voice card and select **Copy Voice ID**. If you created a custom voice via the API (Enterprise only), the `voice_id` is returned in the response.

Custom voices are interchangeable with built-in voices across all voice APIs. Pass your `voice_id` to any of:

* `POST /v1/tts`
* `wss://api.x.ai/v1/tts`
* `wss://api.x.ai/v1/realtime`

Built-in voices remain available through `GET /v1/tts/voices`. Custom voices are returned by `GET /v1/custom-voices` only — they will not appear in the built-in voice list. Your custom voices are scoped to your team and are never available to other users.

## Recording Your Reference Audio

Create a custom voice by cloning a reference clip up to 120 seconds long. For best results:

* **Record in a quiet setting**, ideally with a high-quality microphone.
* **Read naturally.** If it sounds like you're reading a script, the resulting voice will match this behavior.
* **Longer is better.** Clips under 30 seconds may lack detail. Aim for 90–120 seconds for the best results.
* **Speak expressively.** The resulting voice will match the expressiveness of your recording.

### What to record

The model picks up not just the timbre but the **delivery patterns** of the reference clip. For best results, match the recording to the content you intend to generate:

* **Customer support** — Record realistic support exchanges including greetings, holds, troubleshooting steps, and sign-offs.
* **Audiobook narration** — Read a few paragraphs of prose with the pacing and inflection intended for the final output.
* **Conversational assistant** — Record natural, unscripted speech such as explaining a topic to a friend.
* **News or documentary** — Read a short article in a natural broadcast voice.

A recording that reflects your intended use case will produce better results than a polished but unrelated sample.

### Recording setup

* **Microphone.** A studio condenser or quality USB microphone is recommended. Phone earbuds are usable but introduce noticeable noise.
* **Pop filter.** Recommended. Plosive sounds (`p`, `b`) are reproduced as audible thumps without one.
* **Room treatment.** Record in a small, soft-furnished room. Hard-walled rooms produce echo and reverb that will be reproduced in the resulting voice.
* **Single speaker.** The recording should contain only one voice with no background music or sound effects.
* **Background noise.** Silence the room. Turn off HVAC, fans, and notifications. Background noise will be cloned along with the voice.

## Create a Custom Voice

Get started in the console — create up to 30 custom voices for free and use them immediately across all voice APIs.

[Clone Voice in Console](https://console.x.ai/team/default/voice/voice-library?campaign=voice-docs-custom-voices\&utm_source=docs\&utm_medium=referral\&utm_campaign=developers-model-capabilities-audio-custom-voices\&utm_content=voice-library)

### API Quick Start

> [!WARNING]
>
> The `POST /v1/custom-voices` endpoint is gated to teams on an Enterprise plan. **** to enable API access.

Create a custom voice from a reference audio file, then synthesize speech with it:

```bash
# 1. Create the voice from a reference clip (max 120s).
CREATE_RESPONSE=$(curl -s -X POST https://api.x.ai/v1/custom-voices \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F "name=Friendly Narrator" \
  -F "language=en" \
  -F "gender=female" \
  -F "tone=warm" \
  -F "use_case=narration" \
  -F "file=@reference.wav;type=audio/wav")

echo "$CREATE_RESPONSE"
# {"voice_id":"abc123xy","name":"Friendly Narrator",...}

# Extract the voice_id from the response (requires jq).
VOICE_ID=$(echo "$CREATE_RESPONSE" | jq -r '.voice_id')

# 2. Use the new voice for TTS.
curl -X POST https://api.x.ai/v1/tts \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Hello! This audio was synthesized using my custom voice.\",
    \"voice_id\": \"$VOICE_ID\",
    \"language\": \"en\"
  }" \
  --output hello.mp3
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

# 1. Create the voice.
with open("reference.wav", "rb") as f:
    create = requests.post(
        "https://api.x.ai/v1/custom-voices",
        headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
        files={"file": ("reference.wav", f, "audio/wav")},
        data={
            "name": "Friendly Narrator",
            "language": "en",
            "gender": "female",
            "tone": "warm",
            "use_case": "narration",
        },
    )
create.raise_for_status()
voice_id = create.json()["voice_id"]

# 2. Synthesize speech with it.
speech = requests.post(
    "https://api.x.ai/v1/tts",
    headers={
        "Authorization": f"Bearer {os.environ['XAI_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "text": "Hello! This audio was synthesized using my custom voice.",
        "voice_id": voice_id,
        "language": "en",
    },
)
speech.raise_for_status()
with open("hello.mp3", "wb") as f:
    f.write(speech.content)
```

```javascript customLanguage="javascriptWithoutSDK"
import fs from "fs";

// 1. Create the voice.
const form = new FormData();
form.append("file", new Blob([fs.readFileSync("reference.wav")]), "reference.wav");
form.append("name", "Friendly Narrator");
form.append("language", "en");
form.append("gender", "female");
form.append("tone", "warm");
form.append("use_case", "narration");

const createResp = await fetch("https://api.x.ai/v1/custom-voices", {
  method: "POST",
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
  body: form,
});
if (!createResp.ok) throw new Error(`Create error ${createResp.status}`);
const { voice_id } = await createResp.json();

// 2. Synthesize speech with it.
const speech = await fetch("https://api.x.ai/v1/tts", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.XAI_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    text: "Hello! This audio was synthesized using my custom voice.",
    voice_id,
    language: "en",
  }),
});
const buffer = Buffer.from(await speech.arrayBuffer());
fs.writeFileSync("hello.mp3", buffer);
```

```swift
import Foundation

let apiKey = ProcessInfo.processInfo.environment["XAI_API_KEY"]!

// 1. Create the voice.
let boundary = UUID().uuidString
var body = Data()

func appendField(_ name: String, _ value: String) {
    body.append("--\(boundary)\r\n".data(using: .utf8)!)
    body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
    body.append("\(value)\r\n".data(using: .utf8)!)
}

appendField("name", "Friendly Narrator")
appendField("language", "en")
appendField("gender", "female")
appendField("tone", "warm")
appendField("use_case", "narration")

let audioData = try Data(contentsOf: URL(fileURLWithPath: "reference.wav"))
body.append("--\(boundary)\r\n".data(using: .utf8)!)
body.append("Content-Disposition: form-data; name=\"file\"; filename=\"reference.wav\"\r\n".data(using: .utf8)!)
body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
body.append(audioData)
body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

var request = URLRequest(url: URL(string: "https://api.x.ai/v1/custom-voices")!)
request.httpMethod = "POST"
request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
request.httpBody = body

let (data, _) = try await URLSession.shared.upload(for: request, from: body)
let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
let voiceId = json["voice_id"] as! String

// 2. Synthesize speech with it.
var ttsRequest = URLRequest(url: URL(string: "https://api.x.ai/v1/tts")!)
ttsRequest.httpMethod = "POST"
ttsRequest.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
ttsRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
ttsRequest.httpBody = try JSONSerialization.data(withJSONObject: [
    "text": "Hello! This audio was synthesized using my custom voice.",
    "voice_id": voiceId,
    "language": "en",
])

let (audioBytes, _) = try await URLSession.shared.data(for: ttsRequest)
try audioBytes.write(to: URL(fileURLWithPath: "hello.mp3"))
```

## Endpoints

All endpoints sit under `https://api.x.ai/v1/custom-voices` and authenticate with a Bearer API key.

### Create a custom voice

`POST /v1/custom-voices` with `multipart/form-data`. Only `file` is required.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | yes | Reference audio. Max 120 s. |
| `name` | string | | Display name. |
| `description` | string | | Free-text description. |
| `gender` | string | | `male`, `female`, or `neutral`. |
| `accent` | string | | Free text (e.g. `British`, `American`). |
| `age` | string | | `young`, `middle-aged`, or `old`. |
| `language` | string | | ISO 639 (`en`) or BCP-47-style (`en-US`, `zh-CN`). Region must be uppercase. |
| `use_case` | string | | `conversational`, `narration`, `characters`, `educational`, `advertisement`, `social_media`, `entertainment`. |
| `tone` | string | | `warm`, `casual`, `professional`, `friendly`, `authoritative`, `expressive`, `calm`. |

The following formats and settings are recommended for the uploaded reference file:

| Setting | Recommendation |
|---------|----------------|
| **Codec** | `.wav` (uncompressed PCM) is recommended. MP3, FLAC, OGG, Opus, M4A, AAC, MKV, and MP4 are also accepted, but lossy formats may introduce compression artifacts that are reproduced in the resulting voice. |
| **Sample rate** | **24 kHz** recommended. Higher rates (44.1 kHz, 48 kHz) are downsampled server-side. Lower rates result in reduced fidelity. |
| **Bit depth** | **16-bit PCM** is sufficient. 24-bit is also supported. |
| **Channels** | **Mono** recommended. Stereo files are downmixed automatically, but recording in mono avoids potential phase artifacts. |

#### Length

* **No minimum, 120s maximum.** Clips of any length up to 120 seconds are accepted; longer clips are rejected with `400`.
* **90+ seconds recommended.** Longer clips capture more prosody and intonation variety, producing a more natural and expressive voice.

A successful create returns `201` with the new voice object:

```json
{
  "voice_id": "nlbqfwie",
  "name": "Friendly Narrator",
  "description": "Warm, conversational tone for narration.",
  "gender": "female",
  "accent": "American",
  "age": "young",
  "language": "en",
  "use_case": "narration",
  "tone": "warm",
  "created_at": "2026-04-26T18:56:34.872993+00:00"
}
```

`voice_id` is an 8-character lowercase alphanumeric identifier.

### List custom voices

`GET /v1/custom-voices` returns all voices owned by your team, paginated.

| Query parameter | Default | Description |
|-----------------|---------|-------------|
| `limit` | `100` | Page size, 1-1000. |
| `pagination_token` | | Token from the previous response. Omit on the first page. |

```bash
curl -s "https://api.x.ai/v1/custom-voices?limit=50" \
  -H "Authorization: Bearer $XAI_API_KEY"
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

response = requests.get(
    "https://api.x.ai/v1/custom-voices",
    headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
    params={"limit": 50},
)
for voice in response.json()["voices"]:
    print(f"{voice['voice_id']:10s}  {voice.get('name')}")
```

```javascript customLanguage="javascriptWithoutSDK"
const response = await fetch(
  "https://api.x.ai/v1/custom-voices?limit=50",
  { headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` } },
);
const { voices } = await response.json();
voices.forEach((v) => console.log(`${v.voice_id}  ${v.name}`));
```

Response:

```json
{
  "voices": [
    {
      "voice_id": "nlbqfwie",
      "name": "Friendly Narrator",
      "description": "Warm, conversational tone for narration.",
      "gender": "female",
      "accent": "American",
      "age": "young",
      "language": "en",
      "use_case": "narration",
      "tone": "warm",
      "created_at": "2026-04-26T18:56:34.872993+00:00"
    }
  ],
  "pagination_token": null
}
```

### Get a custom voice

`GET /v1/custom-voices/{voice_id}` returns the metadata for a single voice. Returns `404` for unknown ids or for voices owned by another team.

Response body matches the voice object format shown in [Create](#create-a-custom-voice).

### Update metadata

`PATCH /v1/custom-voices/{voice_id}` with a JSON body. All fields are optional and follow these rules:

* **Field omitted** — no change.
* **Field set to `null`** — clears the value.
* **Field set to a non-empty string** — updates the value.
* **Field set to `""`** — rejected with `400`.

This endpoint never changes the underlying audio. To re-record, delete the voice and create a new one.

```bash
curl -X PATCH "https://api.x.ai/v1/custom-voices/nlbqfwie" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated after a tuning pass.", "tone": "calm"}'
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

response = requests.patch(
    "https://api.x.ai/v1/custom-voices/nlbqfwie",
    headers={
        "Authorization": f"Bearer {os.environ['XAI_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={"description": "Updated after a tuning pass.", "tone": "calm"},
)
print(response.json())
```

```javascript customLanguage="javascriptWithoutSDK"
const response = await fetch(
  "https://api.x.ai/v1/custom-voices/nlbqfwie",
  {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${process.env.XAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      description: "Updated after a tuning pass.",
      tone: "calm",
    }),
  },
);
if (!response.ok) throw new Error(`Update error ${response.status}: ${await response.text()}`);
console.log(await response.json());
```

Returns the full updated voice object:

```json
{
  "voice_id": "nlbqfwie",
  "name": "Friendly Narrator",
  "description": "Updated after a tuning pass.",
  "gender": "female",
  "accent": "American",
  "age": "young",
  "language": "en",
  "use_case": "narration",
  "tone": "calm",
  "created_at": "2026-04-26T18:56:34.872993+00:00"
}
```

### Download the reference audio

`GET /v1/custom-voices/{voice_id}/audio` streams the original reference file with the appropriate `Content-Type` header (e.g. `audio/wav`, `audio/mpeg`).

### Delete a custom voice

`DELETE /v1/custom-voices/{voice_id}` removes the voice and its underlying audio.

```bash
curl -X DELETE "https://api.x.ai/v1/custom-voices/nlbqfwie" \
  -H "Authorization: Bearer $XAI_API_KEY"
```

```python customLanguage="pythonWithoutSDK"
import os
import requests

requests.delete(
    "https://api.x.ai/v1/custom-voices/nlbqfwie",
    headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
)
```

```javascript customLanguage="javascriptWithoutSDK"
await fetch("https://api.x.ai/v1/custom-voices/nlbqfwie", {
  method: "DELETE",
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
});
```

The response is `{"deleted": true}`. After deletion, subsequent requests for the same `voice_id` return `404` and any TTS / Speech to Speech calls referencing it will fail with an unknown-voice error.

## Using a Custom Voice

Once created, a custom `voice_id` works wherever a built-in `voice_id` works.

### REST TTS

```bash
curl -X POST https://api.x.ai/v1/tts \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Welcome back. How can I help today?",
    "voice_id": "nlbqfwie",
    "language": "en"
  }' \
  --output welcome.mp3
```

### Streaming TTS WebSocket

Pass the custom voice as the `voice` query parameter when opening the connection. See [Text to Speech - Streaming](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech#streaming-tts-websocket) for the full event protocol.

**Prerequisite:** Install the WebSocket client library — `pip install websockets` (Python) or `npm install ws` (Node.js).

```python customLanguage="pythonWithoutSDK"
import asyncio
import base64
import json
import os
import websockets

async def stream_with_custom_voice(voice_id: str):
    uri = f"wss://api.x.ai/v1/tts?language=en&voice={voice_id}&codec=mp3"
    async with websockets.connect(
        uri,
        additional_headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
    ) as ws:
        await ws.send(json.dumps({"type": "text.delta", "delta": "Streaming with my custom voice."}))
        await ws.send(json.dumps({"type": "text.done"}))
        audio = bytearray()
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "audio.delta":
                audio.extend(base64.b64decode(event["delta"]))
            elif event["type"] == "audio.done":
                break
        with open("stream.mp3", "wb") as f:
            f.write(audio)

asyncio.run(stream_with_custom_voice("nlbqfwie"))
```

### Speech to Speech API

Set `voice` in the `session.update` message. See the [Speech to Speech API docs](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech) for the full session lifecycle.

```python customLanguage="pythonWithoutSDK"
import asyncio
import json
import os
import websockets

async def realtime_with_custom_voice(voice_id: str):
    async with websockets.connect(
        "wss://api.x.ai/v1/realtime",
        additional_headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
    ) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": voice_id,
                "instructions": "You are a helpful assistant.",
                "turn_detection": {"type": "server_vad"},
            },
        }))
        # ... continue with the standard realtime event loop ...

asyncio.run(realtime_with_custom_voice("nlbqfwie"))
```

## Limits

| | Value |
|---|---:|
| Reference audio max duration | 120 seconds |
| Custom voices per team | **30** |
| Voice ID length | 8 characters, lowercase alphanumeric |

### Need more than 30 voices?

The default limit is 30 custom voices per team. If you need more, contact us to discuss higher limits.

[Request more custom voices](https://x.ai/contact-sales)

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `201` | Voice created | Save `voice_id` and start using it. |
| `200` | Successful read / update / delete | - |
| `400` | Bad request | Check: audio under 120 s; label values are within the allowed enums; PATCH does not contain empty strings. Also returned when the team's 30-voice limit is reached — delete an existing voice or [request more](https://x.ai/contact-sales). |
| `401` | Unauthorized | API key is missing or invalid. |
| `403` | Custom voices not enabled for this team, or `POST /v1/custom-voices` was called without an Enterprise contract | Create voices in the [console playground](https://console.x.ai/team/default/voice/voice-library?campaign=voice-docs-custom-voices\&utm_source=docs\&utm_medium=referral\&utm_campaign=developers-model-capabilities-audio-custom-voices\&utm_content=voice-library), or [contact sales](https://x.ai/contact-sales) to enable the create API. |
| `404` | Voice not found | The id does not exist or is owned by another team. |
| `500` | Server error | Retry with exponential backoff. |
