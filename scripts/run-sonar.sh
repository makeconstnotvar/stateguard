#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
: "${SONAR_HOST_URL:?Set SONAR_HOST_URL, e.g. http://sonarqube.internal:9000}"
: "${SONAR_TOKEN:?Set a project-analysis SONAR_TOKEN}"
SONAR_SCANNER_BIN=${SONAR_SCANNER_BIN:-sonar-scanner}

command -v "$SONAR_SCANNER_BIN" >/dev/null || {
  echo "$SONAR_SCANNER_BIN is not installed. Install the scanner approved for your language/build." >&2
  exit 2
}

cd "$REPO_ROOT"
"$SONAR_SCANNER_BIN" \
  -Dsonar.host.url="$SONAR_HOST_URL" \
  -Dsonar.token="$SONAR_TOKEN"
