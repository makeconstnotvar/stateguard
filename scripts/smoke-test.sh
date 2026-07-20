#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/product/server"
printf '%s\n' "export const status = 'draft';" > "$TMP/product/server/order.js"
export PYTHONPATH="$KIT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -m stateguard.cli --repo "$TMP/product" init --project-key smoke --project-name Smoke
python -m stateguard.cli --repo "$TMP/product" validate
python -m stateguard.cli --repo "$TMP/product" scan
python -m stateguard.cli --repo "$TMP/product" autoplan
python -m stateguard.cli --repo "$TMP/product" claim --worker smoke-worker --lease-minutes 5 > "$TMP/claim.txt"
python -m stateguard.cli --repo "$TMP/product" status

echo 'StateGuard CLI smoke: OK'
