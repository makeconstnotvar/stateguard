#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INFRA_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
docker compose --env-file "$INFRA_DIR/.env" -f "$INFRA_DIR/docker-compose.sonarqube.yml" down
