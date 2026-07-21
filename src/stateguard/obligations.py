from __future__ import annotations

from pathlib import Path

import yaml

from .config import ProjectConfig
from .db import Ledger
from .proofs import record_proof
from .util import sha256_file


def generate_invariant_preservation_obligations(
    repo_root: Path, config: ProjectConfig, ledger: Ledger
) -> list[str]:
    spec_path = (repo_root / config.specification).resolve()
    mapping_path = (repo_root / config.mappings).resolve()
    specification = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    spec_hash = sha256_file(spec_path)

    invariants = {
        invariant["id"]: invariant for invariant in specification.get("invariants") or []
    }
    keys: list[str] = []
    for command in specification.get("commands") or []:
        for invariant_id in command.get("preserves") or []:
            invariant = invariants[invariant_id]
            key = f"PO-{invariant_id}-BY-{command['id']}"
            record_proof(
                ledger,
                obligation_key=key,
                kind="invariant-preservation",
                title=f"{invariant['title']} preserved by {command['title']}",
                description=(
                    f"Invariant {invariant_id} must hold after {command['id']} executes "
                    "under its guards. See specification.yaml for the full "
                    "guard/outcome/postcondition text."
                ),
                status="pending",
                solver="stateguard-obligations",
                criticality=invariant["criticality"],
                specification_hash=spec_hash,
                input_paths=[spec_path, mapping_path],
            )
            keys.append(key)
    return keys
