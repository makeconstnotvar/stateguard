from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from .db import Ledger
from .errors import StateGuardError
from .findings import FindingInput, upsert_finding
from .util import atomic_write, slugify

# Maps a mappings.yaml location `kind` (schemas/mappings.schema.json's enum) to an APG
# node `type` from the vocabulary in docs/08-joern-and-application-property-graph.md.
_LOCATION_KIND_TO_NODE_TYPE = {
    "file": "File",
    "symbol": "Symbol",
    "route": "Endpoint",
    "query": "Query",
    "table": "Table",
    "column": "Column",
    "constraint": "Constraint",
    "index": "Index",
    "test": "Test",
    "job": "Symbol",
    "ui-action": "UIAction",
    "event-b-element": "Symbol",
}

_SECTION_NODE_TYPE = {
    "entities": "DomainEntity",
    "invariants": "Invariant",
    "commands": "Command",
    "observations": "Observation",
}
_SECTION_PREFIX = {
    "entities": "entity",
    "invariants": "invariant",
    "commands": "command",
    "observations": "observation",
}

# Selectors for these kinds are already globally stable identifiers (SQL/route names),
# so the external ID drops the path. These kinds' selector alone is the ID (one query
# file == one named query, by this codebase's convention).
_SELECTOR_ONLY_KINDS = {"table", "column", "constraint", "route"}
_PATH_ONLY_KINDS = {"query", "file"}


def _location_external_id(kind: str, path: str | None, selector: str) -> str:
    if kind in _SELECTOR_ONLY_KINDS or not path:
        return f"{kind}:{slugify(selector)}"
    if kind in _PATH_ONLY_KINDS:
        return f"{kind}:{path}"
    return f"{kind}:{path}:{slugify(selector)}"


def _node(
    external_id: str,
    node_type: str,
    name: str,
    *,
    artifact_path: str | None = None,
    line_range: dict[str, int] | None = None,
    source_tool: str = "stateguard-mapping",
    confidence: str = "asserted",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": "node",
        "externalId": external_id,
        "type": node_type,
        "name": name,
        "sourceTool": source_tool,
        "properties": {"confidence": confidence},
    }
    if artifact_path:
        record["artifactPath"] = artifact_path
    if line_range:
        record["range"] = line_range
    return record


def _edge(external_id: str, edge_type: str, source: str, target: str) -> dict[str, Any]:
    return {
        "kind": "edge",
        "externalId": external_id,
        "type": edge_type,
        "source": source,
        "target": target,
        "sourceTool": "stateguard-mapping",
        "properties": {"confidence": "asserted"},
    }


def _load_joern_export(joern_dir: Path | None) -> dict[str, list[dict]]:
    if joern_dir is None or not joern_dir.exists():
        return {}
    export: dict[str, list[dict]] = {}
    for name in ("methods", "calls", "files", "type-declarations"):
        path = joern_dir / f"{name}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list):
            export[name] = [item for item in data if isinstance(item, dict)]
    return export


def _enrich_line_range(export: dict[str, list[dict]], path: str, selector: str) -> dict[str, int] | None:
    # Best-effort: field names follow Joern's documented stable CPG properties
    # (name/filename/lineNumber). This has not been reconciled against a live
    # joern-parse run — treat as provisional until it has been.
    for method in export.get("methods") or []:
        filename = method.get("filename") or method.get("file")
        name = method.get("name") or method.get("methodName")
        if filename is None or name is None:
            continue
        if not str(filename).endswith(path) or name != selector:
            continue
        start = method.get("lineNumber")
        if start is None:
            continue
        end = method.get("lineNumberEnd") or start
        try:
            return {"startLine": int(start), "endLine": int(end)}
        except (TypeError, ValueError):
            return None
    return None


def _transaction_wrapper_selectors(mapping: dict[str, Any]) -> set[str]:
    selectors: set[str] = set()
    for adapter in mapping.get("framework_adapters") or []:
        rules = adapter.get("rules") or {}
        selectors.update(rules.get("transaction_starts") or [])
    return selectors


