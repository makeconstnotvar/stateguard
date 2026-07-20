from __future__ import annotations

import subprocess
from pathlib import Path


def discover_repo_root(candidate: str | None = None) -> Path:
    start = Path(candidate or ".").resolve()
    if start.is_file():
        start = start.parent

    current = start
    while True:
        if (current / ".git").exists() or (current / ".stateguard").exists():
            return current
        if current.parent == current:
            return start
        current = current.parent


def git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value or None
