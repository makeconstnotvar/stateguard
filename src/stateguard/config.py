from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import StateGuardError


DEFAULT_EXCLUDES = [
    ".git",
    ".stateguard",
    ".idea",
    ".vscode",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "target",
    "bin",
    "obj",
    "__pycache__",
    "*.min.js",
    "*.map",
    "*.lock",
]


@dataclass(slots=True)
class ProjectConfig:
    project_key: str
    project_name: str
    source_roots: list[str] = field(default_factory=lambda: ["."])
    excludes: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    max_files_per_unit: int = 80
    critical_paths: list[str] = field(default_factory=list)
    generated_paths: list[str] = field(default_factory=list)
    sonar_project_key: str | None = None
    specification: str = ".stateguard/specification.yaml"
    mappings: str = ".stateguard/mappings.yaml"
    event_b_project: str | None = None
    semgrep_rules: list[str] = field(default_factory=list)
    semgrep_report: str = ".stateguard/results/semgrep.sarif"
    joern_output: str = ".stateguard/results/joern"
    joern_languages: list[str] = field(default_factory=list)
    native_analyzers: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ProjectConfig":
        project = data.get("project") or {}
        scanning = data.get("scanning") or {}
        review = data.get("review") or {}
        integrations = data.get("integrations") or {}
        spec = data.get("specification") or {}
        semgrep = integrations.get("semgrep") or {}
        joern = integrations.get("joern") or {}

        key = str(project.get("key") or "").strip()
        if not key:
            raise StateGuardError("В stateguard.yaml отсутствует project.key")

        return cls(
            project_key=key,
            project_name=str(project.get("name") or key),
            source_roots=[str(x) for x in scanning.get("source_roots", ["."])],
            excludes=list(DEFAULT_EXCLUDES) + [str(x) for x in scanning.get("excludes", [])],
            max_files_per_unit=int(review.get("max_files_per_unit", 80)),
            critical_paths=[str(x) for x in review.get("critical_paths", [])],
            generated_paths=[str(x) for x in scanning.get("generated_paths", [])],
            sonar_project_key=(integrations.get("sonarqube") or {}).get("project_key"),
            specification=str(spec.get("file") or ".stateguard/specification.yaml"),
            mappings=str(spec.get("mappings") or ".stateguard/mappings.yaml"),
            event_b_project=(str(spec["event_b_project"]) if spec.get("event_b_project") else None),
            semgrep_rules=[str(x) for x in semgrep.get("rules", [])],
            semgrep_report=str(semgrep.get("report") or ".stateguard/results/semgrep.sarif"),
            joern_output=str(joern.get("output") or ".stateguard/results/joern"),
            joern_languages=[str(x) for x in joern.get("languages", [])],
            native_analyzers=[dict(x) for x in integrations.get("native_analyzers", [])],
        )


def load_config(repo_root: Path) -> ProjectConfig:
    path = repo_root / ".stateguard" / "stateguard.yaml"
    if not path.exists():
        raise StateGuardError(
            f"Конфигурация не найдена: {path}. Выполните `stateguard init`."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise StateGuardError(f"Ожидался YAML-объект в {path}")
    return ProjectConfig.from_mapping(data)
