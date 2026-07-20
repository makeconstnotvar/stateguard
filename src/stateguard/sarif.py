from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .db import Ledger
from .errors import StateGuardError
from .findings import FindingInput, list_open_findings, upsert_finding
from .util import atomic_write, stable_hash


def _uri_to_path(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        value = unquote(parsed.path)
        if value.startswith("/") and len(value) > 3 and value[2] == ":":
            value = value[1:]
        return value.replace("\\", "/")
    return unquote(uri).replace("\\", "/").lstrip("./")


def _rule_title(run: dict[str, Any], rule_id: str) -> str:
    driver = (run.get("tool") or {}).get("driver") or {}
    rules = driver.get("rules") or []
    for rule in rules:
        if str(rule.get("id")) == rule_id:
            short = rule.get("shortDescription") or {}
            full = rule.get("fullDescription") or {}
            return str(short.get("text") or full.get("text") or rule_id)
    return rule_id


def import_sarif(ledger: Ledger, path: Path, *, run_id: int | None = None) -> dict[str, int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateGuardError(f"Не удалось прочитать SARIF {path}: {exc}") from exc

    if payload.get("version") != "2.1.0":
        raise StateGuardError(f"Поддерживается SARIF 2.1.0, получено {payload.get('version')!r}")

    imported = 0
    skipped = 0
    for run in payload.get("runs") or []:
        driver = (run.get("tool") or {}).get("driver") or {}
        tool_name = str(driver.get("name") or "sarif")
        for result in run.get("results") or []:
            rule_id = str(result.get("ruleId") or "unknown-rule")
            message = str((result.get("message") or {}).get("text") or "").strip()
            if not message:
                skipped += 1
                continue
            level = str(result.get("level") or "warning")
            locations = result.get("locations") or [None]
            location = locations[0] if locations else None
            file_path = None
            start_line = start_column = end_line = end_column = None
            if location:
                physical = location.get("physicalLocation") or {}
                artifact = physical.get("artifactLocation") or {}
                region = physical.get("region") or {}
                if artifact.get("uri"):
                    file_path = _uri_to_path(str(artifact["uri"]))
                start_line = region.get("startLine")
                start_column = region.get("startColumn")
                end_line = region.get("endLine")
                end_column = region.get("endColumn")

            partial = result.get("partialFingerprints") or {}
            fingerprint = (
                result.get("fingerprints")
                or partial
                or {
                    "rule": rule_id,
                    "path": file_path,
                    "line": start_line,
                    "message": message,
                }
            )
            external_key = f"{tool_name}:{stable_hash(fingerprint)}"
            properties = result.get("properties") or {}
            finding = FindingInput(
                source_tool=tool_name,
                rule_id=rule_id,
                title=_rule_title(run, rule_id),
                message=message,
                severity=level,
                file_path=file_path,
                start_line=start_line,
                start_column=start_column,
                end_line=end_line,
                end_column=end_column,
                confidence=str(properties.get("confidence") or "medium"),
                category=str(properties.get("category") or "implementation-defect"),
                invariant_id=properties.get("invariantId"),
                transition_id=properties.get("transitionId"),
                counterexample=properties.get("counterexample"),
                impact=properties.get("impact"),
                root_cause=properties.get("rootCause"),
                remediation=properties.get("remediation"),
                verification=properties.get("verification"),
                external_key=external_key,
            )
            upsert_finding(ledger, finding, run_id=run_id)
            imported += 1
    return {"imported": imported, "skipped": skipped}


def _sarif_level(severity: str) -> str:
    return {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "info": "none",
    }.get(severity, "warning")


def export_sarif(ledger: Ledger, output: Path) -> int:
    findings = list_open_findings(ledger)
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for finding in findings:
        rule_id = str(finding["rule_id"])
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": finding["title"]},
                "defaultConfiguration": {"level": _sarif_level(finding["severity"])},
                "properties": {
                    "sourceTool": finding["source_tool"],
                    "category": finding["category"],
                },
            },
        )
        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": _sarif_level(finding["severity"]),
            "message": {"text": finding["message"]},
            "partialFingerprints": {"stateGuardFindingId": str(finding["external_key"])},
            "properties": {
                "findingId": finding["id"],
                "sourceTool": finding["source_tool"],
                "confidence": finding["confidence"],
                "category": finding["category"],
                "invariantId": finding["invariant_id"],
                "transitionId": finding["transition_id"],
                "counterexample": finding["counterexample"],
                "impact": finding["impact"],
                "rootCause": finding["root_cause"],
                "remediation": finding["remediation"],
                "verification": finding["verification"],
            },
        }
        if finding["file_path"]:
            region = {
                key: value
                for key, value in {
                    "startLine": finding["start_line"] or 1,
                    "startColumn": finding["start_column"],
                    "endLine": finding["end_line"],
                    "endColumn": finding["end_column"],
                }.items()
                if value is not None
            }
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding["file_path"]},
                        "region": region,
                    }
                }
            ]
        results.append(result)

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "StateGuard",
                        "informationUri": "https://example.invalid/stateguard",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    atomic_write(output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return len(results)
