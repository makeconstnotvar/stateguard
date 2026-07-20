from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from .apg import import_apg_jsonl
from .bootstrap import initialize_project
from .config import load_config
from .db import Ledger
from .errors import StateGuardError
from .findings import FindingInput, set_finding_status, upsert_finding
from .prompt import generate_fix_prompt
from .proofs import record_proof
from .repository import discover_repo_root
from .review import claim_next_unit, complete_unit
from .sarif import export_sarif, import_sarif
from .scanner import autoplan_review_units, scan_repository
from .status import collect_status, doctor
from .validation import validate_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stateguard",
        description="StateGuard — локальный ledger и оркестратор доказательного аудита.",
    )
    parser.add_argument("--repo", help="Корень репозитория; по умолчанию определяется автоматически")
    parser.add_argument("--json", action="store_true", help="Выводить машинно-читаемый JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Создать .stateguard и audit.db")
    init.add_argument("--project-key")
    init.add_argument("--project-name")

    sub.add_parser("scan", help="Просканировать файлы и инвалидировать устаревшие доказательства")
    sub.add_parser("validate", help="Проверить config, specification, mappings и ссылки")

    plan = sub.add_parser("autoplan", help="Сформировать review units из текущего manifest")
    plan.add_argument("--replace", action="store_true")

    claim = sub.add_parser("claim", help="Атомарно забрать следующий review unit")
    claim.add_argument("--worker", required=True)
    claim.add_argument("--lease-minutes", type=int, default=60)

    complete = sub.add_parser("complete", help="Завершить review unit")
    complete.add_argument("--unit", required=True)
    complete.add_argument("--worker", required=True)
    complete.add_argument("--status", choices=["completed", "partial", "failed"], default="completed")
    complete.add_argument("--notes")

    sarif_import = sub.add_parser("import-sarif", help="Импортировать SARIF 2.1.0 в ledger")
    sarif_import.add_argument("path")

    apg_import = sub.add_parser("apg-import", help="Импортировать normalized APG JSONL")
    apg_import.add_argument("path")
    apg_import.add_argument("--source-tool")

    proof = sub.add_parser("proof-record", help="Записать proof attempt и его входные хэши")
    proof.add_argument("--key", required=True)
    proof.add_argument("--kind", required=True)
    proof.add_argument("--title", required=True)
    proof.add_argument("--description", required=True)
    proof.add_argument(
        "--status",
        required=True,
        choices=["pending", "running", "proved", "verified", "reviewed-ai", "failed", "inconclusive", "waived", "stale"],
    )
    proof.add_argument("--solver", required=True)
    proof.add_argument("--criticality", choices=["critical", "high", "medium", "low"], default="medium")
    proof.add_argument("--specification-hash")
    proof.add_argument("--input", action="append", default=[])
    proof.add_argument("--command")
    proof.add_argument("--summary")
    proof.add_argument("--counterexample")
    proof.add_argument("--tool-version")

    sarif_export = sub.add_parser("export-sarif", help="Экспортировать открытые findings для SonarQube")
    sarif_export.add_argument(
        "--output", default=".stateguard/results/stateguard.sarif", help="Путь результата"
    )

    finding_add = sub.add_parser("finding-add", help="Добавить доказательную находку вручную")
    finding_add.add_argument("--tool", default="manual-review")
    finding_add.add_argument("--rule", required=True)
    finding_add.add_argument("--title", required=True)
    finding_add.add_argument("--message", required=True)
    finding_add.add_argument("--severity", choices=["critical", "high", "medium", "low", "info"], required=True)
    finding_add.add_argument("--file")
    finding_add.add_argument("--line", type=int)
    finding_add.add_argument("--invariant")
    finding_add.add_argument("--transition")
    finding_add.add_argument("--counterexample")
    finding_add.add_argument("--impact")
    finding_add.add_argument("--root-cause")
    finding_add.add_argument("--remediation")
    finding_add.add_argument("--verification")

    finding_status = sub.add_parser("finding-status", help="Изменить статус finding")
    finding_status.add_argument("id", type=int)
    finding_status.add_argument("status")

    sub.add_parser("status", help="Показать состояние аудита")

    doctor_parser = sub.add_parser("doctor", help="Проверить критерии завершения аудита")
    doctor_parser.add_argument("--strict", action="store_true")

    prompt = sub.add_parser("generate-fix-prompt", help="Создать промпт для агента-исправителя")
    prompt.add_argument(
        "--output", default=".stateguard/reports/fix-prompt.md", help="Путь результата"
    )

    return parser


