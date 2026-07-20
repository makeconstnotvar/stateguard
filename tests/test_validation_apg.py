from __future__ import annotations

import json
from pathlib import Path

from stateguard.apg import import_apg_jsonl
from stateguard.bootstrap import initialize_project
from stateguard.db import Ledger
from stateguard.validation import validate_project


def test_empty_initialized_spec_is_valid_minimal_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    result = validate_project(repo)
    assert result.ok, result.errors


def test_apg_jsonl_import(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    ledger = Ledger(repo)
    path = repo / "graph.jsonl"
    records = [
        {
            "kind": "node",
            "externalId": "endpoint:submit",
            "type": "Endpoint",
            "name": "submit",
            "artifactPath": "server.js",
            "range": {"startLine": 1, "endLine": 3},
            "sourceTool": "test",
            "properties": {},
        },
        {
            "kind": "node",
            "externalId": "write:orders",
            "type": "Query",
            "name": "update orders",
            "sourceTool": "test",
            "properties": {},
        },
        {
            "kind": "edge",
            "externalId": "edge:1",
            "type": "CALLS",
            "source": "endpoint:submit",
            "target": "write:orders",
            "sourceTool": "test",
            "properties": {},
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    result = import_apg_jsonl(ledger, path)
    assert result["nodes"] == 2
    assert result["edges"] == 1
    with ledger.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM apg_nodes").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM apg_edges").fetchone()[0] == 1
