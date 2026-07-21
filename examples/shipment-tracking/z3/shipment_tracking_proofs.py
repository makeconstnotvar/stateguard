#!/usr/bin/env python3
"""Bounded, machine-checked restatements of the 6 invariant-preservation obligations
generated from examples/shipment-tracking/specification.yaml (see
src/stateguard/obligations.py for the generation rule).

Unlike examples/order-workflow/z3/order_workflow_proofs.py (three proofs: terminal-state
irreversibility, version-increments-on-mutation, cross-table payment match), these six
exercise four different shapes:
  - an inequality guard over an externally-supplied, adversarial input (sequence_no),
    not a system-generated counter (PO-INV-SHIP-001-BY-CMD-SHIPMENT-RECORD-CHECKPOINT);
  - an idempotent-replay-as-no-op branch, `Implies(already_processed, post == pre)`
    (PO-INV-SHIP-002-BY-CMD-SHIPMENT-RECORD-CHECKPOINT);
  - an "establishment" proof for a from-scratch creation command, where there is no
    pre-state to preserve from (the two CMD-SHIPMENT-CREATE obligations);
  - a finite-state-machine well-formedness check over the *result* of a transition
    (PO-INV-SHIP-004-BY-CMD-SHIPMENT-RECORD-CHECKPOINT — see note below on why this
    needed its own invariant rather than piggybacking on an existing one).

Same caveat as order-workflow's script: these are small, bounded, single-transition
proofs that the guard/postcondition pairs declared in specification.yaml are internally
consistent with the invariants they claim to preserve — regression-protecting, not an
independent discovery of deep hidden bugs.

An adversarial review of the first version of this file (which had only 5 obligations)
found two real gaps, both fixed here:
  - PO-INV-SHIP-001-BY-CMD-SHIPMENT-RECORD-CHECKPOINT's goal was `last_sequence_post >=
    last_sequence_pre` — non-strict monotonicity — even though INV-SHIP-001 itself
    declares *strictly* increasing order. Weakening the real guard from `sequence_no >
    last_sequence_pre` to `>=` still passed this goal. Fixed by proving
    `Implies(accept_guard, last_sequence_post > last_sequence_pre)` instead.
  - The `code in allowed_next(status)` guard was encoded in `_allowed_next()` and used
    inside `accept_guard`, but no proof goal for any of the original 5 obligations
    actually depended on it — deleting the conjunct from `accept_guard` still left all 5
    "PROVED". That guard protects a real property (the shipment only moves along valid
    FSM edges) that was never declared as its own invariant, so nothing could reference
    it. Fixed by adding INV-SHIP-004 to specification.yaml and giving it a proof whose
    goal genuinely depends on `_allowed_next` holding — re-verified by deleting the
    conjunct again after the fix and confirming only this one proof now fails.

Install optional dependency:
    pip install 'z3-solver>=4.13,<5'
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass

from z3 import And, Bool, If, Implies, Int, Not, Or, Solver, sat

# shipment.status / checkpoint.code enum (shared space; code only ever takes the
# non-initial values)
PENDING, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, EXCEPTION = 0, 1, 2, 3, 4


@dataclass(slots=True)
class ObligationResult:
    key: str
    status: str
    summary: str
    counterexample: str | None = None


def _terminal(status) -> bool:
    return Or(status == DELIVERED, status == EXCEPTION)


def _allowed_next(status, code) -> bool:
    return Or(
        And(status == PENDING, Or(code == IN_TRANSIT, code == EXCEPTION)),
        And(status == IN_TRANSIT, Or(code == OUT_FOR_DELIVERY, code == EXCEPTION)),
        And(status == OUT_FOR_DELIVERY, Or(code == DELIVERED, code == EXCEPTION)),
    )


def _prove(key: str, summary: str, hypotheses: list, goal) -> ObligationResult:
    solver = Solver()
    solver.add(*hypotheses, Not(goal))
    if solver.check() == sat:
        return ObligationResult(key, "failed", summary, str(solver.model()))
    return ObligationResult(key, "proved", summary)


def _create_obligations() -> list[ObligationResult]:
    # CMD-SHIPMENT-CREATE has no pre-state for the shipment being created — these are
    # "establishment" proofs (the freshly created row satisfies the invariant), not
    # preservation-across-a-transition proofs like the other three.
    status_post, last_sequence_post = Int("status_post"), Int("last_sequence_post")
    highest_checkpoint_seq = Int("highest_checkpoint_seq")

    # CMD-SHIPMENT-CREATE's accepted postconditions, from specification.yaml.
    postconditions = [status_post == PENDING, last_sequence_post == 0]
    # A freshly created shipment has no checkpoints yet.
    no_checkpoints_yet = highest_checkpoint_seq == 0

    inv_001 = _prove(
        "PO-INV-SHIP-001-BY-CMD-SHIPMENT-CREATE",
        "A freshly created shipment's last_sequence matches its (empty) checkpoint history",
        [*postconditions, no_checkpoints_yet],
        last_sequence_post == highest_checkpoint_seq,
    )
    inv_003 = _prove(
        "PO-INV-SHIP-003-BY-CMD-SHIPMENT-CREATE",
        "A freshly created shipment is not already in a terminal state",
        postconditions,
        Not(_terminal(status_post)),
    )
    return [inv_001, inv_003]


def _record_checkpoint_obligations() -> list[ObligationResult]:
    status_pre, status_post = Int("status_pre"), Int("status_post")
    last_sequence_pre, last_sequence_post = Int("last_sequence_pre"), Int("last_sequence_post")
    sequence_no = Int("sequence_no")  # externally supplied by the carrier — adversarial input
    code = Int("code")  # externally supplied checkpoint code
    already_processed = Bool("already_processed")  # abstract: this provider_event_id seen before

    # CMD-SHIPMENT-RECORD-CHECKPOINT's accept guard, from specification.yaml. The
    # duplicate check happens first (matches the real code's evaluation order), then
    # terminal/ordering/transition guards — all four rejection outcomes collapse to
    # "no mutation" for state-transition purposes.
    accept_guard = And(
        Not(already_processed),
        Not(_terminal(status_pre)),
        sequence_no > last_sequence_pre,
        _allowed_next(status_pre, code),
    )
    transition = [
        status_post == If(accept_guard, code, status_pre),
        last_sequence_post == If(accept_guard, sequence_no, last_sequence_pre),
    ]

    inv_001 = _prove(
        "PO-INV-SHIP-001-BY-CMD-SHIPMENT-RECORD-CHECKPOINT",
        "Every real transition strictly increases last_sequence (not just non-decreasing)",
        transition,
        Implies(accept_guard, last_sequence_post > last_sequence_pre),
    )
    inv_004 = _prove(
        "PO-INV-SHIP-004-BY-CMD-SHIPMENT-RECORD-CHECKPOINT",
        "The resulting status is either unchanged or reached via a valid FSM edge from status_pre",
        transition,
        Or(status_post == status_pre, _allowed_next(status_pre, status_post)),
    )
    inv_002 = _prove(
        "PO-INV-SHIP-002-BY-CMD-SHIPMENT-RECORD-CHECKPOINT",
        "Replaying an already-processed provider_event_id is a pure no-op",
        transition,
        Implies(already_processed, And(status_post == status_pre, last_sequence_post == last_sequence_pre)),
    )
    inv_003 = _prove(
        "PO-INV-SHIP-003-BY-CMD-SHIPMENT-RECORD-CHECKPOINT",
        "Terminal shipment states are irreversible across CMD-SHIPMENT-RECORD-CHECKPOINT",
        transition,
        Implies(_terminal(status_pre), status_post == status_pre),
    )
    return [inv_001, inv_002, inv_003, inv_004]


def run_all() -> list[ObligationResult]:
    return _create_obligations() + _record_checkpoint_obligations()


def main() -> int:
    import z3

    results = run_all()
    as_json = "--json" in sys.argv
    if as_json:
        payload = [dict(asdict(result), tool_version=z3.get_version_string()) for result in results]
        print(json.dumps(payload))
    else:
        for result in results:
            if result.status == "proved":
                print(f"PROVED: {result.key} — {result.summary}")
            else:
                print(f"FAILED: {result.key} — {result.summary}\n  counterexample: {result.counterexample}")
    return 0 if all(result.status == "proved" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
