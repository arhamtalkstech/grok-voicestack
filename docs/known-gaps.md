# Known gaps and TODOs

Everything in the UI calls a real backend path; there is no mock data. This file lists what is **not built**, **not verified against a live system**, or **known to behave unreliably**. It was produced by auditing every UI action against the backend and by running the live tests in `docs/testing.md` (2026-10-12). Pick an item, fix it, add a test, and remove it from this list.

## Not built

- [ ] **Audio recording.** No call audio is stored, only transcripts, tool calls, and events. Where audio can be captured:
  - Relay mode: the server sees both directions (`runtime/transports/relay.py`).
  - SIP: the server receives the assistant's audio deltas, but xAI bridges the caller's audio directly.
  - Direct mode: the browser would need to upload a `MediaRecorder` capture.

  Add storage (S3/GCS), a retention policy, and consent prompts before building this.
- [ ] **Full event log in direct-mode previews.** The browser forwards only the events the server needs to make decisions: transcripts, function calls, `response.created`/`response.done`, speech start/stop, MCP events, and errors. Relay mode and phone calls record every event except audio and transcript deltas. To log everything in direct mode, forward more types in `frontend/src/audio/live.ts` (`FORWARD`).
- [ ] **Outbound webhooks** to tell other systems when a conversation starts, hands off, or ends. Today, use `wss://…/api/live/ws` or poll `GET /api/conversations`. (An unused table for this was removed.)
- [ ] **Database migrations.** Tables are created with SQLAlchemy `create_all` at startup, which adds new tables but never alters existing ones. Add Alembic before changing a column in a deployed database. Since 2026-10-12, `conversation_events` is new, and the `outbound_webhooks` and `settings` tables are unused in older databases.
- [ ] **Users and roles.** Everyone with access is an admin. `AUTH_MODE=proxy` trusts the identity header without verifying the IAP JWT (`x-goog-iap-jwt-assertion`).
- [ ] **Outbound phone calls.** xAI's public API documents inbound SIP only.
- [ ] **Data lifecycle.**
  - Deleting a conversation leaves the caller's memory profile in the LangGraph store.
  - There is no retention job and no per-contact export or erase.
- [ ] **UI editing gaps.** The API supports these, but the UI doesn't expose them yet:
  - A phone number's disclosure line and "use published versions" setting after registration (`PATCH /api/telephony/numbers/{id}`).
  - A knowledge base's `top_k` after creation.
  - An HTTP tool's `body_template` (YAML or API only).
- [ ] **Vector index for local mode.** `SqlVectorStore` does brute-force cosine search. For large local corpora, swap in pgvector or another LangChain `VectorStore` (`knowledge/ingest.py`).

## Built but not verified end to end

- [ ] **A real phone call through a carrier.** These were run against the live API:
  - number registration and deletion
  - signed-webhook routing using the real signing secret
  - call setup
  - the `refer`/`hangup` endpoints (404 for an unknown call)

  Not yet observed on a real call: DTMF events, the verbatim disclosure, a successful REFER, and `output_audio_buffer` playback timing on SIP.
- [ ] **Deploying to Cloud Run and Kubernetes.** `deploy/cloudrun/deploy.sh` was run with `DRY_RUN=1`, and the k8s manifests were rendered. Neither has been applied to a real project or cluster. Docker Compose was run and passes `voicestack doctor`.
- [ ] **Successful custom voice creation.** This team gets xAI's 403 ("not available in your region"), and the UI shows it. Listing and using existing custom voices works.
- [ ] **Managed MCP over stdio**, and the `openai_compatible` embeddings provider. Code paths exist; neither has been run.
- [ ] **Collections metadata.** Documents are attached without custom fields, and `field_definitions` and metadata filters are not exposed. During testing, one upload that sent an undeclared custom field never finished processing at xAI. Uploads without fields processed in seconds.

## Behavior that depends on xAI (worked around or documented)

These come from `backend/spikes/phase0.py` (`docs/xai-api-notes.md`) and the live tests:

- **Native `x_search` in realtime** hands its inner tool (`x_keyword_search`) to the client and never runs it. Voice Stack provides its own `x_search` function tool through the Responses API instead.
- **Server-side tools** (`web_search`, `browse_page`, `collections_search`) also appear as function-call events, even though xAI runs them. Voice Stack records them as server-side tool turns and does not answer them.
- **xAI-hosted MCP with slow servers (DeepWiki)** often stalled after `response.mcp_call.in_progress`. Managed mode, with `MCP_TOOL_TIMEOUT_S`, works.
- **Native session resumption** (`conversation_id`) replayed assistant turns but not typed user turns. "Continue in preview" seeds the full history instead.
- **Collections management route.** xAI's docs describe creating collections and attaching documents on `management-api.x.ai` with a Management API key, and searching on `api.x.ai` with a regular API key. Voice Stack calls the same `/v1/collections` routes on `api.x.ai` with the regular API key. That worked in every live test, but it is not the documented route and could change. If it stops working, add a Management-key option that uses `management-api.x.ai` (`xai/client.py`).
- **The voice agent sometimes answers without searching its documents.** In about 1 of 4 live runs of `test_live_knowledge_collections`, the agent said it had no information instead of calling `file_search`, even with the compiler's "always search before saying you do not know" line. Try stronger per-agent prompt wording or a lower `top_k` description, and keep the test to catch regressions.
- **Collections indexing time varies.** Most files processed in seconds, but one stayed at "Processing" for more than ten minutes. Voice Stack keeps such documents as "indexing" and re-checks them whenever the knowledge page loads.
