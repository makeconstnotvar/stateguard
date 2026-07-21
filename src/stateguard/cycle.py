from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .ai_review import run_ai_review
from .apg import import_apg_jsonl
from .bootstrap import GITIGNORE_TEMPLATE
from .config import ProjectConfig, load_config
from .db import Ledger
from .joern_adapter import build_apg, write_apg_jsonl
from .obligations import generate_invariant_preservation_obligations
from .probcli_parser import parse_prob_output
from .proofs import record_proof
from .review import claim_next_unit, complete_unit
from .rules import sync_semgrep_rules
from .sarif import import_sarif
from .scanner import autoplan_review_units, scan_repository
from .status import doctor
from .test_evidence import record_test_evidence
from .util import atomic_write
from .validation import validate_project

ALL_STAGES = (
    "validate",
    "scan",
    "semgrep",
    "joern",
    "obligations",
    "event-b",
    "z3",
    "ai-review",
    "tests",
)

AUTO_REVIEW_NOTES = (
    "Auto-completed by stateguard run-cycle for walking-skeleton demonstration; "
    "NOT a substitute for human code review."
)


@dataclass(slots=True)
class StageResult:
    name: str
    status: str  # "ok" | "skipped" | "failed"
    message: str = ""


@dataclass(slots=True)
class CycleReport:
    stages: list[StageResult] = field(default_factory=list)
    doctor: dict[str, Any] | None = None


def _kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _existing_criticality(ledger: Ledger, obligation_key: str, default: str = "medium") -> str:
    with ledger.connect() as connection:
        row = connection.execute(
            "SELECT criticality FROM proof_obligations WHERE obligation_key=?", (obligation_key,)
        ).fetchone()
    return row["criticality"] if row else default


def _stage_setup(repo_root: Path, ledger: Ledger, report: CycleReport) -> None:
    state = repo_root / ".stateguard"
    for directory in (state, state / "results", state / "reports", state / "rules", state / "work"):
        directory.mkdir(parents=True, exist_ok=True)
    gitignore = state / ".gitignore"
    if not gitignore.exists():
        atomic_write(gitignore, GITIGNORE_TEMPLATE)
    ledger.initialize()
    report.stages.append(StageResult("setup", "ok"))


def _stage_validate(repo_root: Path, report: CycleReport) -> None:
    result = validate_project(repo_root)
    status = "ok" if result.ok else "failed"
    message = "clean" if result.ok else "; ".join(result.errors)
    report.stages.append(StageResult("validate", status, message))


def _stage_scan_and_review(
    repo_root: Path, config: ProjectConfig, ledger: Ledger, report: CycleReport, auto_complete_review: bool
) -> None:
    scan_repository(repo_root, config, ledger)
    autoplan_review_units(repo_root, config, ledger)
    if not auto_complete_review:
        report.stages.append(StageResult("scan", "ok", "review units left for human claim"))
        return

    completed = 0
    while True:
        claimed = claim_next_unit(ledger, worker="stateguard-run-cycle", lease_minutes=5)
        if claimed is None:
            break
        complete_unit(ledger, claimed["unit_key"], "stateguard-run-cycle", "completed", notes=AUTO_REVIEW_NOTES)
        completed += 1
    report.stages.append(
        StageResult("scan", "ok", f"{completed} review unit(s) auto-completed (demo simplification)")
    )


def _stage_semgrep(repo_root: Path, config: ProjectConfig, ledger: Ledger, report: CycleReport) -> None:
    sync_semgrep_rules(repo_root, config)
    rules_dir = repo_root / ".stateguard" / "rules"
    output = (repo_root / config.semgrep_report).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if _has_tool("semgrep") and any(rules_dir.rglob("*.y*ml")):
        result = _run(
            ["semgrep", "scan", "--metrics=off", "--config", str(rules_dir), "--sarif", "--output", str(output), "."],
            cwd=repo_root,
            timeout=300,
        )
        if result.returncode not in (0, 1):  # semgrep exits 1 when findings were reported, not an error
            report.stages.append(StageResult("semgrep", "failed", (result.stderr or result.stdout)[-500:]))
            return
    elif _has_tool("docker"):
        script = _kit_root() / "scripts" / "run-semgrep.sh"
        result = _run(["bash", str(script), str(repo_root)], timeout=300)
        if result.returncode != 0:
            report.stages.append(StageResult("semgrep", "failed", (result.stderr or result.stdout)[-500:]))
            return
    else:
        report.stages.append(StageResult("semgrep", "skipped", "SKIPPED: semgrep and docker both not installed"))
        return

    if output.exists():
        imported = import_sarif(ledger, output)
        report.stages.append(StageResult("semgrep", "ok", f"{imported['imported']} finding(s) imported"))
    else:
        report.stages.append(StageResult("semgrep", "ok", "ran, no SARIF output produced"))


