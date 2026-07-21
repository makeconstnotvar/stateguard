#!/usr/bin/env bash
# Starter template — full project test suite (main branch / pre-merge tier). Runs
# whatever test command each detected stack declares, including docker-backed suites.
# Adapt/extend per project.
set -euo pipefail
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
cd "$REPO_ROOT"

ran_any=0

if [ -f package.json ]; then
  ran_any=1
  echo "== Node: npm test =="
  if [ ! -d node_modules ]; then npm ci --no-audit --no-fund || npm install --no-audit --no-fund; fi
  if node -e "process.exit(require('./package.json').scripts && require('./package.json').scripts.test ? 0 : 1)"; then
    npm test
  else
    echo "no npm 'test' script defined — skipping" >&2
  fi
fi

if [ -f pyproject.toml ]; then
  ran_any=1
  echo "== Python: pytest =="
  python -m pytest -q
fi

if [ -f pom.xml ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
  ran_any=1
  echo "== Java: test =="
  if [ -f pom.xml ]; then mvn -q test; else ./gradlew -q test; fi
fi

if [ "$ran_any" -eq 0 ]; then
  echo "project-full-checks.sh: no recognized stack (package.json/pyproject.toml/pom.xml/build.gradle) — nothing to do" >&2
fi
