from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .db import Ledger
from .errors import StateGuardError
from .util import sha256_text, stable_json, utc_now


SEVERITIES = {"critical", "high", "medium", "low", "info"}
STATUSES = {
    "open",
    "stale",
    "in-review",
    "fixed-pending-verification",
    "closed",
    "accepted-risk",
    "false-positive",
    "deferred",
}


@dataclass(slots=True)
class FindingInput:
    source_tool: str
    rule_id: str
    title: str
    message: str
    severity: str
    file_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    confidence: str = "medium"
    category: str = "implementation-defect"
    invariant_id: str | None = None
    transition_id: str | None = None
    counterexample: str | None = None
    impact: str | None = None
    root_cause: str | None = None
    remediation: str | None = None
    verification: str | None = None
    external_key: str | None = None

    def normalized_severity(self) -> str:
        severity = self.severity.lower().strip()
        aliases = {
            "error": "high",
            "warning": "medium",
            "warn": "medium",
            "note": "low",
            "none": "info",
            "blocker": "critical",
            "major": "high",
            "minor": "low",
        }
        severity = aliases.get(severity, severity)
        return severity if severity in SEVERITIES else "medium"

    def key(self) -> str:
        if self.external_key:
            return self.external_key
        identity = {
            "tool": self.source_tool,
            "rule": self.rule_id,
            "path": self.file_path,
            "line": self.start_line,
            "column": self.start_column,
            "message": self.message,
        }
        return f"{self.source_tool}:{sha256_text(stable_json(identity))}"


def upsert_finding(
    ledger: Ledger,
    finding: FindingInput,
    *,
    run_id: int | None = None,
) -> int:
    now = utc_now()
    artifact_sha = None
    with ledger.transaction(immediate=True) as connection:
        if finding.file_path:
            row = connection.execute(
                "SELECT sha256 FROM artifacts WHERE path=? AND deleted=0",
                (finding.file_path,),
            ).fetchone()
            artifact_sha = row["sha256"] if row else None

        key = finding.key()
        existing = connection.execute(
            "SELECT id, status FROM findings WHERE external_key=?", (key,)
        ).fetchone()
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO findings(
                    external_key, source_tool, rule_id, title, message, severity,
                    confidence, category, status, file_path, start_line, start_column,
                    end_line, end_column, artifact_sha256, invariant_id, transition_id,
                    counterexample, impact, root_cause, remediation, verification,
                    first_seen_run_id, last_seen_run_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    finding.source_tool,
                    finding.rule_id,
                    finding.title,
                    finding.message,
                    finding.normalized_severity(),
                    finding.confidence,
                    finding.category,
                    finding.file_path,
                    finding.start_line,
                    finding.start_column,
                    finding.end_line,
                    finding.end_column,
                    artifact_sha,
                    finding.invariant_id,
                    finding.transition_id,
                    finding.counterexample,
                    finding.impact,
                    finding.root_cause,
                    finding.remediation,
                    finding.verification,
                    run_id,
                    run_id,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

        next_status = existing["status"]
        if next_status in {"closed", "false-positive"}:
            next_status = "open"
        connection.execute(
            """
            UPDATE findings
            SET source_tool=?, rule_id=?, title=?, message=?, severity=?, confidence=?,
                category=?, status=?, file_path=?, start_line=?, start_column=?, end_line=?,
                end_column=?, artifact_sha256=?, invariant_id=?, transition_id=?,
                counterexample=?, impact=?, root_cause=?, remediation=?, verification=?,
                last_seen_run_id=?, updated_at=?
            WHERE external_key=?
            """,
            (
                finding.source_tool,
                finding.rule_id,
                finding.title,
                finding.message,
                finding.normalized_severity(),
                finding.confidence,
                finding.category,
                next_status,
                finding.file_path,
                finding.start_line,
                finding.start_column,
                finding.end_line,
                finding.end_column,
                artifact_sha,
                finding.invariant_id,
                finding.transition_id,
                finding.counterexample,
                finding.impact,
                finding.root_cause,
                finding.remediation,
                finding.verification,
                run_id,
                now,
                key,
            ),
        )
        return int(existing["id"])


def set_finding_status(ledger: Ledger, finding_id: int, status: str) -> None:
    if status not in STATUSES:
        raise StateGuardError(f"Недопустимый finding status: {status}")
    with ledger.transaction(immediate=True) as connection:
        cursor = connection.execute(
            "UPDATE findings SET status=?, updated_at=? WHERE id=?",
            (status, utc_now(), finding_id),
        )
        if cursor.rowcount == 0:
            raise StateGuardError(f"Finding не найден: {finding_id}")


def list_open_findings(ledger: Ledger) -> list[dict[str, Any]]:
    with ledger.connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM findings
            WHERE status NOT IN ('closed', 'false-positive', 'accepted-risk')
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END,
                id
            """
        ).fetchall()
        return [dict(row) for row in rows]
