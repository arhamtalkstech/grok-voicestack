---
name: deploy-cloudrun
description: Deploy Voice Stack to Google Cloud Run as two services (private builder behind IAP, public telephony). Use when asked to deploy, update, or troubleshoot Voice Stack on Cloud Run or GCP.
---

# Deploy Voice Stack to Cloud Run

The playbook and its reasoning are in `docs/deploy/cloudrun.md`. Read it first.

1. Collect from the user: `PROJECT_ID`, `REGION`, a Postgres `DATABASE_URL` (and `CLOUDSQL_INSTANCE` if Cloud SQL), whether to store `XAI_API_KEY` in Secret Manager, and the Google group to grant IAP access.
2. Confirm `gcloud auth list` shows an account with deploy rights on the project.
3. Run `DRY_RUN=1 deploy/cloudrun/deploy.sh` with those variables and show the user the commands.
4. Ask the user to approve the real deploy. It creates billable resources and secrets. Then run `deploy/cloudrun/deploy.sh`.
5. Grant IAP access with the command the script prints.
6. Run `cd backend && uv run voicestack doctor --url <telephony URL>` and report each line.
7. Tell the user the remaining steps from "After deploying" in the playbook. Do not register phone numbers without their go-ahead.

For updates, re-run step 4. It tags the image with the git SHA. Warn that in-flight calls on old telephony instances drop during a rollout.
