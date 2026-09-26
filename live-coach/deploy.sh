#!/usr/bin/env bash
set -e

# ==============================================================================
# Deploy Live Trainer to Google Cloud Run
# ==============================================================================

SERVICE_NAME="live-coach"
REGION="${GCP_REGION:-us-central1}"

# Check for GEMINI_API_KEY
if [ -z "$GEMINI_API_KEY" ]; then
  if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
  fi
fi

if [ -z "$GEMINI_API_KEY" ]; then
  echo "Error: GEMINI_API_KEY is not set."
  echo "Please set it via: export GEMINI_API_KEY='your-key' or in .env"
  exit 1
fi

echo "========================================================"
echo " Deploying ${SERVICE_NAME} to Google Cloud Run"
echo " Region: ${REGION}"
echo " WebSocket timeout: 3600s (60 min)"
echo " Session affinity: Enabled"
echo "========================================================"

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --allow-unauthenticated \
  --timeout=3600 \
  --session-affinity \
  --set-env-vars GEMINI_API_KEY="$GEMINI_API_KEY",MODEL_LIVE="gemini-3.8-live",MODEL_TTS="gemini-3.8-flash-tts",MODEL_FLASH="gemini-3.8-flash"


echo ""
echo "Deployment completed successfully! Open the Service URL shown above in your browser."
