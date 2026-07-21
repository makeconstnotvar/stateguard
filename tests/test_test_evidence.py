from __future__ import annotations

from pathlib import Path

import yaml

from stateguard.bootstrap import initialize_project
from stateguard.db import Ledger
from stateguard.test_evidence import (
    TapResult,
    map_test_results_to_obligations,
    parse_tap,
    record_test_evidence,
)

REAL_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "order-workflow"

# Captured verbatim from a real `node --test --test-reporter=tap
# --test-reporter-destination=stdout` run under Node 24 (one passing, one failing test),
# confirming the parser handles Node's genuine TAP13 YAML diagnostic blocks, not a
# guessed format.
REAL_TAP_CAPTURE = """TAP version 13
# Subtest: passing test one
ok 1 - passing test one
  ---
  duration_ms: 0.553417
  type: 'test'
  ...
# Subtest: failing test with a diagnostic
not ok 2 - failing test with a diagnostic
  ---
  duration_ms: 0.580208
  type: 'test'
  location: '/tmp/tap-experiment.test.js:8:1'
  failureType: 'testCodeFailure'
  error: |-
    one is not two

    1 !== 2
  code: 'ERR_ASSERTION'
  name: 'AssertionError'
  expected: 2
  actual: 1
  operator: 'strictEqual'
  ...
1..2
# tests 2
# suites 0
# pass 1
# fail 1
"""


def test_parse_tap_extracts_ok_and_not_ok_with_yaml_diagnostics() -> None:
    results = parse_tap(REAL_TAP_CAPTURE)
    assert [r.title for r in results] == ["passing test one", "failing test with a diagnostic"]
    assert results[0].ok is True
    assert results[0].failure_detail is None
    assert results[1].ok is False
    assert "one is not two" in results[1].failure_detail


def test_map_test_results_derives_obligations_from_real_order_workflow_mapping() -> None:
    specification = yaml.safe_load((REAL_EXAMPLE / "specification.yaml").read_text(encoding="utf-8"))
    mapping = yaml.safe_load((REAL_EXAMPLE / "mappings.yaml").read_text(encoding="utf-8"))
    results = [
        TapResult(title="two concurrent submissions yield exactly one accepted transition", ok=True),
        TapResult(title="deferred database invariant rejects a paid order with rejected payment", ok=True),
    ]
    evidence = map_test_results_to_obligations(results, specification, mapping)
    keys = {item.obligation_key: item.criticality for item in evidence}
    assert keys == {
        "PO-INV-ORDER-002-BY-CMD-ORDER-SUBMIT": "high",
        "PO-INV-ORDER-003-BY-CMD-ORDER-SUBMIT": "high",
        "PO-INV-ORDER-001-BY-CMD-ORDER-MARK-PAID": "critical",
    }


def test_record_test_evidence_writes_verified_and_failed_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")

    spec_path = repo / "specification.yaml"
    spec_path.write_text(
        "version: 1\nproject: repo\nentities: []\nstates: []\n"
        "invariants:\n"
        "  - id: INV-A\n    title: A holds\n    criticality: critical\n"
        "commands:\n"
        "  - id: CMD-X\n    title: Do X\n    preserves: [INV-A]\n"
        "observations: []\nexternal_effects: []\n",
        encoding="utf-8",
    )
    mapping_path = repo / "mappings.yaml"
    mapping_path.write_text(
        "version: 1\nproject: repo\ncomponents: []\nentities: []\ninvariants: []\n"
        "commands:\n"
        "  - id: CMD-X\n    locations:\n"
        "      - kind: test\n        selector: X behaves\n        path: tests/x.test.js\n"
        "observations: []\nframework_adapters: []\n",
        encoding="utf-8",
    )
    test_file = repo / "tests" / "x.test.js"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("// placeholder\n", encoding="utf-8")

    ledger = Ledger(repo)
    ledger.initialize()

    tap_text = "ok 1 - X behaves\n  ---\n  duration_ms: 1\n  ...\n1..1\n"
    recorded = record_test_evidence(ledger, spec_path, mapping_path, tap_text, [test_file])
    assert recorded == {"PO-INV-A-BY-CMD-X": "verified"}
    with ledger.connect() as connection:
        row = connection.execute(
            "SELECT status, criticality, solver FROM proof_obligations WHERE obligation_key=?",
            ("PO-INV-A-BY-CMD-X",),
        ).fetchone()
    assert row["status"] == "verified"
    assert row["criticality"] == "critical"
    assert row["solver"] == "node:test+testcontainers"

    failing_tap = "not ok 1 - X behaves\n  ---\n  error: |-\n    boom\n  ...\n1..1\n"
    recorded = record_test_evidence(ledger, spec_path, mapping_path, failing_tap, [test_file])
    assert recorded == {"PO-INV-A-BY-CMD-X": "failed"}
    with ledger.connect() as connection:
        row = connection.execute(
            """
            SELECT o.status, a.counterexample
            FROM proof_obligations o JOIN proof_attempts a ON a.id = o.last_attempt_id
            WHERE o.obligation_key=?
            """,
            ("PO-INV-A-BY-CMD-X",),
        ).fetchone()
    assert row["status"] == "failed"
    assert "boom" in row["counterexample"]
