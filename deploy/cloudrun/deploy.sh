#!/usr/bin/env bash
# Deploy Voice Stack to Google Cloud Run as two services from one image.
#
#   voicestack-app        UI + API, behind IAP (only your org can reach it)
#   voicestack-telephony  public, serves only /webhooks/* and runs phone-call workers
#
# Required:  PROJECT_ID, and DATABASE_URL (Postgres; Cloud SQL works) unless the secret exists.
# Optional:  REGION (us-central1), PREFIX (voicestack), TAG (git sha or timestamp),
#            CLOUDSQL_INSTANCE (project:region:instance), XAI_API_KEY (stored in Secret Manager),
#            IAP=true|false (default true), DRY_RUN=1 (print commands only).
# Full playbook: docs/deploy/cloudrun.md
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
PREFIX="${PREFIX:-voicestack}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IAP="${IAP:-true}"
DRY_RUN="${DRY_RUN:-0}"
REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/${PREFIX}"
IMAGE="${REPO}/voicestack:${TAG}"

run() {
  echo "+ $*"
  if [ "$DRY_RUN" != "1" ]; then "$@"; fi
}

secret_exists() { [ "$DRY_RUN" = "1" ] && return 1; gcloud secrets describe "$1" --project "$PROJECT_ID" >/dev/null 2>&1; }

put_secret() {
  local name="$1" value="$2"
  if secret_exists "$name"; then
    echo "  secret $name exists (leaving it unchanged)"
  else
    echo "+ gcloud secrets create $name (value hidden)"
    if [ "$DRY_RUN" != "1" ]; then
      printf '%s' "$value" | gcloud secrets create "$name" --project "$PROJECT_ID" --replication-policy automatic --data-file=-
    fi
  fi
}

echo "==> Project ${PROJECT_ID}, region ${REGION}, image ${IMAGE}"
run gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com iap.googleapis.com --project "$PROJECT_ID"

if [ "$DRY_RUN" = "1" ] || ! gcloud artifacts repositories describe "$PREFIX" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  run gcloud artifacts repositories create "$PREFIX" --repository-format docker --location "$REGION" --project "$PROJECT_ID"
fi

echo "==> Build and push"
run gcloud builds submit --project "$PROJECT_ID" --tag "$IMAGE" .

echo "==> Secrets"
put_secret "${PREFIX}-encryption-key" "$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
if ! secret_exists "${PREFIX}-database-url"; then
  : "${DATABASE_URL:?Set DATABASE_URL (Postgres) the first time; it is stored in Secret Manager}"
fi
put_secret "${PREFIX}-database-url" "${DATABASE_URL:-}"
SECRETS="APP_ENCRYPTION_KEY=${PREFIX}-encryption-key:latest,DATABASE_URL=${PREFIX}-database-url:latest"
if [ -n "${XAI_API_KEY:-}" ] || secret_exists "${PREFIX}-xai-api-key"; then
  put_secret "${PREFIX}-xai-api-key" "${XAI_API_KEY:-}"
  SECRETS="${SECRETS},XAI_API_KEY=${PREFIX}-xai-api-key:latest"
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)' 2>/dev/null || echo PROJECT_NUMBER)"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
BOUND="encryption-key database-url"
case "$SECRETS" in *XAI_API_KEY*) BOUND="$BOUND xai-api-key" ;; esac
for s in $BOUND; do
  if [ "$DRY_RUN" = "1" ] || secret_exists "${PREFIX}-${s}"; then
    run gcloud secrets add-iam-policy-binding "${PREFIX}-${s}" --project "$PROJECT_ID" \
      --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor --quiet
  fi
done

SQL_FLAGS=()
if [ -n "${CLOUDSQL_INSTANCE:-}" ]; then SQL_FLAGS=(--add-cloudsql-instances "$CLOUDSQL_INSTANCE"); fi

echo "==> Telephony service (public webhook, always-on CPU for call sockets)"
run gcloud run deploy "${PREFIX}-telephony" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
  --allow-unauthenticated --no-cpu-throttling --min-instances 1 --max-instances 10 --concurrency 80 \
  --timeout 3600 --cpu 1 --memory 1Gi --port 8000 \
  --set-env-vars "ROLE=telephony,APP_ENV=production,SEED_EXAMPLE=false" \
  --set-secrets "$SECRETS" ${SQL_FLAGS[@]+"${SQL_FLAGS[@]}"}

TELEPHONY_URL="$(gcloud run services describe "${PREFIX}-telephony" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)' 2>/dev/null || echo https://TELEPHONY_URL)"

echo "==> App service (UI + API)"
AUTH_FLAGS=(--no-allow-unauthenticated)
AUTH_MODE="token"
if [ "$IAP" = "true" ]; then AUTH_MODE="proxy"; fi
run gcloud beta run deploy "${PREFIX}-app" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
  "${AUTH_FLAGS[@]}" --session-affinity --timeout 3600 --cpu 1 --memory 2Gi --port 8000 --min-instances 0 \
  --set-env-vars "ROLE=app,APP_ENV=production,AUTH_MODE=${AUTH_MODE},PUBLIC_BASE_URL=${TELEPHONY_URL}" \
  --set-secrets "$SECRETS" ${SQL_FLAGS[@]+"${SQL_FLAGS[@]}"}
if [ "$IAP" = "true" ]; then
  run gcloud beta run services update "${PREFIX}-app" --project "$PROJECT_ID" --region "$REGION" --iap
  echo "  Grant access: gcloud beta iap web add-iam-policy-binding --resource-type=cloud-run --service=${PREFIX}-app \\"
  echo "    --region=${REGION} --member=group:YOUR-TEAM@example.com --role=roles/iap.httpsResourceAccessor"
fi

APP_URL="$(gcloud run services describe "${PREFIX}-app" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)' 2>/dev/null || echo https://APP_URL)"
cat <<EOF

Done.
  Builder:   ${APP_URL}
  Webhooks:  ${TELEPHONY_URL}/webhooks/xai/call-incoming   (register numbers from Telephony in the builder)
  Check:     voicestack doctor --url ${TELEPHONY_URL}
EOF
