from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .config import ProjectConfig


def sync_semgrep_rules(repo_root: Path, config: ProjectConfig) -> dict:
    dest = repo_root / ".stateguard" / "rules"
    dest.mkdir(parents=True, exist_ok=True)

    synced = 0
    sources: list[str] = []
    for raw in config.semgrep_rules:
        candidate = Path(raw)
        source = candidate if candidate.is_absolute() else (repo_root / candidate).resolve()
        if not source.exists():
            print(f"sync-rules: SKIPPED missing source {source}", file=sys.stderr)
            continue

        target = dest / source.name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
            synced += sum(1 for _ in target.rglob("*.y*ml"))
        else:
            shutil.copy2(source, target)
            synced += 1
        sources.append(str(source))

    return {"synced": synced, "sources": sources, "destination": str(dest)}
