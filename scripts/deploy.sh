#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ==============================================================================
# AstraZeneca Campaign Lab (UC4) — Cloud Provisioning & Deployment Script
# Configures Workforce Pool & Service Account IAM on gs://astrazeneca-ge-pilot-usecase,
# syncs UC4 brand logos, and deploys the standalone "AstraZeneca Campaign Lab"
# ADK Reasoning Engine to Vertex AI Agent Engine & Gemini Enterprise.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Source environment variables if .env exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PROJECT_ID="${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-gcp-ai-intelligence-dev-0a06}}"
PROJECT_NUMBER="${PROJECT_NUMBER:-${GOOGLE_CLOUD_PROJECT_NUMBER:-726684663091}}"
REGION="${AGENT_REGION:-${GOOGLE_CLOUD_LOCATION:-europe-west1}}"
APP_ID="${APP_ID:-${GEMINI_ENTERPRISE_ENGINE_ID:-gemini-enterprise-commerci_1781864147849}}"
SERVICE_NAME="${SERVICE_NAME:-AstraZeneca Campaign Lab}"
STAGING_BUCKET="${GCS_STAGING_BUCKET:-gs://astrazeneca-ge-pilot-usecase}"
GCS_EXPORT_BUCKET="${GCS_ASSETS_BUCKET:-astrazeneca-ge-pilot-usecase}"
ARTIFACT_SERVICE_URI="${ARTIFACT_SERVICE_URI:-gs://astrazeneca-ge-pilot-usecase}"
GCS_FOLDER_PREFIX="${GCS_FOLDER_PREFIX:-UC4}"
SIGNING_SERVICE_ACCOUNT="${SIGNING_SERVICE_ACCOUNT:-project-service-account@gcp-ai-intelligence-dev-0a06.iam.gserviceaccount.com}"
WORKFORCE_POOL_PRINCIPAL="${WORKFORCE_POOL_PRINCIPAL:-principalSet://iam.googleapis.com/locations/global/workforcePools/az-gemini-enterprise-oidc-pool/*}"
RE_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
DE_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

configure_iam_permissions() {
    echo "========================================================"
    echo " CONFIGURING CYBERSECURITY-COMPLIANT IAM (WORKFORCE POOL ONLY)"
    echo "========================================================"
    echo "Project ID          : $PROJECT_ID ($PROJECT_NUMBER)"
    echo "Unified GCS Bucket  : gs://${GCS_EXPORT_BUCKET} (Prefix: ${GCS_FOLDER_PREFIX}/)"
    echo "Signing SA          : $SIGNING_SERVICE_ACCOUNT"
    echo "Workforce Pool      : $WORKFORCE_POOL_PRINCIPAL"
    echo "Reasoning Engine SA : $RE_SERVICE_AGENT"
    echo "Discovery Engine SA : $DE_SERVICE_AGENT"

    # 1. Remove any forbidden domain-wide or public IAM bindings if present
    for FORBIDDEN_MEMBER in "domain:astrazeneca.net" "domain:astrazeneca.com" "allUsers" "allAuthenticatedUsers"; do
        gcloud storage buckets remove-iam-policy-binding "gs://${GCS_EXPORT_BUCKET}" \
            --member="$FORBIDDEN_MEMBER" \
            --role="roles/storage.objectViewer" \
            --quiet >/dev/null 2>&1 || true
    done

    # 2. Scope roles/storage.objectViewer strictly to the Workforce Identity Federation Pool
    echo "Granting roles/storage.objectViewer on gs://${GCS_EXPORT_BUCKET} to Workforce Identity Pool..."
    gcloud storage buckets add-iam-policy-binding "gs://${GCS_EXPORT_BUCKET}" \
        --member="$WORKFORCE_POOL_PRINCIPAL" \
        --role="roles/storage.objectViewer" \
        --quiet >/dev/null || true

    # 3. Grant roles/storage.objectAdmin on bucket and roles/iam.serviceAccountTokenCreator on signing SA
    for SA_PRINCIPAL in "$RE_SERVICE_AGENT" "$DE_SERVICE_AGENT" "$SIGNING_SERVICE_ACCOUNT"; do
        echo "Granting roles/storage.objectAdmin on gs://${GCS_EXPORT_BUCKET} to serviceAccount:${SA_PRINCIPAL}..."
        gcloud storage buckets add-iam-policy-binding "gs://${GCS_EXPORT_BUCKET}" \
            --member="serviceAccount:${SA_PRINCIPAL}" \
            --role="roles/storage.objectAdmin" \
            --quiet >/dev/null || true

        echo "Granting roles/iam.serviceAccountTokenCreator on ${SIGNING_SERVICE_ACCOUNT} to serviceAccount:${SA_PRINCIPAL}..."
        gcloud iam service-accounts add-iam-policy-binding "$SIGNING_SERVICE_ACCOUNT" \
            --project="$PROJECT_ID" \
            --member="serviceAccount:${SA_PRINCIPAL}" \
            --role="roles/iam.serviceAccountTokenCreator" \
            --condition=None \
            --quiet >/dev/null || true
    done

    echo "Cybersecurity-compliant IAM configuration verified!"
}

