#!/usr/bin/env bash
# Starter template — PR-fast tier: native compiler/linter + genuinely fast unit tests
# (docker/testcontainers-backed suites belong in run-database-concurrency-suite.sh, not
# here). Detects a handful of common stacks; adapt/extend per project, same spirit as
# config/semgrep/rules being starter rules rather than a universal ruleset.
set -euo pipefail
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)
cd "$REPO_ROOT"

ran_any=0

if [ -f package.json ]; then
  ran_any=1
  echo "== Node: native checks =="
  if [ ! -d node_modules ]; then npm ci --no-audit --no-fund || npm install --no-audit --no-fund; fi
  if node -e "process.exit(require('./package.json').scripts && require('./package.json').scripts.lint ? 0 : 1)"; then
    npm run lint
  else
    echo "no npm 'lint' script defined — running node --check on tracked .js files as a minimal native check"
    git ls-files '*.js' '*.mjs' '*.cjs' | xargs -r -n1 node --check
  fi
fi

if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  ran_any=1
  echo "== Python: native checks =="
  python -m compileall -q .
  if command -v ruff >/dev/null 2>&1; then ruff check .; else echo "ruff not installed, skipping lint"; fi
fi

if [ -f pom.xml ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
  ran_any=1
  echo "== Java: native checks =="
  if [ -f pom.xml ]; then mvn -q -DskipTests compile; else ./gradlew -q compileJava; fi
fi

if [ "$ran_any" -eq 0 ]; then
  echo "project-fast-checks.sh: no recognized stack (package.json/pyproject.toml/pom.xml/build.gradle) — nothing to do" >&2
fi