def _stage_joern_and_apg(
    repo_root: Path,
    ledger: Ledger,
    spec_path: Path,
    mapping_path: Path,
    config: ProjectConfig,
    report: CycleReport,
) -> None:
    joern_dir = (repo_root / config.joern_output).resolve()
    enriched = False
    if _has_tool("joern-parse") and _has_tool("joern"):
        script = _kit_root() / "scripts" / "run-joern.sh"
        result = _run(["bash", str(script), str(repo_root)], timeout=1800)
        if result.returncode == 0:
            enriched = True
            report.stages.append(StageResult("joern", "ok", "raw CPG export written"))
        else:
            report.stages.append(StageResult("joern", "failed", (result.stderr or result.stdout)[-500:]))
    else:
        report.stages.append(StageResult("joern", "skipped", "SKIPPED: joern/joern-parse not installed"))

    records = build_apg(repo_root, ledger, spec_path, mapping_path, joern_dir=joern_dir if enriched else None)
    output = repo_root / ".stateguard" / "results" / "apg.jsonl"
    write_apg_jsonl(records, output)
    import_result = import_apg_jsonl(
        ledger, output, source_tool="joern-apg-adapter" if enriched else "stateguard-mapping"
    )
    mode = "enriched" if enriched else "mapping-only"
    report.stages.append(
        StageResult(
            "apg", "ok", f"built in {mode} mode: {import_result['nodes']} nodes, {import_result['edges']} edges"
        )
    )


def _stage_generate_obligations(
    repo_root: Path, config: ProjectConfig, ledger: Ledger, report: CycleReport
) -> None:
    keys = generate_invariant_preservation_obligations(repo_root, config, ledger)
    report.stages.append(StageResult("obligations", "ok", f"{len(keys)} obligation(s) generated"))


def _stage_event_b(repo_root: Path, config: ProjectConfig, ledger: Ledger, report: CycleReport) -> None:
    if not _has_tool("probcli"):
        report.stages.append(StageResult("event-b", "skipped", "SKIPPED: probcli not installed"))
        return
    if not config.event_b_project:
        report.stages.append(
            StageResult("event-b", "skipped", "SKIPPED: specification.event_b_project not configured")
        )
        return

    # Convention: specification.event_b_project (schemas/stateguard.schema.json) points
    # at a directory (possibly outside repo_root, e.g. "../../event-b" for a project
    # sharing the kit's pilot model) containing *.mch model(s) and a
    # proof-obligations.yaml linking model labels to PO-* keys — same shape as
    # event-b/proof-obligations.yaml. run-prob.sh itself stays kit-level generic tooling.
    project_dir = (repo_root / config.event_b_project).resolve()
    models = sorted(project_dir.glob("*.mch"))
    obligations_path = project_dir / "proof-obligations.yaml"
    if not models or not obligations_path.exists():
        report.stages.append(
            StageResult(
                "event-b", "skipped", f"SKIPPED: {config.event_b_project} has no *.mch or proof-obligations.yaml"
            )
        )
        return

    run_prob = _kit_root() / "event-b" / "run-prob.sh"
    out_dir = repo_root / ".stateguard" / "results" / "event-b"
    out_dir.mkdir(parents=True, exist_ok=True)

    obligations_doc = yaml.safe_load(obligations_path.read_text(encoding="utf-8")) or {}
    keys: set[str] = set()
    for link in obligations_doc.get("links") or []:
        keys.update(link.get("obligations") or [])

    summaries: list[str] = []
    any_failed = False
    for model in models:
        log_path = out_dir / f"{model.stem}.prob-run.log"
        result = _run(["bash", str(run_prob), str(model), str(log_path)], timeout=900)
        text = log_path.read_text(encoding="utf-8") if log_path.exists() else (result.stdout + result.stderr)
        parsed = parse_prob_output(text)
        summaries.append(f"{model.name}: {parsed.status}")
        any_failed = any_failed or parsed.status == "failed"

        for key in sorted(keys):
            record_proof(
                ledger,
                obligation_key=key,
                kind="event-b-model-check",
                title=f"Event-B/ProB model-check evidence for {key}",
                description=f"See {model.name} and {obligations_path.name} in {config.event_b_project}.",
                status=parsed.status,
                solver="probcli",
                criticality=_existing_criticality(ledger, key),
                input_paths=[model, obligations_path],
                result_summary=parsed.summary,
                counterexample=parsed.counterexample,
                tool_version=parsed.tool_version,
            )
    report.stages.append(StageResult("event-b", "failed" if any_failed else "ok", "; ".join(summaries)))