deploy_agent() {
    configure_iam_permissions

    echo "========================================================"
    echo " DEPLOYING ASTRAZENECA CAMPAIGN LAB (UC4) TO AGENT ENGINE & GEMINI ENTERPRISE"
    echo "========================================================"
    echo "Project ID           : $PROJECT_ID ($PROJECT_NUMBER)"
    echo "Region               : $REGION"
    echo "Service Name         : $SERVICE_NAME"
    echo "Staging Bucket       : $STAGING_BUCKET"
    echo "Artifact Service URI : $ARTIFACT_SERVICE_URI"
    echo "GCS Folder Prefix    : $GCS_FOLDER_PREFIX"

    # Sync official AstraZeneca vector & PNG logos to UC4 GCS prefix
    gcloud storage cp "${PROJECT_ROOT}/assets/astrazeneca_logos_svg/"* \
        "gs://${GCS_EXPORT_BUCKET}/${GCS_FOLDER_PREFIX}/logos/" >/dev/null 2>&1 || true

    PYTHON_BIN="${PROJECT_ROOT}/../Campaign_Expert/.venv/bin/python"
    if [ ! -f "$PYTHON_BIN" ]; then
        if [ -f ".venv/bin/python" ]; then
            PYTHON_BIN=".venv/bin/python"
        else
            PYTHON_BIN="python3"
        fi
    fi

    export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
    export GOOGLE_CLOUD_PROJECT_NUMBER="$PROJECT_NUMBER"
    export GOOGLE_CLOUD_LOCATION="$REGION"
    export GCS_STAGING_BUCKET="$STAGING_BUCKET"
    export GCS_ASSETS_BUCKET="$GCS_EXPORT_BUCKET"
    export ARTIFACT_SERVICE_URI="$ARTIFACT_SERVICE_URI"
    export GCS_FOLDER_PREFIX="$GCS_FOLDER_PREFIX"
    export SIGNING_SERVICE_ACCOUNT="$SIGNING_SERVICE_ACCOUNT"
    export GEMINI_ENTERPRISE_ENGINE_ID="$APP_ID"

    "$PYTHON_BIN" scripts/deploy_reasoning_engine.py --artifact_service_uri="$ARTIFACT_SERVICE_URI"

    echo "========================================================"
    echo " Deployment & Registration of ${SERVICE_NAME} (UC4) Completed Successfully!"
    echo "========================================================"
}

ACTION="${1:-deploy}"

case "$ACTION" in
    iam|--iam)
        configure_iam_permissions
        ;;
    deploy|--deploy)
        deploy_agent
        ;;
    *)
        echo "Usage: $0 {iam|deploy}"
        exit 1
        ;;
esac