def _print(value, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            print(f"{key}: {item}")
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = discover_repo_root(args.repo)

    try:
        if args.command == "init":
            result = initialize_project(repo_root, args.project_key, args.project_name)
            _print(result, args.json)
            return 0

        ledger = Ledger(repo_root)
        ledger.initialize()

        if args.command == "scan":
            config = load_config(repo_root)
            result = scan_repository(repo_root, config, ledger)
            _print(asdict(result), args.json)
            return 0

        if args.command == "validate":
            result = validate_project(repo_root)
            payload = {
                "ok": result.ok,
                "errors": result.errors,
                "warnings": result.warnings,
                "files": result.files,
            }
            _print(payload, args.json)
            return 0 if result.ok else 2

        if args.command == "autoplan":
            config = load_config(repo_root)
            result = autoplan_review_units(repo_root, config, ledger, replace=args.replace)
            _print(result, args.json)
            return 0

        if args.command == "claim":
            result = claim_next_unit(ledger, args.worker, args.lease_minutes)
            _print(result or {"message": "Нет доступных review units"}, args.json)
            return 0

        if args.command == "complete":
            result = complete_unit(ledger, args.unit, args.worker, args.status, args.notes)
            _print(result, args.json)
            return 0

        if args.command == "import-sarif":
            result = import_sarif(ledger, (repo_root / args.path).resolve())
            _print(result, args.json)
            return 0

        if args.command == "apg-import":
            result = import_apg_jsonl(
                ledger, (repo_root / args.path).resolve(), source_tool=args.source_tool
            )
            _print(result, args.json)
            return 0

        if args.command == "proof-record":
            obligation_id = record_proof(
                ledger,
                obligation_key=args.key,
                kind=args.kind,
                title=args.title,
                description=args.description,
                status=args.status,
                solver=args.solver,
                criticality=args.criticality,
                specification_hash=args.specification_hash,
                input_paths=[(repo_root / value).resolve() for value in args.input],
                command=args.command,
                result_summary=args.summary,
                counterexample=args.counterexample,
                tool_version=args.tool_version,
            )
            _print({"obligation_id": obligation_id, "status": args.status}, args.json)
            return 0

        if args.command == "export-sarif":
            output = (repo_root / args.output).resolve()
            count = export_sarif(ledger, output)
            _print({"exported": count, "output": str(output)}, args.json)
            return 0

        if args.command == "finding-add":
            finding_id = upsert_finding(
                ledger,
                FindingInput(
                    source_tool=args.tool,
                    rule_id=args.rule,
                    title=args.title,
                    message=args.message,
                    severity=args.severity,
                    file_path=args.file,
                    start_line=args.line,
                    invariant_id=args.invariant,
                    transition_id=args.transition,
                    counterexample=args.counterexample,
                    impact=args.impact,
                    root_cause=args.root_cause,
                    remediation=args.remediation,
                    verification=args.verification,
                ),
            )
            _print({"finding_id": finding_id}, args.json)
            return 0

        if args.command == "finding-status":
            set_finding_status(ledger, args.id, args.status)
            _print({"finding_id": args.id, "status": args.status}, args.json)
            return 0

        if args.command == "status":
            _print(collect_status(ledger), args.json)
            return 0

        if args.command == "doctor":
            result = doctor(ledger, strict=args.strict)
            payload = {
                "ok": result.ok,
                "failures": result.failures,
                "warnings": result.warnings,
                "counts": result.counts,
            }
            _print(payload, args.json)
            return 0 if result.ok else 2

        if args.command == "generate-fix-prompt":
            output = (repo_root / args.output).resolve()
            count = generate_fix_prompt(ledger, output)
            _print({"findings": count, "output": str(output)}, args.json)
            return 0

        raise StateGuardError(f"Неизвестная команда: {args.command}")
    except StateGuardError as exc:
        print(f"StateGuard: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("StateGuard: выполнение прервано", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
