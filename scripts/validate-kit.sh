#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$KIT_ROOT"

python - <<'PY'
from pathlib import Path
import json
import yaml

root = Path('.')
for path in root.rglob('*.json'):
    json.loads(path.read_text(encoding='utf-8'))
for path in [*root.rglob('*.yaml'), *root.rglob('*.yml')]:
    yaml.safe_load(path.read_text(encoding='utf-8'))
print('JSON/YAML parse: OK')
PY

python -m compileall -q src tests z3
PYTHONPATH=src python -m pytest -q

for script in $(find . -type f -name '*.sh' -not -path './.git/*'); do
  bash -n "$script"
done

diff -u src/stateguard/schema.sql sql/ledger.sql
for schema in schemas/*.json; do
  diff -u "$schema" "src/stateguard/schemas/$(basename "$schema")"
done

if command -v semgrep >/dev/null 2>&1; then
  semgrep scan --metrics=off --config config/semgrep/rules --validate
else
  echo 'Semgrep not installed: rule syntax runtime validation skipped.'
fi

if command -v docker >/dev/null 2>&1; then
  docker compose -f infra/docker-compose.sonarqube.yml --env-file infra/.env.example config >/dev/null
else
  echo 'Docker not installed: Compose runtime validation skipped.'
fi

echo 'StateGuard implementation kit validation: OK'
