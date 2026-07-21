#!/usr/bin/env bash
# Runs the project's node:test suite (testcontainers-backed concurrency/constraint
# tests) and records each result as proof evidence via `stateguard
# record-test-evidence`, matched to PO-* obligations through the project's own
# mappings.yaml (see src/stateguard/test_evidence.py — nothing here is
# order-workflow-specific). Requires Docker; other stacks' concurrency suites should
# get their own script following this same shape (run suite -> capture structured
# result -> stateguard record-test-evidence / proof-record).
set -euo pipefail
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
cd "$REPO_ROOT"

command -v docker >/dev/null 2>&1 || {
  echo "run-database-concurrency-suite.sh: docker not installed; testcontainers cannot start" >&2
  exit 2
}

if [ ! -d tests ] || [ -z "$(find tests -maxdepth 1 -name '*.test.js' -print -quit 2>/dev/null)" ]; then
  echo "run-database-concurrency-suite.sh: no tests/*.test.js found — nothing to do" >&2
  exit 0
fi

if [ ! -d node_modules ]; then npm ci --no-audit --no-fund || npm install --no-audit --no-fund; fi

TAP_FILE=$(mktemp)
trap 'rm -f "$TAP_FILE"' EXIT

test_files=(tests/*.test.js)
TEST_STATUS=0
node --test --test-reporter=tap --test-reporter-destination="$TAP_FILE" "${test_files[@]}" || TEST_STATUS=$?

test_file_args=()
for f in "${test_files[@]}"; do test_file_args+=(--test-file "$f"); done
stateguard --repo "$REPO_ROOT" record-test-evidence --tap-file "$TAP_FILE" "${test_file_args[@]}"

exit "$TEST_STATUS"
