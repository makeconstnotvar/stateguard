#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INFRA_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE=(docker compose --env-file "$INFRA_DIR/.env" -f "$INFRA_DIR/docker-compose.sonarqube.yml")
# shellcheck disable=SC1091
set -a; source "$INFRA_DIR/.env"; set +a
BACKUP_DIR=${1:-"$INFRA_DIR/backups"}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"
OUTPUT="$BACKUP_DIR/sonarqube-${STAMP}.dump"

restart_sonar() {
  "${COMPOSE[@]}" start sonarqube >/dev/null 2>&1 || true
}
trap restart_sonar EXIT

# Stop compute/web activity so the database backup corresponds to a quiet application state.
"${COMPOSE[@]}" stop sonarqube
"${COMPOSE[@]}" exec -T sonar-db \
  pg_dump --format=custom --no-owner --no-acl \
  --username "${SONAR_DB_USER:-sonar}" "${SONAR_DB_NAME:-sonar}" > "$OUTPUT"

sha256sum "$OUTPUT" > "$OUTPUT.sha256"
echo "Created $OUTPUT"
