# Deploy on Google Cloud Run (internal)

This playbook runs Voice Stack for an internal team: the builder is reachable only through IAP, and phone calls come in on a separate public service.

```
                    IAP (your Google group)
users ───────────────▶ voicestack-app        ROLE=app        UI, API, live previews
xAI SIP webhooks ────▶ voicestack-telephony  ROLE=telephony  /webhooks/* + call workers (always-on CPU)
                              │
                      Cloud SQL Postgres + Secret Manager
```

Why two services:

- The builder must be private, but xAI must reach the webhook. One public service limited to `/webhooks/*` keeps the attack surface small.
- Call workers hold a WebSocket outside any HTTP request. On Cloud Run that needs CPU allocated all the time (`--no-cpu-throttling`) and a warm instance (`--min-instances 1`). The builder does not need either.

## Before you start

- A GCP project with billing, and `gcloud` authenticated as someone who can enable APIs and deploy Cloud Run.
- A Postgres database. Cloud SQL works: create an instance and database, then use a URL like `postgresql://USER:PASS@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE` with `CLOUDSQL_INSTANCE=PROJECT:REGION:INSTANCE`. Any reachable Postgres also works.
- Optional: an xAI API key to store in Secret Manager. You can also save it later in the builder's Settings.

## Deploy

```bash
export PROJECT_ID=my-project REGION=us-central1
export DATABASE_URL='postgresql://voicestack:PASS@/voicestack?host=/cloudsql/my-project:us-central1:voicestack'
export CLOUDSQL_INSTANCE=my-project:us-central1:voicestack
export XAI_API_KEY=...                 # optional
DRY_RUN=1 deploy/cloudrun/deploy.sh    # review every command
deploy/cloudrun/deploy.sh              # or: voicestack deploy cloudrun
```

The script:

1. Enables Cloud Run, Artifact Registry, Cloud Build, Secret Manager, and IAP.
2. Creates an Artifact Registry repo and builds the image with Cloud Build.
3. Creates secrets: `voicestack-encryption-key` (generated), `voicestack-database-url`, and optionally `voicestack-xai-api-key`. It grants the runtime service account access. Existing secrets are left unchanged.
4. Deploys `voicestack-telephony`: public, `--no-cpu-throttling --min-instances 1 --timeout 3600 --concurrency 80`.
5. Deploys `voicestack-app` with `--no-allow-unauthenticated --session-affinity --timeout 3600`, `AUTH_MODE=proxy`, and `PUBLIC_BASE_URL` set to the telephony URL. It then turns on IAP.
6. Prints both URLs.

Grant your team access through IAP:

```bash
gcloud beta iap web add-iam-policy-binding --resource-type=cloud-run --service=voicestack-app \
  --region=$REGION --member=group:voice-team@example.com --role=roles/iap.httpsResourceAccessor
```

Cloud Run's direct IAP integration (`--iap`) is a beta `gcloud` surface. If your organization uses a load balancer with IAP instead, deploy the app service with `--ingress internal-and-cloud-load-balancing` and attach IAP to the backend service. Either way, set `AUTH_MODE=proxy` only when IAP is the sole path to the service. Otherwise use `AUTH_MODE=token`, which the script picks when `IAP=false`.

## After deploying

```bash
voicestack doctor --url https://voicestack-telephony-xxxx.a.run.app
```

In the builder:

1. **Settings:** save the xAI key, unless it came from Secret Manager.
2. **Agents:** publish the agents that should answer calls.
3. **Telephony:** add your number. The webhook points at the telephony service automatically.
4. Point your carrier at the SIP URI shown.

## Operating it

- **Rollouts drop in-flight calls** on old telephony instances when they stop. Deploy during quiet hours, or use `gcloud run services update-traffic` to shift traffic gradually while old revisions drain.
- **Scaling:** each telephony instance handles many concurrent calls. Raise `--max-instances` as needed. The app service scales to zero when unused.
- **Live monitors are per instance.** Conversations are visible to every instance through Postgres, and the live view shows the sessions on the instance serving it.
- **Logs:** Cloud Logging collects uvicorn and app logs. Set `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` as env vars to trace every graph run in LangSmith.
- **Updating:** re-run the script. It builds a new image tagged with the git SHA and deploys both services.

## Cost notes

The telephony service keeps one instance with always-on CPU, which is billed continuously. The app service with min-instances 0 costs nothing when idle. xAI usage is billed per minute of voice.
