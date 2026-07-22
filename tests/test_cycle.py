from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stateguard import cycle
from stateguard.config import load_config
from stateguard.cycle import CycleReport, _stage_joern_and_apg
from stateguard.db import Ledger

REAL_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "order-workflow"


def _copy_real_example(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(REAL_EXAMPLE, repo)
    return repo


def _fake_run_ok(*_args, **_kwargs) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_joern_exit_zero_with_no_enriched_symbols_reports_failed_not_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Reproduces a real observed failure mode: joern-parse/joern exit 0 (e.g. astgen
    # silently resolving to the wrong binary) but the CPG export matches nothing. Exit
    # code alone must not be trusted as a proxy for "enrichment actually happened" —
    # order-workflow's mappings.yaml has real kind:symbol locations, so a genuine
    # enrichment attempt that comes back empty is a failure, not an "ok".
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    config = load_config(repo)
    # A prior *real* `scripts/run-joern.sh` run against the checked-out
    # examples/order-workflow tree (gitignored, but still present on disk on a machine
    # that has actually run live Joern) must not leak into this fixture's copy — the
    # whole point of this test is a genuinely empty export.
    shutil.rmtree(repo / config.joern_output, ignore_errors=True)

    monkeypatch.setattr(cycle, "_has_tool", lambda name: True)
    monkeypatch.setattr(cycle, "_run", _fake_run_ok)

    report = CycleReport()
    _stage_joern_and_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml", config, report)

    stages = {s.name: s for s in report.stages}
    assert stages["joern"].status == "failed"
    assert "enriched none of" in stages["joern"].message
    assert "mapping-only mode" in stages["apg"].message


def test_joern_exit_zero_with_real_enrichment_data_reports_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    config = load_config(repo)

    joern_dir = repo / config.joern_output
    joern_dir.mkdir(parents=True, exist_ok=True)
    (joern_dir / "methods.json").write_text(
        json.dumps(
            [{"name": "submitOrder", "filename": "server/submit-order.js", "lineNumber": 3, "lineNumberEnd": 39}]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cycle, "_has_tool", lambda name: True)
    monkeypatch.setattr(cycle, "_run", _fake_run_ok)

    report = CycleReport()
    _stage_joern_and_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml", config, report)

    stages = {s.name: s for s in report.stages}
    assert stages["joern"].status == "ok"
    assert "enriched mode" in stages["apg"].message


def test_joern_not_installed_skips_without_attempting_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    config = load_config(repo)

    monkeypatch.setattr(cycle, "_has_tool", lambda name: False)

    report = CycleReport()
    _stage_joern_and_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml", config, report)

    stages = {s.name: s for s in report.stages}
    assert stages["joern"].status == "skipped"
    assert "mapping-only mode" in stages["apg"].message
