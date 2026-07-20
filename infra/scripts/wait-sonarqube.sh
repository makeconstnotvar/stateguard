#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INFRA_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck disable=SC1091
set -a; source "$INFRA_DIR/.env"; set +a
URL="http://${SONAR_BIND_ADDRESS:-127.0.0.1}:${SONAR_PORT:-9000}/api/system/status"

for _ in $(seq 1 120); do
  if response=$(curl --fail --silent --show-error "$URL" 2>/dev/null); then
    if printf '%s' "$response" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"(UP|DB_MIGRATION_NEEDED|DB_MIGRATION_RUNNING)"'; then
      echo "SonarQube: $response"
      exit 0
    fi
  fi
  sleep 5
done

echo "SonarQube did not become ready. Inspect logs:" >&2
echo "  docker compose --env-file '$INFRA_DIR/.env' -f '$INFRA_DIR/docker-compose.sonarqube.yml' logs sonarqube" >&2
exit 1
