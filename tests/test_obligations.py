from __future__ import annotations

from pathlib import Path

from stateguard.bootstrap import initialize_project
from stateguard.config import load_config
from stateguard.db import Ledger
from stateguard.obligations import generate_invariant_preservation_obligations


SPEC = """version: 1
project: repo

entities: []
states: []
invariants:
  - id: INV-A
    title: A holds
    criticality: critical
  - id: INV-B
    title: B holds
    criticality: high
commands:
  - id: CMD-X
    title: Do X
    preserves: [INV-A, INV-B]
observations: []
external_effects: []
"""

MAPPINGS = """version: 1
project: repo

components: []
entities: []
invariants: []
commands: []
observations: []
framework_adapters: []
"""


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    (repo / ".stateguard" / "specification.yaml").write_text(SPEC, encoding="utf-8")
    (repo / ".stateguard" / "mappings.yaml").write_text(MAPPINGS, encoding="utf-8")
    return repo


def test_generates_one_obligation_per_command_invariant_pair(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    config = load_config(repo)

    keys = generate_invariant_preservation_obligations(repo, config, ledger)

    assert sorted(keys) == ["PO-INV-A-BY-CMD-X", "PO-INV-B-BY-CMD-X"]
    with ledger.connect() as connection:
        rows = {
            row["obligation_key"]: row["criticality"]
            for row in connection.execute(
                "SELECT obligation_key, criticality FROM proof_obligations"
            ).fetchall()
        }
    assert rows == {"PO-INV-A-BY-CMD-X": "critical", "PO-INV-B-BY-CMD-X": "high"}


def test_is_idempotent_across_repeated_calls(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    config = load_config(repo)

    generate_invariant_preservation_obligations(repo, config, ledger)
    generate_invariant_preservation_obligations(repo, config, ledger)

    with ledger.connect() as connection:
        count = connection.execute("SELECT COUNT(*) FROM proof_obligations").fetchone()[0]
    assert count == 2
