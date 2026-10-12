# Keys and security

## Bring your own key

Voice Stack resolves the xAI key for each request in this order:

1. **Session-only key.** Entered in Settings, held in the browser tab's memory, and sent as `X-XAI-API-Key` with each request. It is never written to the server or to browser storage. It is used for previews, voices, TTS samples, and the optimiser. Phone calls cannot use it.
2. **Workspace key.** Saved in Settings. It is validated against `GET /v1/models` before saving and encrypted at rest.
3. **`XAI_API_KEY`** from the environment.

The UI only ever shows the last four characters. Keys never reach the browser. Live previews in direct mode get an **ephemeral token** from `POST /v1/realtime/client_secrets` (TTL `EPHEMERAL_TOKEN_TTL_S`, default 300 s) and pass it as the WebSocket subprotocol `xai-client-secret.<token>`.

## Secrets at rest

API keys, webhook signing secrets, and tool or MCP secrets are encrypted with AES-GCM. The key is derived from `APP_ENCRYPTION_KEY`, which must be a 32-byte urlsafe-base64 value or any passphrase. In production the app refuses to start without it. In development a key file is generated in `DATA_DIR/encryption.key`. Landscape exports contain secret names, never values.

## Builder access

| `AUTH_MODE` | Use |
|---|---|
| `none` | Local development only. |
| `token` | A shared `ADMIN_TOKEN`. The UI asks for it once and sends it as a bearer token, and as `?token=` on WebSockets. |
| `proxy` | Behind Cloud Run IAP, Cloudflare Access, or oauth2-proxy. The identity header (`PROXY_USER_HEADER`, default `x-goog-authenticated-user-email`) must be present. Only use this when the proxy is the sole way in. |

The webhook endpoint is public by design. It is protected by signature verification, a timestamp window, and deduplication. In the two-service layout, only the telephony service is public.

## Outbound safety

HTTP tools and run-by-Voice-Stack MCP servers go through an SSRF guard. Destinations that resolve to private, loopback, link-local, reserved, or multicast addresses are refused unless allowlisted with `SSRF_ALLOWLIST` (hosts, `*.domain`, or CIDRs). Redirects are not followed.

## Data

- Audio is not recorded. Transcripts, tool calls with their arguments and outputs, handoffs, summaries, and a realtime event log are stored in the database (see [history-and-memory.md](history-and-memory.md)). Set `RECORD_EVENTS=false` to skip the event log.
- Collections-mode knowledge files are stored in your xAI team through the Files API. Local-mode files stay in `DATA_DIR`.
- Deleting a conversation removes its turns, its event log, and its LangGraph checkpoint thread.
- Custom voice uploads require confirming that the speaker consented to cloning.

## Known gaps

- `AUTH_MODE=proxy` trusts the identity header. It does not verify the IAP JWT (`x-goog-iap-jwt-assertion`). Add verification if the service could be reached without the proxy.
- There are no per-user roles; everyone with access is an admin.
