from __future__ import annotations

import json
import shutil
from pathlib import Path

from stateguard.apg import import_apg_jsonl
from stateguard.bootstrap import initialize_project
from stateguard.db import Ledger
from stateguard.joern_adapter import build_apg, write_apg_jsonl

REAL_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "order-workflow"
SHIPMENT_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "shipment-tracking"


def _copy_real_example(tmp_path: Path, source: Path = REAL_EXAMPLE) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)
    return repo


def test_mapping_only_mode_builds_a_self_consistent_apg_from_the_real_example(tmp_path: Path) -> None:
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()

    records = build_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml")
    node_ids = {r["externalId"] for r in records if r["kind"] == "node"}

    assert "command:CMD-ORDER-SUBMIT" in node_ids
    assert "invariant:INV-ORDER-001" in node_ids
    assert "table:public.orders" in node_ids
    assert "constraint:inv_paid_order_requires_matching_payment" in node_ids
    assert "transaction:server/transaction.js:withserializableretry" in node_ids

    edges = [r for r in records if r["kind"] == "edge"]

    def has_edge(edge_type: str, source: str, target: str) -> bool:
        return any(e["type"] == edge_type and e["source"] == source and e["target"] == target for e in edges)

    assert has_edge("ENFORCES", "constraint:inv_paid_order_requires_matching_payment", "invariant:INV-ORDER-001")
    assert has_edge("CALLS", "command:CMD-ORDER-SUBMIT", "query:db/submit-order.sql")
    assert has_edge(
        "WRITES",
        "symbol:server/mark-order-paid.js:markorderpaid",
        "table:public.orders",
    )
    assert has_edge(
        "PART_OF_TRANSACTION",
        "symbol:server/mark-order-paid.js:markorderpaid",
        "transaction:server/transaction.js:withserializableretry",
    )
    # CMD-ORDER-SUBMIT is a single-statement write; it must NOT get a transaction edge.
    assert not any(e["type"] == "PART_OF_TRANSACTION" and "submitorder" in e["source"] for e in edges)

    # No mapping-gap findings: every mapped path resolves on disk.
    with ledger.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM findings WHERE category='mapping-gap'"
        ).fetchone()[0]
    assert count == 0

    # Every edge endpoint must resolve to a real node: round-trip through the same
    # loader the rest of the pipeline uses, and confirm it accepts the output as-is.
    output = repo / ".stateguard" / "results" / "apg.jsonl"
    write_apg_jsonl(records, output)
    result = import_apg_jsonl(ledger, output, source_tool="joern-apg-adapter")
    assert result["nodes"] == len(node_ids)
    assert result["edges"] == len(edges)


def test_declared_decoder_is_excluded_from_writes_via_config_not_naming(tmp_path: Path) -> None:
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()
    mapping_path = repo / "mappings.yaml"

    records = build_apg(repo, ledger, repo / "specification.yaml", mapping_path)
    edges = [r for r in records if r["kind"] == "edge"]
    decoder_id = "symbol:server/decoders.js:decodesubmitorder"

    # decodeSubmitOrder is excluded from handler-detection because it's declared under
    # framework_adapters[].rules.decoders in mappings.yaml, not because of its name.
    assert not any(e["source"] == decoder_id for e in edges)
    handler_id = "symbol:server/submit-order.js:submitorder"
    assert any(e["type"] == "WRITES" and e["source"] == handler_id for e in edges)

    # Prove the exclusion is actually caused by the `decoders:` declaration, not merely by
    # decodeSubmitOrder's name coincidentally starting with "decode": remove ONLY the
    # declaration (the selector text itself is untouched) and confirm the WRITES edge
    # reappears. Without this half, the assertions above would pass just as well against
    # the old `.lower().startswith("decode")` naming heuristic this fix replaced.
    declaration = "      decoders:\n        - decodeSubmitOrder\n"
    mapping_text = mapping_path.read_text(encoding="utf-8")
    assert declaration in mapping_text
    mapping_path.write_text(mapping_text.replace(declaration, ""), encoding="utf-8")

    records_undeclared = build_apg(repo, ledger, repo / "specification.yaml", mapping_path)
    edges_undeclared = [r for r in records_undeclared if r["kind"] == "edge"]
    assert any(e["type"] == "WRITES" and e["source"] == decoder_id for e in edges_undeclared)


