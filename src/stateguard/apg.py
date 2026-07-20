from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import Ledger
from .errors import StateGuardError
from .util import sha256_file, utc_now


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        raise StateGuardError(f"APG JSONL не найден: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StateGuardError(f"Некорректный APG JSONL {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise StateGuardError(f"APG record должен быть объектом: {path}:{line_number}")
            records.append(record)
    return records


def import_apg_jsonl(ledger: Ledger, path: Path, source_tool: str | None = None) -> dict[str, int | str]:
    ledger.initialize()
    records = _load_jsonl(path)
    source_hash = sha256_file(path)
    now = utc_now()
    nodes = [record for record in records if record.get("kind") == "node"]
    edges = [record for record in records if record.get("kind") == "edge"]
    unknown = len(records) - len(nodes) - len(edges)
    if unknown:
        raise StateGuardError(f"APG содержит {unknown} record(s) с неизвестным kind")

    with ledger.transaction(immediate=True) as connection:
        for node in nodes:
            external_id = str(node.get("externalId") or "").strip()
            node_type = str(node.get("type") or "").strip()
            if not external_id or not node_type:
                raise StateGuardError("APG node требует externalId и type")
            properties = node.get("properties") or {}
            if not isinstance(properties, dict):
                raise StateGuardError(f"APG node {external_id}: properties должен быть объектом")
            node_source = str(node.get("sourceTool") or source_tool or "apg-import")
            range_value = node.get("range") or {}
            connection.execute(
                """
                INSERT INTO apg_nodes(
                    external_id, node_type, name, artifact_path, start_line, end_line,
                    properties_json, source_tool, source_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    node_type=excluded.node_type,
                    name=excluded.name,
                    artifact_path=excluded.artifact_path,
                    start_line=excluded.start_line,
                    end_line=excluded.end_line,
                    properties_json=excluded.properties_json,
                    source_tool=excluded.source_tool,
                    source_hash=excluded.source_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    external_id,
                    node_type,
                    node.get("name"),
                    node.get("artifactPath"),
                    range_value.get("startLine"),
                    range_value.get("endLine"),
                    json.dumps(properties, ensure_ascii=False, sort_keys=True),
                    node_source,
                    source_hash,
                    now,
                ),
            )

        existing_ids = {
            row["external_id"] for row in connection.execute("SELECT external_id FROM apg_nodes")
        }
        for edge in edges:
            external_id = str(edge.get("externalId") or "").strip()
            edge_type = str(edge.get("type") or "").strip()
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
            if not external_id or not edge_type or not source or not target:
                raise StateGuardError("APG edge требует externalId, type, source и target")
            if source not in existing_ids or target not in existing_ids:
                raise StateGuardError(
                    f"APG edge {external_id}: dangling endpoint source={source} target={target}"
                )
            properties = edge.get("properties") or {}
            if not isinstance(properties, dict):
                raise StateGuardError(f"APG edge {external_id}: properties должен быть объектом")
            edge_source = str(edge.get("sourceTool") or source_tool or "apg-import")
            connection.execute(
                """
                INSERT INTO apg_edges(
                    external_id, source_external_id, target_external_id, edge_type,
                    properties_json, source_tool, source_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    source_external_id=excluded.source_external_id,
                    target_external_id=excluded.target_external_id,
                    edge_type=excluded.edge_type,
                    properties_json=excluded.properties_json,
                    source_tool=excluded.source_tool,
                    source_hash=excluded.source_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    external_id,
                    source,
                    target,
                    edge_type,
                    json.dumps(properties, ensure_ascii=False, sort_keys=True),
                    edge_source,
                    source_hash,
                    now,
                ),
            )
    return {"nodes": len(nodes), "edges": len(edges), "source_hash": source_hash}
