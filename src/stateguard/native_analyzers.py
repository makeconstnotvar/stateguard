from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .db import Ledger
from .errors import StateGuardError
from .sarif import import_sarif


def _resolve_eslint_binary(repo_root: Path) -> str | None:
    local = repo_root / "node_modules" / ".bin" / "eslint"
    if local.exists():
        return str(local)
    return shutil.which("eslint")


def _resolve_eslint_sarif_formatter(repo_root: Path) -> str | None:
    candidate = repo_root / "node_modules" / "@microsoft" / "eslint-formatter-sarif" / "sarif.js"
    return str(candidate) if candidate.exists() else None


def run_native_analyzer(repo_root: Path, ledger: Ledger, entry: dict[str, Any]) -> dict[str, Any]:
    tool = entry.get("tool")
    targets = [str(t) for t in (entry.get("targets") or [])]
    report_path = (repo_root / (entry.get("report") or f".stateguard/results/{tool}.sarif")).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if tool == "ruff":
        binary = shutil.which("ruff")
        if not binary:
            return {"tool": tool, "status": "skipped", "message": "SKIPPED: ruff not installed"}
        cmd = [binary, "check", "--output-format", "sarif", "--output-file", str(report_path)]
        if entry.get("config"):
            cmd += ["--config", entry["config"]]
        cmd += targets
    elif tool == "eslint":
        binary = _resolve_eslint_binary(repo_root)
        formatter = _resolve_eslint_sarif_formatter(repo_root)
        if not binary or not formatter:
            return {
                "tool": tool,
                "status": "skipped",
                "message": "SKIPPED: eslint or @microsoft/eslint-formatter-sarif not installed",
            }
        cmd = [binary, "--format", formatter, "--output-file", str(report_path)]
        if entry.get("config"):
            cmd += ["--config", entry["config"]]
        cmd += targets
    else:
        raise StateGuardError(f"Неизвестный native analyzer: {tool!r} (допустимо: ruff, eslint)")

    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=300)
    # Both ruff and eslint exit 1 when violations were found (not a tool failure) — only
    # >=2 indicates the tool itself broke.
    if result.returncode not in (0, 1):
        return {"tool": tool, "status": "failed", "message": (result.stderr or result.stdout)[-500:]}

    if not report_path.exists():
        return {"tool": tool, "status": "ok", "message": "ran, no SARIF output produced"}
    imported = import_sarif(ledger, report_path)
    return {"tool": tool, "status": "ok", "imported": imported["imported"]}


def run_native_analyzers(repo_root: Path, ledger: Ledger, config: ProjectConfig) -> list[dict[str, Any]]:
    return [run_native_analyzer(repo_root, ledger, entry) for entry in config.native_analyzers]
