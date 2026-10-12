# Telephony (SIP)

Voice Stack answers phone numbers you own on any SIP trunk. xAI terminates SIP and bridges the audio. Voice Stack receives a signed webhook per call, joins the call's realtime session, and runs the conversation with the same runtime as previews.

> **Testing status:** number registration and deletion through xAI, webhook verification with a real signing secret, routing, contact lookup, call setup, and the `refer`/`hangup` endpoints have all been exercised against the live API. A live phone call through a carrier has not been placed.

## Requirements

- `PUBLIC_BASE_URL`: an HTTPS URL xAI can reach. The webhook path is `/webhooks/xai/call-incoming`.
- A server-side key: saved in Settings or `XAI_API_KEY`. Ephemeral tokens cannot join `call_id` sessions, and session-only browser keys are not available when a call arrives.
- A process with `ROLE=all` or `ROLE=telephony`, kept running for the length of every call.

## Register a number

Go to Telephony → **Add number** → *Register with xAI now*. This calls:

```http
POST https://api.x.ai/v2/phone-numbers
{"origin": "byo_trunk", "name": "Support line", "phone_number": "+18005550199",
 "sip_auth": {"allowed_addresses": ["203.0.113.0/24"], "auth_username": "…", "auth_password": "…"},
 "webhook": {"url": "https://<PUBLIC_BASE_URL>/webhooks/xai/call-incoming"}}
```

The response's `dispatch_signing_secret` is returned once. Voice Stack encrypts and stores it. If a number was registered elsewhere, choose *Attach an existing registration* and paste its signing secret.

Then point your carrier at the SIP URI shown on the number card, `sip:+18005550199@sip.voice.x.ai;transport=tls`. The API response's `sip_host` was an IP and port (`…:5060`) in testing. The card shows it for reference, but follows xAI's SIP guide for the URI. The card shows the steps for Twilio, Telnyx, Plivo, or a PBX. If you set `allowed_addresses`, include your carrier's SIP signaling ranges.

## What happens on a call

1. xAI posts `realtime.call.incoming` with `call_id` and the SIP `From`/`To` headers.
2. Voice Stack verifies the Standard Webhooks signature (HMAC-SHA256 over `id.timestamp.body`, 5-minute tolerance) against the dialed number's secret. It drops duplicates by `webhook-id`. It replies `200` immediately and starts the call in the background.
3. The call worker finds or creates the contact for `From`, creates the conversation, and loads the landscape: published versions by default, drafts if the number is set that way. It opens `wss://api.x.ai/v1/realtime?call_id=…` with the API key.
4. The entry agent's `session.update` is sent. Then the number's disclosure plays verbatim and uninterruptible, if set, followed by the greeting.
5. Handoffs, tools, memory, and summaries work exactly as in previews. Keypad digits arrive as `input_audio_buffer.dtmf_event_received`. They are stored as turns and shown in the call monitor. xAI also passes them to the model as text.
6. `transfer_call` uses SIP REFER. `end_call` hangs up after the goodbye plays (`POST /v1/realtime/calls/{id}/hangup`). If the caller hangs up, the conversation closes.

Playback timing on SIP comes from `output_audio_buffer.started`/`stopped`. If those events do not arrive, the controller estimates the length of the agent's line from the transcript before sending the next `response.create`.

## Test without a carrier

```bash
uv run voicestack sip simulate --to +18005550199 --from +14155550100 --url http://localhost:8000
```

This posts a correctly signed webhook using the stored secret for `--to`. It exercises signature checks, routing, contact and conversation creation, and call setup. Because the `call_id` is synthetic, xAI accepts the WebSocket and then closes it. The conversation ends with `call_unavailable: xAI closed the socket (1005)`. A wrong `--secret` returns `401`.

## Operations

- Calls live on the process that received the webhook. Use a dedicated telephony service with always-on CPU and at least one warm instance (Cloud Run: `--no-cpu-throttling --min-instances 1`), and a long termination grace period on Kubernetes.
- Deploying a new revision drops in-flight calls on old instances unless they drain. Roll out gradually and outside peak hours.
- Remove a number from Telephony to delete it at xAI too. The number stays with your carrier.
