#!/usr/bin/env bash
# Fires a fake incident at the backend so you can watch the full pipeline
# run end-to-end without waiting for a real Alertmanager alert.
#
# Usage: ./scripts/send_test_alert.sh [API_BASE_URL]

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"

curl -s -X POST "${API_BASE}/webhook/alert" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "alertmanager",
    "severity": "critical",
    "service": "checkout-api",
    "namespace": "staging",
    "image": "ghcr.io/your-org/checkout-api:1.4.2",
    "summary": "checkout-api pod crash-looping with OOMKilled in staging",
    "raw": {"alertname": "PodCrashLooping", "pod": "checkout-api-7f9c8d-xk2lp"}
  }' | python3 -m json.tool
