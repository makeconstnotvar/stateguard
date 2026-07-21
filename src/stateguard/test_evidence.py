from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .db import Ledger
from .proofs import record_proof

_RESULT_RE = re.compile(r"^(ok|not ok)\s+\d+\s+-\s+(.+)$")


@dataclass(slots=True)
class TapResult:
    title: str
    ok: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def failure_detail(self) -> str | None:
        if self.ok:
            return None
        error = self.diagnostics.get("error")
        return str(error) if error else None


def parse_tap(text: str) -> list[TapResult]:
    """Parse `node --test --test-reporter=tap` output.

    Node's TAP13 output follows each result line with a genuine YAML diagnostic block
    (`  ---` ... `  ...`), so the diagnostics are parsed with a real YAML loader rather
    than hand-rolled field extraction — verified directly against real `node --test`
    output (Node 24), not guessed from the spec.
    """
    lines = text.splitlines()
    results: list[TapResult] = []
    index = 0
    while index < len(lines):
        match = _RESULT_RE.match(lines[index].strip())
        index += 1
        if not match:
            continue
        ok = match.group(1) == "ok"
        title = match.group(2).strip()

        diagnostics: dict[str, Any] = {}
        if index < len(lines) and lines[index].strip() == "---":
            block_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "...":
                line = lines[index]
                block_lines.append(line[2:] if line.startswith("  ") else line)
                index += 1
            index += 1  # skip the closing '...'
            try:
                parsed = yaml.safe_load("\n".join(block_lines))
            except yaml.YAMLError:
                parsed = None
            if isinstance(parsed, dict):
                diagnostics = parsed

        results.append(TapResult(title, ok, diagnostics))
    return results


@dataclass(slots=True)
class ObligationEvidence:
    obligation_key: str
    criticality: str
    result: TapResult


def map_test_results_to_obligations(
    results: list[TapResult], specification: dict[str, Any], mapping: dict[str, Any]
) -> list[ObligationEvidence]:
    """Derive obligation coverage from mappings.yaml — never hardcoded.

    A command's own `kind: test` location covers `PO-<inv>-BY-<command>` for every
    invariant it preserves. An invariant's own `kind: test` location covers
    `PO-<inv>-BY-<command>` for every command that preserves it. Matches
    src/stateguard/obligations.py's `PO-<invariant>-BY-<command>` naming exactly.
    """
    by_title = {result.title: result for result in results}
    commands = {item["id"]: item for item in specification.get("commands") or [] if item.get("id")}
    invariants = {item["id"]: item for item in specification.get("invariants") or [] if item.get("id")}

    evidence: list[ObligationEvidence] = []
    seen: set[str] = set()

    def add(invariant_id: str, command_id: str, result: TapResult) -> None:
        key = f"PO-{invariant_id}-BY-{command_id}"
        if key in seen:
            return
        seen.add(key)
        criticality = invariants.get(invariant_id, {}).get("criticality", "medium")
        evidence.append(ObligationEvidence(key, criticality, result))

    for command_map in mapping.get("commands") or []:
        command_id = command_map.get("id")
        preserves = (commands.get(command_id) or {}).get("preserves") or []
        for location in command_map.get("locations") or []:
            if location.get("kind") != "test":
                continue
            result = by_title.get(location.get("selector"))
            if result is None:
                continue
            for invariant_id in preserves:
                add(invariant_id, command_id, result)

    for invariant_map in mapping.get("invariants") or []:
        invariant_id = invariant_map.get("id")
        for location in invariant_map.get("locations") or []:
            if location.get("kind") != "test":
                continue
            result = by_title.get(location.get("selector"))
            if result is None:
                continue
            for command_id, command_spec in commands.items():
                if invariant_id in (command_spec.get("preserves") or []):
                    add(invariant_id, command_id, result)

    return evidence


def record_test_evidence(
    ledger: Ledger,
    spec_path: Path,
    mapping_path: Path,
    tap_text: str,
    input_paths: list[Path],
) -> dict[str, str]:
    specification = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    evidence = map_test_results_to_obligations(parse_tap(tap_text), specification, mapping)

    recorded: dict[str, str] = {}
    for item in evidence:
        status = "verified" if item.result.ok else "failed"
        record_proof(
            ledger,
            obligation_key=item.obligation_key,
            kind="integration-test",
            title=f"Integration test evidence for {item.obligation_key}",
            description=f"node:test evidence from {item.result.title!r}.",
            status=status,
            solver="node:test+testcontainers",
            criticality=item.criticality,
            input_paths=input_paths,
            result_summary=item.result.title,
            counterexample=item.result.failure_detail,
        )
        recorded[item.obligation_key] = status
    return recorded
