from __future__ import annotations

from dataclasses import dataclass, field

from .db import Ledger


@dataclass(slots=True)
class DoctorResult:
    ok: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def collect_status(ledger: Ledger) -> dict:
    ledger.initialize()
    with ledger.connect() as connection:
        artifact_rows = connection.execute(
            """
            SELECT review_status, COUNT(*) AS count
            FROM artifacts WHERE deleted=0 AND generated=0
            GROUP BY review_status
            """
        ).fetchall()
        unit_rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM review_units GROUP BY status"
        ).fetchall()
        finding_rows = connection.execute(
            """
            SELECT status, severity, COUNT(*) AS count
            FROM findings
            GROUP BY status, severity
            """
        ).fetchall()
        proof_rows = connection.execute(
            "SELECT status, criticality, COUNT(*) AS count FROM proof_obligations GROUP BY status, criticality"
        ).fetchall()
        run = connection.execute(
            "SELECT * FROM audit_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return {
        "artifacts": {row["review_status"]: row["count"] for row in artifact_rows},
        "review_units": {row["status"]: row["count"] for row in unit_rows},
        "findings": [dict(row) for row in finding_rows],
        "proofs": [dict(row) for row in proof_rows],
        "last_run": dict(run) if run else None,
    }


def doctor(ledger: Ledger, *, strict: bool = False) -> DoctorResult:
    ledger.initialize()
    result = DoctorResult(ok=True)
    with ledger.connect() as connection:
        queries = {
            "unreviewed_artifacts": """
                SELECT COUNT(*) FROM artifacts
                WHERE deleted=0 AND generated=0 AND review_status <> 'reviewed'
            """,
            "stale_or_incomplete_units": """
                SELECT COUNT(*) FROM review_units
                WHERE status <> 'completed'
            """,
            "expired_claims": """
                SELECT COUNT(*) FROM review_units
                WHERE status='claimed' AND lease_until IS NOT NULL
                  AND lease_until < strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
            """,
            "open_critical_findings": """
                SELECT COUNT(*) FROM findings
                WHERE severity='critical'
                  AND status NOT IN ('closed','false-positive','accepted-risk')
            """,
            "open_high_findings": """
                SELECT COUNT(*) FROM findings
                WHERE severity='high'
                  AND status NOT IN ('closed','false-positive','accepted-risk')
            """,
            "open_other_findings": """
                SELECT COUNT(*) FROM findings
                WHERE severity NOT IN ('critical','high')
                  AND status NOT IN ('closed','false-positive','accepted-risk')
            """,
            "failed_critical_proofs": """
                SELECT COUNT(*) FROM proof_obligations
                WHERE criticality IN ('critical','high')
                  AND status IN ('failed','inconclusive','stale','pending')
            """,
            "reviewed_ai_critical_proofs": """
                SELECT COUNT(*) FROM proof_obligations
                WHERE criticality IN ('critical','high') AND status='reviewed-ai'
            """,
        }
        for key, query in queries.items():
            result.counts[key] = int(connection.execute(query).fetchone()[0])

    hard_failures = [
        ("open_critical_findings", "Остались открытые critical findings"),
        ("open_high_findings", "Остались открытые high findings"),
        ("failed_critical_proofs", "Critical/high proof obligations не закрыты"),
    ]
    strict_failures = [
        ("unreviewed_artifacts", "Есть непросмотренные или изменённые файлы"),
        ("stale_or_incomplete_units", "Есть незавершённые review units"),
        ("expired_claims", "Есть просроченные review claims"),
        ("open_other_findings", "Остались открытые findings средней/низкой критичности"),
        (
            "reviewed_ai_critical_proofs",
            "Critical/high obligations имеют только AI-review, а не проверяемое доказательство",
        ),
    ]

    for key, message in hard_failures:
        if result.counts[key]:
            result.failures.append(f"{message}: {result.counts[key]}")
    for key, message in strict_failures:
        if result.counts[key]:
            destination = result.failures if strict else result.warnings
            destination.append(f"{message}: {result.counts[key]}")

    result.ok = not result.failures
    return result
