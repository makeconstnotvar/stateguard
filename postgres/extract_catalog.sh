#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL for a disposable migrated database}"
OUT=${1:-.stateguard/results/postgres-catalog.jsonl}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$(dirname "$OUT")"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -qAt -f "$SCRIPT_DIR/catalog_snapshot.sql" > "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
echo "Catalog snapshot: $OUT"
