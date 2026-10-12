<!-- Source: https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens (markdown: https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Model Capabilities

# Ephemeral Tokens

Ephemeral tokens provide secure, short-lived authentication for client-side applications. Use them when connecting to the [Speech to Speech API](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech) from browsers or mobile apps to avoid exposing your API key.

## How It Works

1. Your **server** requests an ephemeral token from SpaceXAI using your API key
2. Your server passes the ephemeral token to the **client**
3. The **client** uses the ephemeral token to authenticate the WebSocket connection
4. The token expires automatically after the configured duration

> [!WARNING]
>
> **Never expose your API key in client-side code.** Always use ephemeral tokens for browser and mobile applications.

## Creating Ephemeral Tokens

You need to set up a server endpoint to fetch the ephemeral token from SpaceXAI. The ephemeral token gives the holder scoped access to resources.

**Endpoint:** `POST https://api.x.ai/v1/realtime/client_secrets`

```bash
curl --url https://api.x.ai/v1/realtime/client_secrets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  --data '{
    "expires_after": {
      "seconds": 300
    }
  }'

# Note: Does not support "session" or "expires_after.anchor" fields
```

```pythonWithoutSDK
# Example ephemeral token endpoint with FastAPI

import os
import httpx
from fastapi import FastAPI

app = FastAPI()
SESSION_REQUEST_URL = "https://api.x.ai/v1/realtime/client_secrets"
XAI_API_KEY = os.getenv("XAI_API_KEY")

@app.post("/session")
async def get_ephemeral_token():
    # Send request to xAI endpoint to retrieve the ephemeral token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=SESSION_REQUEST_URL,
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"expires_after": {"seconds": 300}},
        )

    # Return the response body from xAI with ephemeral token
    return response.json()
```

```javascriptWithoutSDK
// Example ephemeral token endpoint with Express

import express from 'express';

const app = express();
const SESSION_REQUEST_URL = "https://api.x.ai/v1/realtime/client_secrets";

app.use(express.json());

app.post("/session", async (req, res) => {
  const r = await fetch(SESSION_REQUEST_URL, {
    method: "POST",
    headers: {
      Authorization: \`Bearer \${process.env.XAI_API_KEY}\`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      expires_after: { seconds: 300 }
    }),
  });

  const data = await r.json();
  res.json(data);
});

app.listen(8081);
```

## Using Ephemeral Tokens

The ephemeral token can be used in the same fashion as an API key:

```pythonWithoutSDK
import os
import websockets

base_url = "wss://api.x.ai/v1/realtime?model=grok-voice-latest"

# Connect with API key in Authorization header
async with websockets.connect(
    uri=base_url,
    ssl=True,
    additional_headers={"Authorization": f"Bearer {OBTAINED_EPHEMERAL_TOKEN}"}
) as websocket:
    # WebSocket connection is now authenticated
    pass
```

```javascriptWithoutSDK
import WebSocket from "ws";

const baseUrl = "wss://api.x.ai/v1/realtime?model=grok-voice-latest";

// Connect with API key in Authorization header
const ws = new WebSocket(baseUrl, {
  headers: {
    Authorization: "Bearer " + OBTAINED_EPHEMERAL_TOKEN,
    "Content-Type": "application/json",
  },
});

ws.on("open", () => {
  console.log("Connected with ephemeral token authentication");
});
```

### Browser WebSocket Authentication

If you need to send the ephemeral token from the browser, you can add the ephemeral token with a prefix `xai-client-secret.` to the `sec-websocket-protocol` header:

```javascriptWithoutSDK
new WebSocket("wss://api.x.ai/v1/realtime", [\`xai-client-secret.\${OBTAINED_EPHEMERAL_TOKEN}\`]);
```
