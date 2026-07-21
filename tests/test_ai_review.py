from __future__ import annotations

import json
from pathlib import Path

import pytest

from stateguard.ai_review import run_ai_review
from stateguard.bootstrap import initialize_project
from stateguard.db import Ledger
from stateguard.findings import FindingInput, upsert_finding

SPEC = """version: 1
project: repo

entities: []
states: []
invariants:
  - id: INV-A
    title: A holds
    criticality: high
    predicate: 'always true'
commands: []
observations: []
external_effects: []
"""


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def _fake_urlopen_returning(content: dict | str):
    body = content if isinstance(content, str) else json.dumps(content)

    def fake(request, timeout=60):  # noqa: ARG001 - matches urlopen's call signature
        wire = json.dumps({"choices": [{"message": {"content": body}}]}).encode("utf-8")
        return _FakeResponse(wire)

    return fake


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    (repo / ".stateguard" / "specification.yaml").write_text(SPEC, encoding="utf-8")
    (repo / "server").mkdir()
    (repo / "server" / "x.js").write_text("\n".join(f"line {i}" for i in range(1, 30)), encoding="utf-8")
    return repo


def test_skips_without_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repo = _init_repo(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()

    result = run_ai_review(ledger, repo, repo / ".stateguard" / "specification.yaml")

    assert result == {"status": "skipped", "reason": "DEEPSEEK_API_KEY not set"}
    with ledger.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM proof_obligations").fetchone()[0] == 0


def test_reviews_finding_fills_empty_fields_but_preserves_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    repo = _init_repo(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()

    finding_id = upsert_finding(
        ledger,
        FindingInput(
            source_tool="semgrep",
            rule_id="SG-001",
            title="Possible lost update",
            message="Write is not guarded by version check",
            severity="high",
            file_path="server/x.js",
            start_line=10,
            invariant_id="INV-A",
            root_cause="Pre-existing human-entered root cause",
        ),
    )

    ai_payload = {
        "classification": "confirmed-defect",
        "reasoning_summary": "The write bypasses the version guard.",
        "counterexample": "Two concurrent calls both pass the guard.",
        "evidence_refs": ["server/x.js:10"],
        "specification_gaps": [],
        "recommended_checks": ["Add a regression test."],
        "safe_mechanism": None,
        "finding_proposal": {
            "root_cause": "AI-proposed root cause (should NOT overwrite existing)",
            "impact": "Lost update under concurrency.",
            "remediation": "Add version check to UPDATE.",
            "verification": "Add a concurrent regression test.",
        },
    }
    monkeypatch.setattr(
        "stateguard.ai_review.urllib.request.urlopen", _fake_urlopen_returning(ai_payload)
    )

    result = run_ai_review(ledger, repo, repo / ".stateguard" / "specification.yaml")

    assert result["errors"] == []
    assert result["reviewed"] == [{"finding_id": finding_id, "classification": "confirmed-defect"}]

    with ledger.connect() as connection:
        obligation = connection.execute(
            "SELECT status, criticality, solver FROM proof_obligations WHERE obligation_key=?",
            (f"AI-REVIEW-FINDING-{finding_id}",),
        ).fetchone()
        finding = connection.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()

    assert obligation["status"] == "reviewed-ai"
    assert obligation["criticality"] == "high"
    assert obligation["solver"] == "deepseek:deepseek-chat"
    assert finding["status"] == "in-review"
    # Existing field is preserved, not clobbered by the AI's proposal.
    assert finding["root_cause"] == "Pre-existing human-entered root cause"
    # Empty field is filled from the AI's proposal.
    assert finding["impact"] == "Lost update under concurrency."


def test_schema_invalid_response_is_reported_as_error_not_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    repo = _init_repo(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()

    finding_id = upsert_finding(
        ledger,
        FindingInput(source_tool="semgrep", rule_id="SG-001", title="X", message="Y", severity="low"),
    )
    # Missing the required "classification" field.
    monkeypatch.setattr(
        "stateguard.ai_review.urllib.request.urlopen",
        _fake_urlopen_returning({"reasoning_summary": "oops", "evidence_refs": []}),
    )

    result = run_ai_review(ledger, repo, repo / ".stateguard" / "specification.yaml")

    assert result["reviewed"] == []
    assert len(result["errors"]) == 1
    assert result["errors"][0]["finding_id"] == finding_id
    with ledger.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM proof_obligations").fetchone()[0] == 0
        status = connection.execute("SELECT status FROM findings WHERE id=?", (finding_id,)).fetchone()["status"]
    assert status == "open"
