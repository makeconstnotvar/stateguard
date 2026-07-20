from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .db import Ledger
from .errors import StateGuardError
from .util import stable_hash, utc_now


def claim_next_unit(ledger: Ledger, worker: str, lease_minutes: int = 60) -> dict | None:
    ledger.initialize()
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="seconds")
    lease_until = (now_dt + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds")

    with ledger.transaction(immediate=True) as connection:
        connection.execute(
            """
            UPDATE review_units
            SET status='stale', claimed_by=NULL, lease_until=NULL, updated_at=?
            WHERE status='claimed' AND lease_until IS NOT NULL AND lease_until < ?
            """,
            (now, now),
        )
        row = connection.execute(
            """
            SELECT id, unit_key, title, component, priority, status, current_hash
            FROM review_units
            WHERE status IN ('pending', 'stale', 'partial', 'failed')
              AND (claimed_by IS NULL OR lease_until IS NULL OR lease_until < ?)
            ORDER BY priority ASC, id ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            """
            UPDATE review_units
            SET status='claimed', claimed_by=?, lease_until=?, updated_at=?
            WHERE id=?
            """,
            (worker, lease_until, now, row["id"]),
        )
        files = connection.execute(
            """
            SELECT a.path, a.sha256, a.kind, a.review_status
            FROM review_unit_artifacts ua
            JOIN artifacts a ON a.path=ua.artifact_path
            WHERE ua.unit_id=? AND a.deleted=0
            ORDER BY a.path
            """,
            (row["id"],),
        ).fetchall()
        return {
            "id": int(row["id"]),
            "unit_key": row["unit_key"],
            "title": row["title"],
            "component": row["component"],
            "priority": int(row["priority"]),
            "status": "claimed",
            "claimed_by": worker,
            "lease_until": lease_until,
            "files": [dict(file) for file in files],
        }


def complete_unit(
    ledger: Ledger,
    unit_key: str,
    worker: str,
    status: str = "completed",
    notes: str | None = None,
) -> dict:
    allowed = {"completed", "partial", "failed"}
    if status not in allowed:
        raise StateGuardError(f"Недопустимый статус {status}; ожидается один из {sorted(allowed)}")

    now = utc_now()
    with ledger.transaction(immediate=True) as connection:
        row = connection.execute(
            "SELECT * FROM review_units WHERE unit_key=?", (unit_key,)
        ).fetchone()
        if row is None:
            raise StateGuardError(f"Review unit не найден: {unit_key}")
        if row["claimed_by"] and row["claimed_by"] != worker:
            raise StateGuardError(
                f"Unit {unit_key} занят worker={row['claimed_by']}, а не {worker}"
            )
        files = connection.execute(
            """
            SELECT a.path, a.sha256
            FROM review_unit_artifacts ua
            JOIN artifacts a ON a.path=ua.artifact_path
            WHERE ua.unit_id=? AND a.deleted=0
            ORDER BY a.path
            """,
            (row["id"],),
        ).fetchall()
        current_hash = stable_hash([(item["path"], item["sha256"]) for item in files])
        reviewed_hash = current_hash if status == "completed" else row["reviewed_hash"]
        connection.execute(
            """
            UPDATE review_units
            SET status=?, current_hash=?, reviewed_hash=?, claimed_by=NULL, lease_until=NULL,
                notes=?, updated_at=?
            WHERE id=?
            """,
            (status, current_hash, reviewed_hash, notes, now, row["id"]),
        )
        if status == "completed":
            connection.executemany(
                """
                UPDATE artifacts
                SET reviewed_sha256=sha256, review_status='reviewed', updated_at=?
                WHERE path=?
                """,
                [(now, item["path"]) for item in files],
            )
        return {
            "unit_key": unit_key,
            "status": status,
            "file_count": len(files),
            "reviewed_hash": reviewed_hash,
        }
