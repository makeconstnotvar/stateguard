from __future__ import annotations

from pathlib import Path

from stateguard.bootstrap import initialize_project
from stateguard.config import load_config
from stateguard.db import Ledger
from stateguard.proofs import record_proof
from stateguard.scanner import scan_repository


def test_proof_input_uses_repo_relative_artifact_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "domain.js"
    source.write_text("export const state = 'draft';\n", encoding="utf-8")
    initialize_project(repo, "repo", "Repo")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    obligation_id = record_proof(
        ledger,
        obligation_key="PO-STATE-001",
        kind="invariant-preservation",
        title="Состояние допустимо",
        description="Переход сохраняет допустимость состояния.",
        status="proved",
        solver="unit-test",
        input_paths=[source],
    )
    with ledger.connect() as connection:
        proof_input = connection.execute(
            "SELECT artifact_path FROM proof_inputs WHERE obligation_id=?", (obligation_id,)
        ).fetchone()
    assert proof_input["artifact_path"] == "domain.js"
