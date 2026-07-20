from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .db import Ledger
from .errors import StateGuardError
from .util import sha256_file, stable_hash, utc_now


ALLOWED_PROOF_STATUS = {
    "pending",
    "running",
    "proved",
    "verified",
    "reviewed-ai",
    "failed",
    "inconclusive",
    "waived",
    "stale",
}


def record_proof(
    ledger: Ledger,
    *,
    obligation_key: str,
    kind: str,
    title: str,
    description: str,
    status: str,
    solver: str,
    criticality: str = "medium",
    specification_hash: str | None = None,
    input_paths: Iterable[Path] = (),
    command: str | None = None,
    result_summary: str | None = None,
    counterexample: str | None = None,
    evidence: dict | None = None,
    audit_run_id: int | None = None,
    tool_version: str | None = None,
) -> int:
    if status not in ALLOWED_PROOF_STATUS:
        raise StateGuardError(f"Недопустимый proof status: {status}")

    now = utc_now()
    inputs: list[tuple[str, str]] = []
    for path in input_paths:
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            raise StateGuardError(f"Proof input не найден: {path}")
        try:
            normalized = resolved.relative_to(ledger.repo_root).as_posix()
        except ValueError:
            # External specifications and solver inputs are allowed, but they cannot
            # participate in artifact-driven invalidation until imported into the repo.
            normalized = resolved.as_posix()
        inputs.append((normalized, sha256_file(resolved)))
    input_hash = stable_hash(inputs)

    with ledger.transaction(immediate=True) as connection:
        existing = connection.execute(
            "SELECT id FROM proof_obligations WHERE obligation_key=?",
            (obligation_key,),
        ).fetchone()
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO proof_obligations(
                    obligation_key, kind, title, description, criticality, status,
                    solver, specification_hash, input_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obligation_key,
                    kind,
                    title,
                    description,
                    criticality,
                    status,
                    solver,
                    specification_hash,
                    input_hash,
                    now,
                    now,
                ),
            )
            obligation_id = int(cursor.lastrowid)
        else:
            obligation_id = int(existing["id"])
            connection.execute(
                """
                UPDATE proof_obligations
                SET kind=?, title=?, description=?, criticality=?, status=?, solver=?,
                    specification_hash=?, input_hash=?, updated_at=?
                WHERE id=?
                """,
                (
                    kind,
                    title,
                    description,
                    criticality,
                    status,
                    solver,
                    specification_hash,
                    input_hash,
                    now,
                    obligation_id,
                ),
            )
            connection.execute(
                "DELETE FROM proof_inputs WHERE obligation_id=?", (obligation_id,)
            )

        for path, digest in inputs:
            artifact = connection.execute(
                "SELECT path FROM artifacts WHERE path=?", (path,)
            ).fetchone()
            if artifact:
                connection.execute(
                    """
                    INSERT INTO proof_inputs(obligation_id, artifact_path, artifact_sha256)
                    VALUES (?, ?, ?)
                    """,
                    (obligation_id, path, digest),
                )

        cursor = connection.execute(
            """
            INSERT INTO proof_attempts(
                obligation_id, audit_run_id, status, solver, tool_version, command,
                result_summary, counterexample, evidence_json, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obligation_id,
                audit_run_id,
                status,
                solver,
                tool_version,
                command,
                result_summary,
                counterexample,
                json.dumps(evidence or {}, ensure_ascii=False),
                now,
                now,
            ),
        )
        attempt_id = int(cursor.lastrowid)
        connection.execute(
            "UPDATE proof_obligations SET last_attempt_id=? WHERE id=?",
            (attempt_id, obligation_id),
        )
        return obligation_id