def _stage_z3(repo_root: Path, ledger: Ledger, spec_path: Path, report: CycleReport) -> None:
    # Convention: proof scripts live at <repo_root>/z3/*.py, each accepting --json and
    # printing a JSON array of {key, status, summary, counterexample, tool_version} —
    # see examples/order-workflow/z3/order_workflow_proofs.py for the reference shape.
    scripts = sorted((repo_root / "z3").glob("*.py")) if (repo_root / "z3").exists() else []
    if not scripts:
        report.stages.append(StageResult("z3", "skipped", "SKIPPED: no z3/*.py proof scripts found"))
        return

    proved = 0
    total = 0
    failed_scripts: list[str] = []
    for script in scripts:
        result = _run([sys.executable, str(script), "--json"], timeout=120)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            failed_scripts.append(script.name)
            continue

        for item in payload:
            total += 1
            key = item["key"]
            status = "proved" if item["status"] == "proved" else "failed"
            proved += status == "proved"
            record_proof(
                ledger,
                obligation_key=key,
                kind="z3-invariant-preservation",
                title=f"Z3 proof for {key}",
                description=item["summary"],
                status=status,
                solver="z3",
                criticality=_existing_criticality(ledger, key),
                tool_version=item.get("tool_version"),
                input_paths=[spec_path, script],
                command=f"python {script.name} --json",
                result_summary=item["summary"],
                counterexample=item.get("counterexample"),
            )

    message = f"{proved}/{total} obligation(s) proved across {len(scripts)} script(s)"
    if failed_scripts:
        message += f"; non-JSON output from: {', '.join(failed_scripts)}"
    report.stages.append(StageResult("z3", "failed" if failed_scripts and total == 0 else "ok", message))


def _stage_ai_review(repo_root: Path, ledger: Ledger, spec_path: Path, report: CycleReport) -> None:
    result = run_ai_review(ledger, repo_root, spec_path)
    if result.get("status") == "skipped":
        report.stages.append(StageResult("ai-review", "skipped", result["reason"]))
    else:
        report.stages.append(
            StageResult(
                "ai-review", "ok", f"{len(result['reviewed'])} reviewed, {len(result['errors'])} error(s)"
            )
        )


def _stage_tests(
    repo_root: Path, ledger: Ledger, spec_path: Path, mapping_path: Path, report: CycleReport
) -> None:
    if not _has_tool("docker"):
        report.stages.append(
            StageResult(
                "tests", "skipped", "SKIPPED: docker not installed; testcontainers cannot start postgres:17"
            )
        )
        return

    test_files = sorted((repo_root / "tests").glob("*.test.js")) if (repo_root / "tests").exists() else []
    if not test_files:
        report.stages.append(StageResult("tests", "skipped", "no tests/*.test.js found"))
        return

    if not (repo_root / "node_modules").exists():
        install = _run(["npm", "install"], cwd=repo_root, timeout=600)
        if install.returncode != 0:
            report.stages.append(StageResult("tests", "failed", install.stderr[-500:]))
            return

    result = _run(
        ["node", "--test", "--test-reporter=tap", "--test-reporter-destination=stdout"]
        + [str(f) for f in test_files],
        cwd=repo_root,
        timeout=600,
    )
    recorded = record_test_evidence(ledger, spec_path, mapping_path, result.stdout, test_files)
    report.stages.append(StageResult("tests", "ok", json.dumps(recorded)))


def run_cycle(
    repo_root: Path,
    *,
    skip: frozenset[str] = frozenset(),
    auto_complete_review: bool = True,
    strict_doctor: bool = True,
) -> CycleReport:
    repo_root = repo_root.resolve()
    report = CycleReport()
    ledger = Ledger(repo_root)

    _stage_setup(repo_root, ledger, report)
    config = load_config(repo_root)
    spec_path = (repo_root / config.specification).resolve()
    mapping_path = (repo_root / config.mappings).resolve()

    if "validate" not in skip:
        _stage_validate(repo_root, report)
    if "scan" not in skip:
        _stage_scan_and_review(repo_root, config, ledger, report, auto_complete_review)
    if "semgrep" not in skip:
        _stage_semgrep(repo_root, config, ledger, report)
    if "joern" not in skip:
        _stage_joern_and_apg(repo_root, ledger, spec_path, mapping_path, config, report)
    if "obligations" not in skip:
        _stage_generate_obligations(repo_root, config, ledger, report)
    if "event-b" not in skip:
        _stage_event_b(repo_root, config, ledger, report)
    if "z3" not in skip:
        _stage_z3(repo_root, ledger, spec_path, report)
    if "ai-review" not in skip:
        _stage_ai_review(repo_root, ledger, spec_path, report)
    if "tests" not in skip:
        _stage_tests(repo_root, ledger, spec_path, mapping_path, report)

    doctor_result = doctor(ledger, strict=strict_doctor)
    report.doctor = {
        "ok": doctor_result.ok,
        "failures": doctor_result.failures,
        "warnings": doctor_result.warnings,
        "counts": doctor_result.counts,
    }
    report.stages.append(
        StageResult("doctor", "ok" if doctor_result.ok else "failed", "; ".join(doctor_result.failures) or "clean")
    )
    return report