def build_apg(
    repo_root: Path,
    ledger: Ledger,
    spec_path: Path,
    mapping_path: Path,
    joern_dir: Path | None = None,
) -> list[dict[str, Any]]:
    specification = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    joern_export = _load_joern_export(joern_dir)
    transaction_wrappers = _transaction_wrapper_selectors(mapping)

    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        if record["externalId"] in seen:
            return
        seen.add(record["externalId"])
        records.append(record)

    # Pass 1: a node per spec item and per mapped location, plus the location-kind-
    # driven edges that need no extra context (ENFORCES, CALLS, TESTED_BY). Also
    # performs mapping-gap detection: a location whose path doesn't exist on disk is
    # exactly the class of bug that shipped in this example before it was fixed.
    command_symbol_locations: dict[str, list[dict[str, Any]]] = {}
    for section, node_type in _SECTION_NODE_TYPE.items():
        prefix = _SECTION_PREFIX[section]
        for item in mapping.get(section) or []:
            item_id = item.get("id")
            if not item_id:
                continue
            spec_node_id = f"{prefix}:{item_id}"
            add(_node(spec_node_id, node_type, item_id))

            for location in item.get("locations") or []:
                kind = location.get("kind")
                selector = location.get("selector")
                path = location.get("path")
                if not kind or not selector:
                    continue

                if path:
                    resolved = (repo_root / path).resolve()
                    if not resolved.exists():
                        upsert_finding(
                            ledger,
                            FindingInput(
                                source_tool="joern-apg-adapter",
                                rule_id="MAPPING-GAP",
                                title=f"Mapping references a path that does not exist: {path}",
                                message=(
                                    f"{section}.{item_id} location kind={kind} selector="
                                    f"{selector!r} points at {path!r}, which is not a file "
                                    "in this repository."
                                ),
                                severity="low",
                                category="mapping-gap",
                                file_path=path,
                            ),
                        )
                        continue

                loc_type = _LOCATION_KIND_TO_NODE_TYPE.get(kind, "Symbol")
                loc_id = _location_external_id(kind, path, selector)
                source_tool, line_range = "stateguard-mapping", None
                if kind == "symbol" and path:
                    if selector in transaction_wrappers:
                        loc_type = "Transaction"
                        loc_id = f"transaction:{path}:{slugify(selector)}"
                    enriched_range = _enrich_line_range(joern_export, path, selector)
                    if enriched_range:
                        source_tool, line_range = "joern-apg-adapter", enriched_range
                add(
                    _node(
                        loc_id,
                        loc_type,
                        selector,
                        artifact_path=path,
                        line_range=line_range,
                        source_tool=source_tool,
                        confidence="observed" if line_range else "asserted",
                    )
                )

                if section == "invariants" and kind == "constraint":
                    add(_edge(f"edge:{loc_id}->ENFORCES->{spec_node_id}", "ENFORCES", loc_id, spec_node_id))
                if section == "commands" and kind == "query":
                    add(_edge(f"edge:{spec_node_id}->CALLS->{loc_id}", "CALLS", spec_node_id, loc_id))
                if kind == "test":
                    add(_edge(f"edge:{spec_node_id}->TESTED_BY->{loc_id}", "TESTED_BY", spec_node_id, loc_id))
                if section == "commands" and kind == "symbol":
                    command_symbol_locations.setdefault(item_id, []).append(location)

    # Pass 2: WRITES and PART_OF_TRANSACTION edges need specification.yaml's
    # atomicity.writes/strategy plus the transaction-wrapper locations resolved above,
    # so they're derived from the command's *handler* symbol specifically — the symbol
    # location that is neither a decoder (`decode*`) nor a known transaction wrapper.
    for command in specification.get("commands") or []:
        command_id = command.get("id")
        atomicity = command.get("atomicity") or {}
        writes = atomicity.get("writes") or []
        tables = {write.split(".", 1)[0] for write in writes if "." in write}
        symbol_locations = command_symbol_locations.get(command_id, [])
        handlers = [
            location
            for location in symbol_locations
            if location["selector"] not in transaction_wrappers
            and not location["selector"].lower().startswith("decode")
        ]
        wrappers = [location for location in symbol_locations if location["selector"] in transaction_wrappers]

        for handler in handlers:
            handler_id = _location_external_id("symbol", handler.get("path"), handler["selector"])
            for table in tables:
                table_id = f"table:public.{table}"
                if table_id in seen:
                    add(_edge(f"edge:{handler_id}->WRITES->{table_id}", "WRITES", handler_id, table_id))
            for wrapper in wrappers:
                wrapper_id = f"transaction:{wrapper.get('path')}:{slugify(wrapper['selector'])}"
                add(
                    _edge(
                        f"edge:{handler_id}->PART_OF_TRANSACTION->{wrapper_id}",
                        "PART_OF_TRANSACTION",
                        handler_id,
                        wrapper_id,
                    )
                )

    validation_errors = validate_apg_records(records)
    if validation_errors:
        raise StateGuardError(
            "joern_adapter produced APG records that fail schemas/apg.schema.json: "
            + "; ".join(validation_errors)
        )
    return records


def validate_apg_records(records: list[dict[str, Any]]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(files("stateguard").joinpath("schemas", "apg.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for index, record in enumerate(records):
        for error in validator.iter_errors(record):
            errors.append(f"record[{index}] (externalId={record.get('externalId')!r}): {error.message}")
    return errors


def write_apg_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    content = "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)
    atomic_write(path, content + ("\n" if content else ""))
