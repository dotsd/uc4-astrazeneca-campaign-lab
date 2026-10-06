#!/usr/bin/env bash
# ==============================================================================
# AstraZeneca Campaign Lab (UC4) — Cloud Provisioning & Deployment Script
# Uploads UC4 logos/assets to gs://astrazeneca-ge-pilot-usecase/UC4/ and deploys
# the standalone "AstraZeneca Campaign Lab" Reasoning Engine to Gemini Enterprise.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  source "${PROJECT_ROOT}/.env"
  set +a
fi

echo "=============================================================================="
echo " Deploying: ${SERVICE_NAME:-AstraZeneca Campaign Lab} (UC4)"
echo " Project:   ${GOOGLE_CLOUD_PROJECT} (${GOOGLE_CLOUD_PROJECT_NUMBER})"
echo " Region:    ${GOOGLE_CLOUD_LOCATION}"
echo " GCS Path:  gs://${GCS_ASSETS_BUCKET}/${GCS_FOLDER_PREFIX}/"
echo "=============================================================================="

# 1. Sync official AstraZeneca vector & PNG logos to UC4 GCS prefix
gcloud storage cp "${PROJECT_ROOT}/assets/astrazeneca_logos_svg/"* \
  "gs://${GCS_ASSETS_BUCKET}/${GCS_FOLDER_PREFIX}/logos/"

# 2. Deploy the ADK Reasoning Engine & Register in Gemini Enterprise
python3 "${PROJECT_ROOT}/scripts/deploy_reasoning_engine.py"

echo "=============================================================================="
echo " Deployment of ${SERVICE_NAME:-AstraZeneca Campaign Lab} (UC4) Complete!"
echo "=============================================================================="
