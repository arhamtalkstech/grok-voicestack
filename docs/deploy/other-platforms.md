# Other platforms

The image runs anywhere that runs a container. Map the two roles the same way:

| Platform | App (`ROLE=app`) | Telephony (`ROLE=telephony`) | Notes |
|---|---|---|---|
| AWS ECS on Fargate | Service behind an ALB with an OIDC/Cognito listener rule. Stickiness on. Idle timeout 3600 s. | Separate service and ALB target group routing only `/webhooks/*`, at least one task, `stopTimeout` 120 s (Fargate maximum). | RDS Postgres. Secrets from Secrets Manager into env. |
| Azure Container Apps | Ingress with Easy Auth (Entra ID). Session affinity on. | Separate app with external ingress, min replicas 1. | Azure Database for PostgreSQL. Use secrets mapped to env. |
| Fly.io | `fly launch` with the Dockerfile and `[http_service]` on port 8000. | A second app with `min_machines_running = 1` and `auto_stop_machines = false`. | Fly Postgres or any managed Postgres. |
| Render / Railway | Web service from the Dockerfile. | Second service, always on. | Managed Postgres. Enable WebSocket timeouts as high as the platform allows. |

Requirements on every platform:

- WebSockets for `/api/sessions/*/ws` (previews) and `/api/live/ws` (monitors), with long idle timeouts.
- An HTTPS URL for the telephony role, set as `PUBLIC_BASE_URL` on the app role.
- Telephony instances that stay running for the duration of a call, which on Fargate is bounded by `stopTimeout`.
- `APP_ENCRYPTION_KEY`, `DATABASE_URL`, and either `AUTH_MODE=token` or an identity proxy.

Run `voicestack doctor --url <telephony-url>` after deploying.
