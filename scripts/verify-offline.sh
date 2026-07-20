#!/usr/bin/env bash
set -euo pipefail

# This script does not prove that a binary contains no telemetry. It verifies the operational
# controls under our authority: local rules, no platform token, and a network-disabled container.
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)

if env | grep -Eq '^SEMGREP_(APP_TOKEN|DEPLOYMENT_ID)='; then
  echo "Semgrep platform credentials are present in the environment." >&2
  exit 1
fi

if grep -R --line-number --fixed-strings 'semgrep login' "$REPO_ROOT/.stateguard" 2>/dev/null; then
  echo "Found semgrep login in StateGuard configuration." >&2
  exit 1
fi

if grep -R --line-number -E -- '--config[= ](p/|r/|auto)' "$REPO_ROOT/.stateguard" 2>/dev/null; then
  echo "Found a remote Semgrep registry configuration." >&2
  exit 1
fi

echo "Offline preflight passed. Use scripts/run-semgrep.sh, which starts the scanner with --network none."
