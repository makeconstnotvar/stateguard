from __future__ import annotations

import json
from pathlib import Path

from stateguard.bootstrap import initialize_project
from stateguard.config import load_config
from stateguard.db import Ledger
from stateguard.sarif import import_sarif
from stateguard.scanner import scan_repository


def _sarif(uri: str) -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ruff", "rules": []}},
                "results": [
                    {
                        "ruleId": "F401",
                        "level": "error",
                        "message": {"text": "`json` imported but unused"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": uri},
                                    "region": {"startLine": 3, "startColumn": 8},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_absolute_file_uri_is_relativized_against_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    source = repo / "server.py"
    source.write_text("import json\n", encoding="utf-8")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    sarif_path = repo / "ruff.sarif"
    sarif_path.write_text(json.dumps(_sarif(f"file://{source.resolve()}")), encoding="utf-8")

    result = import_sarif(ledger, sarif_path)
    assert result["imported"] == 1
    with ledger.connect() as connection:
        row = connection.execute(
            "SELECT file_path, artifact_sha256 FROM findings"
        ).fetchone()
    assert row["file_path"] == "server.py"
    assert row["artifact_sha256"] is not None


def test_absolute_file_uri_outside_repo_root_falls_back_to_absolute_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    ledger = Ledger(repo)
    ledger.initialize()

    outside = tmp_path / "elsewhere.py"
    outside.write_text("import json\n", encoding="utf-8")
    sarif_path = repo / "ruff.sarif"
    sarif_path.write_text(json.dumps(_sarif(f"file://{outside.resolve()}")), encoding="utf-8")

    import_sarif(ledger, sarif_path)
    with ledger.connect() as connection:
        row = connection.execute("SELECT file_path FROM findings").fetchone()
    assert row["file_path"] == str(outside.resolve())


def test_relative_uri_is_unaffected_by_repo_root_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    source = repo / "server.js"
    source.write_text("console.log('x');\n", encoding="utf-8")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    sarif_path = repo / "semgrep.sarif"
    sarif_path.write_text(json.dumps(_sarif("server.js")), encoding="utf-8")

    import_sarif(ledger, sarif_path)
    with ledger.connect() as connection:
        row = connection.execute("SELECT file_path, artifact_sha256 FROM findings").fetchone()
    assert row["file_path"] == "server.js"
    assert row["artifact_sha256"] is not None
