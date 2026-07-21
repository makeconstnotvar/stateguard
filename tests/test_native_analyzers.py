from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from stateguard.bootstrap import initialize_project
from stateguard.config import load_config
from stateguard.db import Ledger
from stateguard.errors import StateGuardError
from stateguard.native_analyzers import run_native_analyzer
from stateguard.scanner import scan_repository

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    return repo


def test_ruff_finds_a_real_violation_and_imports_it(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("import json\n\ndef f():\n    return 1\n", encoding="utf-8")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    result = run_native_analyzer(
        repo, ledger, {"tool": "ruff", "targets": ["."], "report": ".stateguard/results/ruff.sarif"}
    )

    assert result["tool"] == "ruff"
    assert result["status"] == "ok"
    assert result["imported"] == 1
    with ledger.connect() as connection:
        row = connection.execute("SELECT file_path, rule_id FROM findings").fetchone()
    assert row["file_path"] == "app.py"
    assert row["rule_id"] == "F401"


def test_ruff_clean_code_imports_zero_findings(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    result = run_native_analyzer(repo, ledger, {"tool": "ruff", "targets": ["."]})
    assert result["status"] == "ok"
    assert result.get("imported", 0) == 0


def test_unknown_tool_raises() -> None:
    with pytest.raises(StateGuardError):
        run_native_analyzer(Path("."), None, {"tool": "spotbugs", "targets": ["."]})


def test_missing_ruff_binary_skips_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stateguard.native_analyzers.shutil.which", lambda name: None)
    repo = _init_repo(tmp_path)
    result = run_native_analyzer(repo, Ledger(repo), {"tool": "ruff", "targets": ["."]})
    assert result == {"tool": "ruff", "status": "skipped", "message": "SKIPPED: ruff not installed"}


def _eslint_sarif(uri: str) -> dict:
    return {
        "version": "2.1.0",
        "$schema": "http://json.schemastore.org/sarif-2.1.0-rtm.5",
        "runs": [
            {
                "tool": {"driver": {"name": "ESLint", "version": "10.7.0", "rules": []}},
                "results": [
                    {
                        "ruleId": "no-unused-vars",
                        "level": "error",
                        "message": {"text": "'x' is assigned a value but never used."},
                        "locations": [
                            {"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": 1}}}
                        ],
                    }
                ],
            }
        ],
    }


def test_eslint_wiring_resolves_local_binary_and_imports_sarif(tmp_path: Path) -> None:
    # Stubs stand in for a real `npm install eslint @microsoft/eslint-formatter-sarif` —
    # this test verifies run_native_analyzer's plumbing (binary/formatter resolution,
    # command construction, SARIF import), not ESLint itself. ESLint + the SARIF
    # formatter were verified manually end-to-end against examples/order-workflow with
    # real npm-installed packages (see IMPLEMENTATION-MASTER-PLAN.md).
    repo = _init_repo(tmp_path)
    source = repo / "app.js"
    source.write_text("const x = 1;\n", encoding="utf-8")
    ledger = Ledger(repo)
    scan_repository(repo, load_config(repo), ledger)

    bin_dir = repo / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    formatter_dir = repo / "node_modules" / "@microsoft" / "eslint-formatter-sarif"
    formatter_dir.mkdir(parents=True)
    (formatter_dir / "sarif.js").write_text("// stub\n", encoding="utf-8")

    sarif_payload = json.dumps(_eslint_sarif(f"file://{source.resolve()}"))
    stub = bin_dir / "eslint"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "out=\"\"\n"
        "for ((i=1;i<=$#;i++)); do\n"
        '  if [ "${!i}" = "--output-file" ]; then j=$((i+1)); out="${!j}"; fi\n'
        "done\n"
        f"cat > \"$out\" <<'SARIF_EOF'\n{sarif_payload}\nSARIF_EOF\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    result = run_native_analyzer(
        repo, ledger, {"tool": "eslint", "targets": ["app.js"], "report": ".stateguard/results/eslint.sarif"}
    )

    assert result == {"tool": "eslint", "status": "ok", "imported": 1}
    with ledger.connect() as connection:
        row = connection.execute("SELECT file_path, rule_id FROM findings").fetchone()
    assert row["file_path"] == "app.js"
    assert row["rule_id"] == "no-unused-vars"


def test_eslint_missing_formatter_skips_gracefully(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    bin_dir = repo / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "eslint").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (bin_dir / "eslint").chmod(0o755)

    result = run_native_analyzer(repo, Ledger(repo), {"tool": "eslint", "targets": ["."]})
    assert result["status"] == "skipped"
    assert "not installed" in result["message"]
