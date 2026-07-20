#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODEL=${1:-"$SCRIPT_DIR/OrderWorkflow.mch"}
OUT=${2:-"$SCRIPT_DIR/prob-run.log"}
command -v probcli >/dev/null || { echo "probcli is not installed" >&2; exit 2; }
{
  probcli --version || true
  sha256sum "$MODEL"
  # Pin/tune these preferences for the approved ProB release and record the exact command.
  probcli "$MODEL" -model_check -nodead -p MAX_OPERATIONS 10000
} | tee "$OUT"
