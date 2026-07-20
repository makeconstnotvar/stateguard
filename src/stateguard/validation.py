from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

import json
import yaml

from .config import load_config
from .errors import StateGuardError


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        raise StateGuardError(f"Файл не найден: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StateGuardError(f"Некорректный YAML {path}: {exc}") from exc


def _schema(name: str) -> dict[str, Any]:
    text = files("stateguard").joinpath("schemas", name).read_text(encoding="utf-8")
    return json.loads(text)


def _validate_json_schema(instance: Any, schema_name: str, label: str, result: ValidationResult) -> None:
    try:
        import jsonschema
    except ImportError:
        result.warnings.append(
            "Пакет jsonschema не установлен; выполнена только semantic/minimal validation. "
            "Установите `pip install -e '.[validation]'` для полной schema validation."
        )
        return

    validator = jsonschema.Draft202012Validator(_schema(schema_name))
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        result.errors.append(f"{label}:{location}: {error.message}")


def _unique_ids(items: list[dict[str, Any]], section: str, result: ValidationResult) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        identifier = str(item.get("id") or "").strip()
        if not identifier:
            result.errors.append(f"specification.{section}[{index}]: отсутствует id")
        elif identifier in seen:
            result.errors.append(f"specification.{section}: дублируется id {identifier}")
        else:
            seen.add(identifier)
    return seen


def _semantic_spec_validation(spec: dict[str, Any], result: ValidationResult) -> None:
    sections = ["entities", "states", "invariants", "commands", "observations", "external_effects"]
    ids: dict[str, set[str]] = {}
    for section in sections:
        value = spec.get(section)
        if not isinstance(value, list):
            result.errors.append(f"specification.{section}: ожидается список")
            value = []
        ids[section] = _unique_ids([item for item in value if isinstance(item, dict)], section, result)

    all_ids = set().union(*ids.values()) if ids else set()
    for state in spec.get("states") or []:
        if not isinstance(state, dict):
            continue
        if state.get("entity") not in ids["entities"]:
            result.errors.append(f"state {state.get('id')}: неизвестная entity {state.get('entity')}")
        values = state.get("values") or []
        if state.get("initial") not in values:
            result.errors.append(f"state {state.get('id')}: initial отсутствует в values")
        invalid_terminal = sorted(set(state.get("terminal") or []) - set(values))
        if invalid_terminal:
            result.errors.append(
                f"state {state.get('id')}: terminal values отсутствуют в values: {invalid_terminal}"
            )

    for command in spec.get("commands") or []:
        if not isinstance(command, dict):
            continue
        identifier = command.get("id")
        if command.get("entity") not in ids["entities"]:
            result.errors.append(f"command {identifier}: неизвестная entity {command.get('entity')}")
        outcomes = command.get("outcomes") or []
        outcome_ids = [outcome.get("id") for outcome in outcomes if isinstance(outcome, dict)]
        if len(outcome_ids) != len(set(outcome_ids)):
            result.errors.append(f"command {identifier}: outcome IDs должны быть уникальны")
        for invariant_id in command.get("preserves") or []:
            if invariant_id not in ids["invariants"]:
                result.errors.append(f"command {identifier}: неизвестный invariant {invariant_id}")
        for effect_id in command.get("effects") or []:
            if effect_id not in ids["external_effects"]:
                result.errors.append(f"command {identifier}: неизвестный effect {effect_id}")

    for invariant in spec.get("invariants") or []:
        if not isinstance(invariant, dict):
            continue
        for reference in invariant.get("scope") or []:
            if reference not in all_ids:
                result.errors.append(
                    f"invariant {invariant.get('id')}: неизвестный scope reference {reference}"
                )
        if invariant.get("criticality") in {"critical", "high"} and not invariant.get("enforcement"):
            result.errors.append(
                f"invariant {invariant.get('id')}: critical/high invariant должен иметь enforcement"
            )


def _semantic_mapping_validation(mapping: dict[str, Any], spec: dict[str, Any], result: ValidationResult) -> None:
    spec_ids = {
        section: {item.get("id") for item in spec.get(section, []) if isinstance(item, dict)}
        for section in ["entities", "invariants", "commands", "observations"]
    }
    for section in ["entities", "invariants", "commands", "observations"]:
        mapping_items = mapping.get(section) or []
        mapped_ids = set()
        for item in mapping_items:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            mapped_ids.add(identifier)
            if identifier not in spec_ids[section]:
                result.errors.append(f"mappings.{section}: неизвестный specification id {identifier}")
        missing = sorted(spec_ids[section] - mapped_ids)
        for identifier in missing:
            result.warnings.append(f"mappings.{section}: отсутствует mapping для {identifier}")


def validate_project(repo_root: Path) -> ValidationResult:
    result = ValidationResult(ok=True)
    config = load_config(repo_root)
    config_path = repo_root / ".stateguard" / "stateguard.yaml"
    spec_path = (repo_root / config.specification).resolve()
    mapping_path = (repo_root / config.mappings).resolve()

    config_data = _load_yaml(config_path) or {}
    spec = _load_yaml(spec_path) or {}
    mapping = _load_yaml(mapping_path) or {}
    if not isinstance(config_data, dict) or not isinstance(spec, dict) or not isinstance(mapping, dict):
        raise StateGuardError("Config, specification и mappings должны быть YAML-объектами")

    result.files = {
        "config": str(config_path),
        "specification": str(spec_path),
        "mappings": str(mapping_path),
    }
    _validate_json_schema(config_data, "stateguard.schema.json", "stateguard.yaml", result)
    _validate_json_schema(spec, "specification.schema.json", "specification.yaml", result)
    _validate_json_schema(mapping, "mappings.schema.json", "mappings.yaml", result)
    _semantic_spec_validation(spec, result)
    _semantic_mapping_validation(mapping, spec, result)
    result.ok = not result.errors
    return result
