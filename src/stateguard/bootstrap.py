from __future__ import annotations

from pathlib import Path

from .db import Ledger
from .errors import StateGuardError
from .util import atomic_write, slugify


CONFIG_TEMPLATE = """project:
  key: {project_key}
  name: {project_name}

scanning:
  source_roots:
    - .
  excludes:
    - .git
    - .stateguard
    - node_modules
    - vendor
    - dist
    - build
    - coverage
    - target
  generated_paths:
    - '**/generated/**'
    - '**/*.generated.*'

review:
  max_files_per_unit: 80
  critical_paths:
    - '**/migrations/**'
    - '**/db/**'
    - '**/payments/**'
    - '**/authorization/**'

specification:
  file: .stateguard/specification.yaml
  mappings: .stateguard/mappings.yaml

integrations:
  sonarqube:
    project_key: {project_key}
  semgrep:
    report: .stateguard/results/semgrep.sarif
  joern:
    output: .stateguard/results/joern
"""

SPEC_TEMPLATE = """version: 1
project: {project_key}

scope:
  product_type: business-application
  assumptions:
    - Supported runtime, database and framework behave according to their documented contracts.
    - Infrastructure outages and hardware faults are outside this specification unless listed explicitly.

entities: []
states: []
invariants: []
commands: []
observations: []
external_effects: []
"""

MAPPINGS_TEMPLATE = """version: 1
project: {project_key}

components: []
entities: []
invariants: []
commands: []
observations: []
framework_adapters: []
"""

GITIGNORE_TEMPLATE = """audit.db
audit.db-shm
audit.db-wal
results/
reports/
cache/
work/
rules/
"""


def initialize_project(repo_root: Path, project_key: str | None, project_name: str | None) -> dict:
    repo_root = repo_root.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise StateGuardError(f"Каталог проекта не найден: {repo_root}")

    key = slugify(project_key or repo_root.name)
    name = project_name or repo_root.name
    state = repo_root / ".stateguard"
    created: list[str] = []
    for directory in [state, state / "results", state / "reports", state / "rules", state / "work"]:
        directory.mkdir(parents=True, exist_ok=True)

    templates = {
        state / "stateguard.yaml": CONFIG_TEMPLATE.format(project_key=key, project_name=name),
        state / "specification.yaml": SPEC_TEMPLATE.format(project_key=key),
        state / "mappings.yaml": MAPPINGS_TEMPLATE.format(project_key=key),
        state / ".gitignore": GITIGNORE_TEMPLATE,
    }
    for path, content in templates.items():
        if not path.exists():
            atomic_write(path, content)
            created.append(path.relative_to(repo_root).as_posix())

    ledger = Ledger(repo_root)
    ledger.initialize()
    return {"project_key": key, "state_dir": str(state), "created": created}
