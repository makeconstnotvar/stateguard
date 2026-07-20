#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
KIT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR="$REPO_ROOT/.stateguard/results/joern"
CPG_FILE="$REPO_ROOT/.stateguard/work/joern.cpg.bin"
mkdir -p "$OUT_DIR" "$(dirname "$CPG_FILE")"

command -v joern-parse >/dev/null || { echo "joern-parse is not installed" >&2; exit 2; }
command -v joern >/dev/null || { echo "joern is not installed" >&2; exit 2; }

rm -f "$CPG_FILE"
joern-parse "$REPO_ROOT" --output "$CPG_FILE"
joern \
  --script "$KIT_ROOT/joern/export_stateguard.sc" \
  --param cpgFile="$CPG_FILE" \
  --param outDir="$OUT_DIR"

echo "Joern extraction: $OUT_DIR"
