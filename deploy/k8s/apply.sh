#!/usr/bin/env bash
# Apply the Kubernetes manifests. Create the secret first (see docs/deploy/kubernetes.md):
#   kubectl -n voicestack create secret generic voicestack \
#     --from-literal=APP_ENCRYPTION_KEY=... --from-literal=DATABASE_URL=postgresql://... --from-literal=XAI_API_KEY=...
# Set IMAGE to your pushed image. DRY_RUN=1 renders without applying.
set -euo pipefail
cd "$(dirname "$0")"
: "${IMAGE:?Set IMAGE, e.g. ghcr.io/your-org/voicestack:1.0.0}"
DRY_RUN="${DRY_RUN:-0}"
RENDERED="$(kubectl kustomize . | sed "s|voicestack:latest|${IMAGE}|g")"
if [ "$DRY_RUN" = "1" ]; then
  echo "$RENDERED"
else
  echo "$RENDERED" | kubectl apply -f -
  kubectl -n voicestack rollout status deploy/voicestack-app --timeout=180s
  kubectl -n voicestack rollout status deploy/voicestack-telephony --timeout=180s
fi
