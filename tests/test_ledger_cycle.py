from __future__ import annotations

import json
from pathlib import Path

from stateguard.bootstrap import initialize_project
from stateguard.config import load_config
from stateguard.db import Ledger
from stateguard.findings import FindingInput, set_finding_status, upsert_finding
from stateguard.prompt import generate_fix_prompt
from stateguard.review import claim_next_unit, complete_unit
from stateguard.sarif import export_sarif, import_sarif
from stateguard.scanner import autoplan_review_units, scan_repository
from stateguard.status import doctor


def _make_repo(tmp_path: Path) -> tuple[Path, Ledger]:
    repo = tmp_path / "product"
    (repo / "server").mkdir(parents=True)
    (repo / "client").mkdir()
    (repo / "server" / "orders.js").write_text(
        "export function submit(order) { return {...order, status: 'submitted'}; }\n",
        encoding="utf-8",
    )
    (repo / "client" / "store.js").write_text(
        "export const state = { kind: 'ready' };\n", encoding="utf-8"
    )
    initialize_project(repo, "product", "Product")
    ledger = Ledger(repo)
    return repo, ledger


def test_resumable_review_and_hash_invalidation(tmp_path: Path) -> None:
    repo, ledger = _make_repo(tmp_path)
    config = load_config(repo)

    first = scan_repository(repo, config, ledger)
    assert first.added >= 2
    plan = autoplan_review_units(repo, config, ledger)
    assert plan["created"] >= 2

    claim = claim_next_unit(ledger, "worker-a", 10)
    assert claim is not None
    assert claim["status"] == "claimed"
    complete_unit(ledger, claim["unit_key"], "worker-a", "completed", "reviewed")

    with ledger.connect() as connection:
        rows = connection.execute(
            """
            SELECT a.path, a.review_status
            FROM artifacts a
            JOIN review_unit_artifacts rua ON rua.artifact_path=a.path
            JOIN review_units ru ON ru.id=rua.unit_id
            WHERE ru.unit_key=?
            """,
            (claim["unit_key"],),
        ).fetchall()
    assert rows
    assert all(row["review_status"] == "reviewed" for row in rows)

    changed = repo / rows[0]["path"]
    changed.write_text(changed.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
    second = scan_repository(repo, config, ledger)
    assert second.changed == 1
    assert second.stale_units >= 1

    with ledger.connect() as connection:
        unit = connection.execute(
            "SELECT status FROM review_units WHERE unit_key=?", (claim["unit_key"],)
        ).fetchone()
        artifact = connection.execute(
            "SELECT review_status FROM artifacts WHERE path=?", (rows[0]["path"],)
        ).fetchone()
    assert unit["status"] == "stale"
    assert artifact["review_status"] == "stale"


def test_sarif_roundtrip_and_fix_prompt(tmp_path: Path) -> None:
    repo, ledger = _make_repo(tmp_path)
    config = load_config(repo)
    scan_repository(repo, config, ledger)

    finding_id = upsert_finding(
        ledger,
        FindingInput(
            source_tool="manual-review",
            rule_id="SG-TX-001",
            title="Неатомарный переход",
            message="Две связанные записи выполняются без общей транзакции.",
            severity="high",
            file_path="server/orders.js",
            start_line=1,
            counterexample="Первая запись фиксируется, вторая завершается ошибкой.",
            remediation="Выполнить обе записи в одной транзакции.",
            verification="Интеграционный тест отката второй записи.",
        ),
    )
    assert finding_id > 0

    sarif_path = repo / ".stateguard" / "results" / "stateguard.sarif"
    assert export_sarif(ledger, sarif_path) == 1
    payload = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"][0]["ruleId"] == "SG-TX-001"

    imported = import_sarif(ledger, sarif_path)
    assert imported["imported"] == 1

    prompt_path = repo / ".stateguard" / "reports" / "fix-prompt.md"
    assert generate_fix_prompt(ledger, prompt_path) >= 1
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "Неатомарный переход" in prompt
    assert "doctor --strict" in prompt

    check = doctor(ledger, strict=True)
    assert not check.ok
    assert any("high findings" in failure for failure in check.failures)

    set_finding_status(ledger, finding_id, "closed")


def test_expired_claim_can_be_reclaimed(tmp_path: Path) -> None:
    repo, ledger = _make_repo(tmp_path)
    config = load_config(repo)
    scan_repository(repo, config, ledger)
    autoplan_review_units(repo, config, ledger)

    first = claim_next_unit(ledger, "worker-a", 10)
    assert first is not None
    with ledger.transaction(immediate=True) as connection:
        connection.execute(
            "UPDATE review_units SET lease_until='2000-01-01T00:00:00+00:00' WHERE unit_key=?",
            (first["unit_key"],),
        )

    second = claim_next_unit(ledger, "worker-b", 10)
    assert second is not None
    assert second["claimed_by"] == "worker-b"
