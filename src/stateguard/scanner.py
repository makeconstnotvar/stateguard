from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import ProjectConfig
from .db import Ledger
from .repository import git_commit
from .util import normalize_repo_path, path_matches, sha256_file, stable_hash, utc_now


@dataclass(slots=True)
class ScanSummary:
    run_id: int
    scanned: int = 0
    added: int = 0
    changed: int = 0
    unchanged: int = 0
    deleted: int = 0
    stale_units: int = 0
    stale_findings: int = 0
    stale_obligations: int = 0


def classify_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".sql"}:
        return "sql"
    if suffix in {".yaml", ".yml", ".json", ".toml", ".xml"}:
        return "configuration"
    if suffix in {".md", ".rst", ".txt"}:
        return "documentation"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf"}:
        return "binary-or-media"
    if suffix in {
        ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".kt", ".kts",
        ".cs", ".go", ".py", ".rb", ".php", ".rs", ".swift", ".c", ".cc", ".cpp",
        ".h", ".hpp", ".scala", ".clj", ".ex", ".exs", ".fs", ".fsx",
    }:
        return "source"
    return "other"


def iter_source_files(repo_root: Path, config: ProjectConfig) -> Iterable[Path]:
    seen: set[Path] = set()
    for root_name in config.source_roots:
        root = (repo_root / root_name).resolve()
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                relative = normalize_repo_path(repo_root, path)
            except (OSError, ValueError):
                continue
            if path_matches(relative, config.excludes):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def scan_repository(repo_root: Path, config: ProjectConfig, ledger: Ledger) -> ScanSummary:
    ledger.initialize()
    now = utc_now()
    config_hash = stable_hash(
        {
            "project_key": config.project_key,
            "source_roots": config.source_roots,
            "excludes": config.excludes,
            "generated_paths": config.generated_paths,
        }
    )

    with ledger.transaction(immediate=True) as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_runs(kind, started_at, status, repo_root, git_commit, config_hash)
            VALUES ('scan', ?, 'running', ?, ?, ?)
            """,
            (now, str(repo_root), git_commit(repo_root), config_hash),
        )
        run_id = int(cursor.lastrowid)

    summary = ScanSummary(run_id=run_id)
    current_paths: set[str] = set()
    changed_paths: set[str] = set()

    try:
        with ledger.transaction(immediate=True) as connection:
            for path in iter_source_files(repo_root, config):
                relative = normalize_repo_path(repo_root, path)
                current_paths.add(relative)
                stat = path.stat()
                digest = sha256_file(path)
                generated = int(path_matches(relative, config.generated_paths))
                existing = connection.execute(
                    "SELECT sha256, deleted FROM artifacts WHERE path = ?", (relative,)
                ).fetchone()

                if existing is None:
                    summary.added += 1
                    changed_paths.add(relative)
                    connection.execute(
                        """
                        INSERT INTO artifacts(
                            path, kind, sha256, size_bytes, mtime_ns, generated, deleted,
                            first_seen_run_id, last_seen_run_id, last_changed_run_id,
                            review_status, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'unreviewed', ?)
                        """,
                        (
                            relative,
                            classify_kind(path),
                            digest,
                            stat.st_size,
                            stat.st_mtime_ns,
                            generated,
                            run_id,
                            run_id,
                            run_id,
                            now,
                        ),
                    )
                elif existing["sha256"] != digest or existing["deleted"]:
                    summary.changed += 1
                    changed_paths.add(relative)
                    connection.execute(
                        """
                        UPDATE artifacts
                        SET kind=?, sha256=?, size_bytes=?, mtime_ns=?, generated=?, deleted=0,
                            last_seen_run_id=?, last_changed_run_id=?, review_status='stale', updated_at=?
                        WHERE path=?
                        """,
                        (
                            classify_kind(path),
                            digest,
                            stat.st_size,
                            stat.st_mtime_ns,
                            generated,
                            run_id,
                            run_id,
                            now,
                            relative,
                        ),
                    )
                else:
                    summary.unchanged += 1
                    connection.execute(
                        """
                        UPDATE artifacts
                        SET size_bytes=?, mtime_ns=?, generated=?, deleted=0,
                            last_seen_run_id=?, updated_at=?
                        WHERE path=?
                        """,
                        (stat.st_size, stat.st_mtime_ns, generated, run_id, now, relative),
                    )
                summary.scanned += 1

            known_rows = connection.execute(
                "SELECT path FROM artifacts WHERE deleted = 0"
            ).fetchall()
            for row in known_rows:
                relative = row["path"]
                if relative not in current_paths:
                    summary.deleted += 1
                    changed_paths.add(relative)
                    connection.execute(
                        """
                        UPDATE artifacts
                        SET deleted=1, review_status='stale', last_changed_run_id=?, updated_at=?
                        WHERE path=?
                        """,
                        (run_id, now, relative),
                    )

            if changed_paths:
                placeholders = ",".join("?" for _ in changed_paths)
                unit_rows = connection.execute(
                    f"""
                    SELECT DISTINCT unit_id
                    FROM review_unit_artifacts
                    WHERE artifact_path IN ({placeholders})
                    """,
                    tuple(sorted(changed_paths)),
                ).fetchall()
                unit_ids = [int(row["unit_id"]) for row in unit_rows]
                if unit_ids:
                    unit_placeholders = ",".join("?" for _ in unit_ids)
                    connection.execute(
                        f"""
                        UPDATE review_units
                        SET status='stale', claimed_by=NULL, lease_until=NULL, updated_at=?
                        WHERE id IN ({unit_placeholders})
                        """,
                        (now, *unit_ids),
                    )
                    summary.stale_units = len(unit_ids)

                finding_rows = connection.execute(
                    f"""
                    SELECT id FROM findings
                    WHERE file_path IN ({placeholders})
                      AND status NOT IN ('closed', 'false-positive', 'accepted-risk')
                    """,
                    tuple(sorted(changed_paths)),
                ).fetchall()
                finding_ids = [int(row["id"]) for row in finding_rows]
                if finding_ids:
                    finding_placeholders = ",".join("?" for _ in finding_ids)
                    connection.execute(
                        f"UPDATE findings SET status='stale', updated_at=? "
                        f"WHERE id IN ({finding_placeholders})",
                        (now, *finding_ids),
                    )
                    summary.stale_findings = len(finding_ids)

                proof_rows = connection.execute(
                    f"""
                    SELECT DISTINCT obligation_id
                    FROM proof_inputs
                    WHERE artifact_path IN ({placeholders})
                    """,
                    tuple(sorted(changed_paths)),
                ).fetchall()
                obligation_ids = [int(row["obligation_id"]) for row in proof_rows]
                if obligation_ids:
                    obligation_placeholders = ",".join("?" for _ in obligation_ids)
                    connection.execute(
                        f"UPDATE proof_obligations SET status='stale', updated_at=? "
                        f"WHERE id IN ({obligation_placeholders})",
                        (now, *obligation_ids),
                    )
                    summary.stale_obligations = len(obligation_ids)

            connection.execute(
                "UPDATE audit_runs SET status='completed', finished_at=? WHERE id=?",
                (utc_now(), run_id),
            )
    except Exception as exc:
        with ledger.transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE audit_runs SET status='failed', finished_at=?, notes=? WHERE id=?",
                (utc_now(), str(exc), run_id),
            )
        raise

    return summary


def _group_key(path: str) -> str:
    parts = path.split("/")
    if len(parts) == 1:
        return "root"
    if len(parts) == 2:
        return parts[0]
    return "/".join(parts[:2])


def autoplan_review_units(
    repo_root: Path,
    config: ProjectConfig,
    ledger: Ledger,
    *,
    replace: bool = False,
) -> dict[str, int]:
    ledger.initialize()
    now = utc_now()
    with ledger.transaction(immediate=True) as connection:
        if replace:
            connection.execute("DELETE FROM review_unit_artifacts")
            connection.execute("DELETE FROM review_units")

        rows = connection.execute(
            """
            SELECT path, sha256, kind
            FROM artifacts
            WHERE deleted=0 AND generated=0
            ORDER BY path
            """
        ).fetchall()
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[_group_key(row["path"])].append((row["path"], row["sha256"]))

        created = 0
        updated = 0
        membership = 0
        for component, files in sorted(grouped.items()):
            chunks = [
                files[index : index + config.max_files_per_unit]
                for index in range(0, len(files), config.max_files_per_unit)
            ]
            for chunk_index, chunk in enumerate(chunks, start=1):
                suffix = f"-{chunk_index}" if len(chunks) > 1 else ""
                unit_key = f"auto:{component}{suffix}"
                title = f"Автоматический срез: {component}{suffix}"
                current_hash = stable_hash(chunk)
                priority = 10 if any(path_matches(path, config.critical_paths) for path, _ in chunk) else 100
                existing = connection.execute(
                    "SELECT id, current_hash, reviewed_hash FROM review_units WHERE unit_key=?",
                    (unit_key,),
                ).fetchone()
                if existing is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO review_units(
                            unit_key, title, component, priority, status, current_hash,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                        """,
                        (unit_key, title, component, priority, current_hash, now, now),
                    )
                    unit_id = int(cursor.lastrowid)
                    created += 1
                else:
                    unit_id = int(existing["id"])
                    status = (
                        "completed"
                        if existing["reviewed_hash"] and existing["reviewed_hash"] == current_hash
                        else "stale"
                    )
                    connection.execute(
                        """
                        UPDATE review_units
                        SET title=?, component=?, priority=?, status=?, current_hash=?, updated_at=?
                        WHERE id=?
                        """,
                        (title, component, priority, status, current_hash, now, unit_id),
                    )
                    connection.execute(
                        "DELETE FROM review_unit_artifacts WHERE unit_id=?", (unit_id,)
                    )
                    updated += 1

                connection.executemany(
                    """
                    INSERT OR IGNORE INTO review_unit_artifacts(unit_id, artifact_path)
                    VALUES (?, ?)
                    """,
                    [(unit_id, path) for path, _ in chunk],
                )
                membership += len(chunk)

        return {"created": created, "updated": updated, "memberships": membership}
