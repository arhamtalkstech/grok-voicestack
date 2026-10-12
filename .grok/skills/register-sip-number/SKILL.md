---
name: register-sip-number
description: Connect a phone number on a SIP trunk (Twilio, Telnyx, Plivo, PBX) to a Voice Stack agent and test the routing. Use when asked to add a phone number, set up SIP, or make an agent answer calls.
---

# Register a SIP number

How it works and the carrier steps are in `docs/telephony-sip.md`.

1. Check prerequisites against the running instance: `GET /api/telephony/info` must show `webhook_url` set and `server_key_configured: true`. If not, explain which env var or setting is missing.
2. Ask the user for the E.164 number, a name, which agent answers, and their carrier's SIP signaling CIDRs. Digest credentials and a spoken disclosure are optional.
3. Make sure the answering agents are published (`POST /api/agents/{id}/publish`). Numbers answer with published versions by default.
4. Register the number with `POST /api/telephony/numbers`, or in the UI under Telephony → Add number. This calls xAI's `POST /v2/phone-numbers`, so confirm with the user first.
5. Give the user the SIP URI from the response and the carrier steps for their provider from the doc.
6. Test routing without a call: `uv run voicestack sip simulate --to <number> --url <instance>`. Expect `200 accepted` and a new SIP conversation marked as an error (the call_id is synthetic). Then ask the user to place a real call and check Conversations.
