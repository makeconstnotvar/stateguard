#!/usr/bin/env bash
set -euo pipefail
: "${STATEGUARD_CONTROL_URL:?Set internal control-plane URL}"
: "${STATEGUARD_CONTROL_TOKEN:?Set workload token}"
PAYLOAD=${1:?Usage: publish-example.sh run.json}
curl --fail --silent --show-error \
  --header "Authorization: Bearer $STATEGUARD_CONTROL_TOKEN" \
  --header "Content-Type: application/json" \
  --data-binary "@$PAYLOAD" \
  "$STATEGUARD_CONTROL_URL/v1/runs"
