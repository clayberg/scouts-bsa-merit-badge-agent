#!/usr/bin/env bash
# ==============================================================================
# Scouts BSA Merit Badge Counselor Workbench — Turn-Key Cloud Run Deployment
# ==============================================================================
# Deploys the FastAPI + Material 3 Expressive A2UI Workbench & A2A 1.0 Server
# to Google Cloud Run using Vertex AI (ADC) and verifies /health and /readiness.
#
# Usage:
#   ./scripts/deploy_cloud_run.sh --project <PROJECT_ID> [--region us-central1] [--public]
#
# For Argolis (altostrat.com) accounts:
#   Pass --public to automatically relax the project-level
#   `iam.allowedPolicyMemberDomains` org policy so `--allow-unauthenticated`
#   public access works on the Cloud Run URL.
# ==============================================================================

set -euo pipefail

# Always run from the repository root (where Dockerfile is located), even if invoked from scripts/
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="scouts-bsa-merit-badge-agent"
ALLOW_PUBLIC="false"
GCLOUD_CONFIG="${GCLOUD_CONFIG:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region|-r)
      REGION="$2"
      shift 2
      ;;
    --service|-s)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --public)
      ALLOW_PUBLIC="true"
      shift 1
      ;;
    --configuration|-c)
      GCLOUD_CONFIG="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 --project <PROJECT_ID> [--region us-central1] [--public] [--configuration argolis]"
      exit 1
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: --project <PROJECT_ID> is required (or set GOOGLE_CLOUD_PROJECT)."
  exit 1
fi

# Prevent Google Cloudtop internal mTLS / quota-project overrides from interfering with external/Argolis accounts
unset CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE \
      CLOUDSDK_CONTEXT_AWARE_USE_MTLS_FOR_GRPC \
      CLOUDSDK_CONTEXT_AWARE_USE_ECP_HTTP_PROXY \
      CLOUDSDK_INTERNAL_USER || true

# Charge API quota to the target project rather than the shared Cloud Shell project (618104708054)
export CLOUDSDK_BILLING_PROJECT="${PROJECT_ID}"

GCLOUD_ARGS=(--project="${PROJECT_ID}" --billing-project="${PROJECT_ID}")
if [[ -n "${GCLOUD_CONFIG}" ]]; then
  GCLOUD_ARGS+=(--configuration="${GCLOUD_CONFIG}")
fi

echo "=============================================================================="
echo " Deploying ${SERVICE_NAME} to Cloud Run"
echo " Repo Dir: ${REPO_ROOT}"
echo " Project : ${PROJECT_ID}"
echo " Region  : ${REGION}"
echo " Public  : ${ALLOW_PUBLIC}"
echo "=============================================================================="

echo "[1/5] Enabling required Google Cloud APIs..."
if ! gcloud "${GCLOUD_ARGS[@]}" services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  orgpolicy.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com; then
  echo "      Note: gcloud services enable returned a quota/rate-limit warning; continuing since APIs are already enabled..."
fi

if [[ "${ALLOW_PUBLIC}" == "true" ]]; then
  echo "[2/5] Configuring project-level Org Policy (iam.allowedPolicyMemberDomains) for public Cloud Run access..."
  TMP_POLICY="$(mktemp /tmp/orgpolicy_XXXXXX.yaml)"
  cat > "${TMP_POLICY}" <<EOF
name: projects/${PROJECT_ID}/policies/iam.allowedPolicyMemberDomains
spec:
  rules:
  - allowAll: true
EOF
  if gcloud "${GCLOUD_ARGS[@]}" org-policies set-policy "${TMP_POLICY}" >/dev/null 2>&1; then
    echo "      Org policy updated (allowAll: true). Waiting 10s for IAM propagation..."
    sleep 10
  else
    echo "      Note: Could not override iam.allowedPolicyMemberDomains (org policy may not be enforced or requires Org Policy Admin)."
  fi
  rm -f "${TMP_POLICY}"
else
  echo "[2/5] Skipping public Org Policy override (pass --public for unauthenticated Argolis access)."
fi

echo "[3/5] Granting Vertex AI & Cloud Build source-deploy IAM roles to the Compute service account..."
PROJECT_NUMBER="$(gcloud "${GCLOUD_ARGS[@]}" projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# New GCP / Argolis projects enforce iam.automaticIamGrantsForDefaultServiceAccounts, so the default
# Compute SA requires explicit Storage, Artifact Registry, Logging, Cloud Build, and Vertex AI roles.
for ROLE in \
  "roles/aiplatform.user" \
  "roles/storage.objectAdmin" \
  "roles/artifactregistry.writer" \
  "roles/logging.logWriter" \
  "roles/cloudbuild.builds.builder"; do
  echo "      Binding ${ROLE} -> ${COMPUTE_SA}"
  gcloud "${GCLOUD_ARGS[@]}" projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="${ROLE}" \
    --quiet >/dev/null
done

AUTH_FLAG="--no-allow-unauthenticated"
if [[ "${ALLOW_PUBLIC}" == "true" ]]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

echo "[4/5] Building Dockerfile and deploying container from ${REPO_ROOT} to Cloud Run..."
gcloud "${GCLOUD_ARGS[@]}" run deploy "${SERVICE_NAME}" \
  --source "${REPO_ROOT}" \
  --region="${REGION}" \
  --port=8085 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=300 \
  --quiet \
  "${AUTH_FLAG}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=true,ENABLE_OPENTELEMETRY=false,AUTH_REQUIRED=false"

SERVICE_URL="$(gcloud "${GCLOUD_ARGS[@]}" run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')"
echo "[5/5] Verifying live Cloud Run endpoints at ${SERVICE_URL}..."

if [[ "${ALLOW_PUBLIC}" == "true" ]]; then
  curl -fsS "${SERVICE_URL}/health" && echo ""
  curl -fsS "${SERVICE_URL}/readiness" && echo ""
else
  ID_TOKEN="$(gcloud "${GCLOUD_ARGS[@]}" auth print-identity-token)"
  curl -fsS -H "Authorization: Bearer ${ID_TOKEN}" "${SERVICE_URL}/health" && echo ""
  curl -fsS -H "Authorization: Bearer ${ID_TOKEN}" "${SERVICE_URL}/readiness" && echo ""
fi

echo "=============================================================================="
echo " ✅ Cloud Run Deployment Verified!"
echo " Workbench URL : ${SERVICE_URL}"
echo " Health Probe  : ${SERVICE_URL}/health"
echo " Readiness     : ${SERVICE_URL}/readiness"
echo "=============================================================================="
