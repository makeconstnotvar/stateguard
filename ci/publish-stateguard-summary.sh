#!/usr/bin/env bash
# Builds a control-plane/openapi.yaml CreateRun payload from the local ledger and
# posts it to POST /v1/runs when STATEGUARD_CONTROL_URL + STATEGUARD_CONTROL_TOKEN are
# set (same env var names as control-plane/publish-example.sh). The control plane is
# not implemented as a running service yet (control-plane/README.md) — this script is
# honest about that: it always writes the payload locally so it's inspectable, and
# only attempts the HTTP call when a real endpoint is configured. Uploading findings/
# proofs (PUT /v1/runs/{id}/findings|proofs) and completing the run (POST .../complete)
# are natural follow-ups once createRun has been validated against a real server —
# deliberately not built speculatively against an endpoint that has never been run.
set -euo pipefail
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
RUN_TYPE=${STATEGUARD_RUN_TYPE:-manual}
OUT_DIR="$REPO_ROOT/.stateguard/reports"
mkdir -p "$OUT_DIR"
PAYLOAD="$OUT_DIR/control-plane-run.json"

COMMIT_SHA=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")

python3 - "$REPO_ROOT" "$COMMIT_SHA" "$RUN_TYPE" "$PAYLOAD" <<'PY'
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

repo_root, commit_sha, run_type, out_path = sys.argv[1:5]
repo_root = Path(repo_root)

config = yaml.safe_load((repo_root / ".stateguard" / "stateguard.yaml").read_text(encoding="utf-8")) or {}
project_key = (config.get("project") or {}).get("key") or repo_root.name
spec = config.get("specification") or {}

def sha256_file(path):
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()

policy_sha256 = sha256_file(repo_root / ".stateguard" / "stateguard.yaml") or hashlib.sha256(b"").hexdigest()
spec_sha256 = sha256_file(repo_root / spec.get("file", ".stateguard/specification.yaml"))
mappings_sha256 = sha256_file(repo_root / spec.get("mappings", ".stateguard/mappings.yaml"))

db_path = repo_root / ".stateguard" / "audit.db"
started_at = datetime.now(UTC).isoformat(timespec="seconds")
manifest_sha256 = hashlib.sha256(b"").hexdigest()
if db_path.exists():
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    run = connection.execute(
        "SELECT started_at FROM audit_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if run:
        started_at = run["started_at"]
    manifest_rows = connection.execute(
        "SELECT path, sha256 FROM artifacts WHERE deleted=0 ORDER BY path"
    ).fetchall()
    manifest_json = json.dumps(
        [[row["path"], row["sha256"]] for row in manifest_rows], separators=(",", ":")
    )
    manifest_sha256 = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    connection.close()

payload = {
    "repositoryKey": project_key,
    "idempotencyKey": hashlib.sha256(f"{commit_sha}:{policy_sha256}".encode()).hexdigest(),
    "runType": run_type,
    "commitSha": commit_sha,
    "policySha256": policy_sha256,
    "specificationSha256": spec_sha256,
    "mappingsSha256": mappings_sha256,
    "sourceManifestSha256": manifest_sha256,
    "toolchain": {"stateguard": "0.1.0"},
    "startedAt": started_at,
}
Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out_path}")
PY

if [ -n "${STATEGUARD_CONTROL_URL:-}" ] && [ -n "${STATEGUARD_CONTROL_TOKEN:-}" ]; then
  echo "Publishing to $STATEGUARD_CONTROL_URL/v1/runs"
  curl --fail --silent --show-error \
    --header "Authorization: Bearer $STATEGUARD_CONTROL_TOKEN" \
    --header "Content-Type: application/json" \
    --data-binary "@$PAYLOAD" \
    "$STATEGUARD_CONTROL_URL/v1/runs"
else
  echo "publish-stateguard-summary.sh: STATEGUARD_CONTROL_URL/STATEGUARD_CONTROL_TOKEN not set — payload written locally, not published. See control-plane/README.md." >&2
fi
