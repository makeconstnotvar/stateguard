#!/usr/bin/env bash
set -euo pipefail

: "${SONAR_HOST_URL:?Set SONAR_HOST_URL}"
: "${SONAR_ADMIN_TOKEN:?Set SONAR_ADMIN_TOKEN}"
PROJECT_KEY=${1:?Usage: provision-project.sh PROJECT_KEY [PROJECT_NAME]}
PROJECT_NAME=${2:-$PROJECT_KEY}

curl --fail --silent --show-error \
  --user "$SONAR_ADMIN_TOKEN:" \
  --request POST "$SONAR_HOST_URL/api/projects/create" \
  --data-urlencode "project=$PROJECT_KEY" \
  --data-urlencode "name=$PROJECT_NAME"

echo
echo "Project $PROJECT_KEY created. Create a project-analysis token in the SonarQube UI or your approved secrets workflow."
