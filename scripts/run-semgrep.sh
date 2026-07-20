#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
OUT_DIR="$REPO_ROOT/.stateguard/results"
RULES_DIR=${STATEGUARD_SEMGREP_RULES:-"$REPO_ROOT/.stateguard/rules"}
IMAGE=${SEMGREP_IMAGE:-semgrep/semgrep:1.170.0}
mkdir -p "$OUT_DIR"

if [[ ! -d "$RULES_DIR" ]]; then
  echo "Rules directory not found: $RULES_DIR" >&2
  echo "Copy/adapt config/semgrep/rules into .stateguard/rules first." >&2
  exit 2
fi

# The repository and rules are read-only. Only /out is writable. Network is disabled so a scan
# cannot fetch registry rules or send telemetry. HOME points to writable tmpfs.
docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m \
  --env HOME=/tmp \
  --volume "$REPO_ROOT:/src:ro" \
  --volume "$RULES_DIR:/rules:ro" \
  --volume "$OUT_DIR:/out:rw" \
  "$IMAGE" \
  semgrep scan \
    --metrics=off \
    --config /rules \
    --sarif \
    --output /out/semgrep.sarif \
    /src

echo "Semgrep report: $OUT_DIR/semgrep.sarif"
