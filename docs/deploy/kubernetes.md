# Deploy on Kubernetes

Manifests are in `deploy/k8s/` (Kustomize): a namespace, a ConfigMap, two Deployments (`voicestack-app`, `voicestack-telephony`), Services, an HPA for the app, a PodDisruptionBudget for telephony, and an Ingress with two hosts.

```bash
docker build -t ghcr.io/your-org/voicestack:1.0.0 . && docker push ghcr.io/your-org/voicestack:1.0.0
kubectl create namespace voicestack
kubectl -n voicestack create secret generic voicestack \
  --from-literal=APP_ENCRYPTION_KEY="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" \
  --from-literal=DATABASE_URL='postgresql://user:pass@postgres:5432/voicestack' \
  --from-literal=XAI_API_KEY='...'
IMAGE=ghcr.io/your-org/voicestack:1.0.0 DRY_RUN=1 deploy/k8s/apply.sh   # render
IMAGE=ghcr.io/your-org/voicestack:1.0.0 deploy/k8s/apply.sh             # apply and wait for rollout
```

Edit before applying:

- `configmap.yaml`: set `PUBLIC_BASE_URL` to the public webhook host. `AUTH_MODE=proxy` assumes your ingress enforces identity, for example with oauth2-proxy. Otherwise switch to `token` and add `ADMIN_TOKEN` to the secret.
- `ingress.yaml`: set both hosts, the ingress class, and TLS. The webhook host routes only `/webhooks` and `/healthz` to telephony pods.

Design notes:

- **Telephony pods** have `terminationGracePeriodSeconds: 3600`, `maxUnavailable: 0`, and a PodDisruptionBudget, so rollouts and node drains let active calls finish.
- **App pods** use `sessionAffinity: ClientIP` and cookie affinity at the ingress, so a preview's control WebSocket and its REST calls reach the same pod. The ingress timeouts are 3600 s for WebSockets.
- **Postgres** is required with more than one replica. SQLite on `emptyDir` is per pod.