def test_query_kind_node_shared_by_command_and_invariant_uses_commands_name(tmp_path: Path) -> None:
    repo = _copy_real_example(tmp_path)
    ledger = Ledger(repo)
    ledger.initialize()

    records = build_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml")
    nodes = {r["externalId"]: r for r in records if r["kind"] == "node"}
    edges = [r for r in records if r["kind"] == "edge"]

    query_id = "query:db/submit-order.sql"
    # db/submit-order.sql is referenced from CMD-ORDER-SUBMIT (selector "submit_order") and
    # from both INV-ORDER-002 and INV-ORDER-003 (descriptive-sentence selectors) — all three
    # collide on the same path-only external ID (query kind is path-only-identified). The
    # command's short identifier must win the shared node's display name: commands are
    # processed before invariants specifically so this happens deterministically.
    assert nodes[query_id]["name"] == "submit_order"

    def has_edge(edge_type: str, source: str, target: str) -> bool:
        return any(e["type"] == edge_type and e["source"] == source and e["target"] == target for e in edges)

    assert has_edge("CALLS", "command:CMD-ORDER-SUBMIT", query_id)
    # Broadened ENFORCES: an invariant-section query location (not just `kind: constraint`)
    # now gets an inbound edge to its invariant, even though the node itself was already
    # created while processing the commands section above.
    assert has_edge("ENFORCES", query_id, "invariant:INV-ORDER-002")
    assert has_edge("ENFORCES", query_id, "invariant:INV-ORDER-003")

    # But the broadening must not go so far that a merely-structural reference (a schema
    # column, not any code or DB config that rejects a violation) counts as "enforcing" —
    # INV-ORDER-003 also has a `kind: column` location (public.orders.version) that must
    # NOT get an ENFORCES edge.
    assert not has_edge("ENFORCES", "column:public.orders.version", "invariant:INV-ORDER-003")


def test_shipment_tracking_declared_decoder_closes_the_documented_gap(tmp_path: Path) -> None:
    repo = _copy_real_example(tmp_path, source=SHIPMENT_EXAMPLE)
    ledger = Ledger(repo)
    ledger.initialize()

    records = build_apg(repo, ledger, repo / "specification.yaml", repo / "mappings.yaml")
    edges = [r for r in records if r["kind"] == "edge"]
    decoder_id = "symbol:server/webhook-parser.js:parsecarrierwebhook"

    # This is the exact gap examples/shipment-tracking/README.md documented as deliberately
    # unfixed: parseCarrierWebhook plays a decoder role without a "decode" prefix. It is now
    # declared under framework_adapters[].rules.decoders instead of being renamed, proving
    # the config-driven fix closes the gap without forcing a naming convention on the target
    # codebase.
    assert not any(e["source"] == decoder_id for e in edges)


def test_enriched_mode_uses_joern_line_ranges_when_available(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")
    (repo / "server").mkdir()
    (repo / "server" / "handler.js").write_text("export function doThing() {}\n", encoding="utf-8")

    spec_path = repo / "specification.yaml"
    spec_path.write_text(
        "version: 1\nproject: repo\nentities: []\nstates: []\ninvariants: []\n"
        "commands:\n  - id: CMD-X\n    title: Do X\n    preserves: []\n"
        "observations: []\nexternal_effects: []\n",
        encoding="utf-8",
    )
    mapping_path = repo / "mappings.yaml"
    mapping_path.write_text(
        "version: 1\nproject: repo\ncomponents: []\nentities: []\ninvariants: []\n"
        "commands:\n  - id: CMD-X\n    locations:\n      - kind: symbol\n"
        "        selector: doThing\n        path: server/handler.js\n"
        "observations: []\nframework_adapters: []\n",
        encoding="utf-8",
    )

    joern_dir = repo / "joern-out"
    joern_dir.mkdir()
    (joern_dir / "methods.json").write_text(
        json.dumps([{"name": "doThing", "filename": "server/handler.js", "lineNumber": 1, "lineNumberEnd": 1}]),
        encoding="utf-8",
    )

    ledger = Ledger(repo)
    ledger.initialize()
    records = build_apg(repo, ledger, spec_path, mapping_path, joern_dir=joern_dir)
    node = next(r for r in records if r["kind"] == "node" and r["type"] == "Symbol")
    assert node["sourceTool"] == "joern-apg-adapter"
    assert node["range"] == {"startLine": 1, "endLine": 1}
    assert node["properties"]["confidence"] == "observed"


def test_missing_mapped_path_creates_low_severity_finding_and_skips_node(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    initialize_project(repo, "repo", "Repo")

    spec_path = repo / "specification.yaml"
    spec_path.write_text(
        "version: 1\nproject: repo\nentities: []\nstates: []\ninvariants: []\ncommands: []\n"
        "observations: []\nexternal_effects: []\n",
        encoding="utf-8",
    )
    mapping_path = repo / "mappings.yaml"
    mapping_path.write_text(
        "version: 1\nproject: repo\ncomponents: []\n"
        "entities:\n  - id: ENT-X\n    locations:\n      - kind: symbol\n"
        "        selector: ghost\n        path: does/not/exist.js\n"
        "invariants: []\ncommands: []\nobservations: []\nframework_adapters: []\n",
        encoding="utf-8",
    )

    ledger = Ledger(repo)
    ledger.initialize()
    records = build_apg(repo, ledger, spec_path, mapping_path)

    node_ids = {r["externalId"] for r in records if r["kind"] == "node"}
    assert "symbol:does/not/exist.js:ghost" not in node_ids

    with ledger.connect() as connection:
        row = connection.execute(
            "SELECT category, severity, file_path FROM findings WHERE category='mapping-gap'"
        ).fetchone()
    assert row["severity"] == "low"
    assert row["file_path"] == "does/not/exist.js"
