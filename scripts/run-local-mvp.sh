#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)

stateguard --repo "$REPO_ROOT" scan
stateguard --repo "$REPO_ROOT" autoplan
"$(dirname "$0")/run-semgrep.sh" "$REPO_ROOT"
stateguard --repo "$REPO_ROOT" import-sarif .stateguard/results/semgrep.sarif
stateguard --repo "$REPO_ROOT" export-sarif
stateguard --repo "$REPO_ROOT" generate-fix-prompt
stateguard --repo "$REPO_ROOT" status
