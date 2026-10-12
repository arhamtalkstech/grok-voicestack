---
name: deploy-kubernetes
description: Deploy Voice Stack to a Kubernetes cluster with the Kustomize manifests in deploy/k8s. Use when asked to deploy Voice Stack to Kubernetes, GKE, EKS, or AKS.
---

# Deploy Voice Stack to Kubernetes

Details are in `docs/deploy/kubernetes.md`.

1. Confirm the target context: `kubectl config current-context`. Ask the user to confirm it is the right cluster.
2. Build and push the image to a registry the cluster can pull from. Get the image reference from the user.
3. Edit `deploy/k8s/configmap.yaml` (`PUBLIC_BASE_URL`, `AUTH_MODE`) and `deploy/k8s/ingress.yaml` (hosts, class, TLS) with the user's values.
4. Create the `voicestack` secret with the command in the doc. Ask the user for the values, and do not echo them back.
5. Run `IMAGE=... DRY_RUN=1 deploy/k8s/apply.sh` and show the rendered manifests. Then run it without `DRY_RUN` after the user approves.
6. Run `voicestack doctor --url https://<webhook host>` and report the results.
