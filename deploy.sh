#!/usr/bin/env bash
set -euo pipefail

PROJECT=bikram-java
REGION=us-east1
REPO=us-travel-planner-repo
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/us-travel-planner-frontend"
SERVICE=us-travel-planner-frontend
AGENT_RESOURCE="projects/527485542788/locations/us-east1/reasoningEngines/5990579152774758400"

echo "==> Ensuring Artifact Registry repo exists..."
gcloud artifacts repositories describe "${REPO}" \
  --location="${REGION}" --project="${PROJECT}" &>/dev/null \
  || gcloud artifacts repositories create "${REPO}" \
       --repository-format=docker \
       --location="${REGION}" \
       --project="${PROJECT}"

echo "==> Building frontend image via Cloud Build..."
gcloud builds submit \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --tag="${IMAGE}:latest" \
  ./frontend

echo "==> Deploying Cloud Run service..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=${AGENT_RESOURCE},AGENT_DIRECTORY=app,GOOGLE_CLOUD_PROJECT=${PROJECT}" \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3

echo ""
echo "==> Done! Service URL:"
gcloud run services describe "${SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --format="value(status.url)"
