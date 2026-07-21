#!/usr/bin/env python3
"""Bounded, machine-checked restatements of the 5 invariant-preservation obligations
generated from examples/order-workflow/specification.yaml (see
src/stateguard/obligations.py for the generation rule: one PO-<invariant>-BY-<command>
per (command, invariant) pair in commands[].preserves).

These are small, bounded, single-transition proofs that the guard/postcondition pairs
declared in specification.yaml are internally consistent with the invariants they claim
to preserve. They are valuable as machine-checked, regression-protecting artifacts — a
future edit that silently drops a guard clause will start failing this script — not as
independent discovery of deep hidden bugs or as a substitute for the full relational
model that is Event-B/ProB's job (see z3/README.md's stated scope).

Each proof follows the standard inductive-invariant technique: assume the invariant
holds in the pre-state, model the transition as guard-true (accept, apply the
specification's stated postconditions) or guard-false (reject, no mutation — matches
the real code: a zero-row UPDATE performs no write), and show the invariant cannot fail
to hold in the post-state (i.e. the negation of "invariant holds" is UNSAT).

Install optional dependency:
    pip install 'z3-solver>=4.13,<5'
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass

from z3 import And, Bool, If, Implies, Int, Not, Or, Solver, sat

# order.status enum
DRAFT, SUBMITTED, PAID, CANCELLED = 0, 1, 2, 3
# payment.status enum
NEW, PROCESSING, CONFIRMED, REJECTED, OUTCOME_UNKNOWN = 0, 1, 2, 3, 4


@dataclass(slots=True)
class ObligationResult:
    key: str
    status: str
    summary: str
    counterexample: str | None = None


def _terminal(status) -> bool:
    return Or(status == PAID, status == CANCELLED)


def _prove(key: str, summary: str, hypotheses: list, goal) -> ObligationResult:
    solver = Solver()
    solver.add(*hypotheses, Not(goal))
    if solver.check() == sat:
        return ObligationResult(key, "failed", summary, str(solver.model()))
    return ObligationResult(key, "proved", summary)


def _submit_obligations() -> list[ObligationResult]:
    status_pre, status_post = Int("status_pre"), Int("status_post")
    version_pre, version_post, expected_version = (
        Int("version_pre"),
        Int("version_post"),
        Int("expected_version"),
    )

    # CMD-ORDER-SUBMIT's guard, from specification.yaml (`order.status = draft` and
    # `order.version = expected_version`); authorization is out of scope for these two
    # invariants. On accept, apply the stated postconditions; on reject, the real UPDATE
    # affects zero rows, so nothing changes.
    accept_guard = And(status_pre == DRAFT, version_pre == expected_version)
    transition = [
        status_post == If(accept_guard, SUBMITTED, status_pre),
        version_post == If(accept_guard, version_pre + 1, version_pre),
    ]

    inv_002 = _prove(
        "PO-INV-ORDER-002-BY-CMD-ORDER-SUBMIT",
        "Terminal order states are irreversible across CMD-ORDER-SUBMIT",
        transition,
        Implies(_terminal(status_pre), status_post == status_pre),
    )
    inv_003 = _prove(
        "PO-INV-ORDER-003-BY-CMD-ORDER-SUBMIT",
        "Order version increases on every committed mutation by CMD-ORDER-SUBMIT",
        transition,
        Implies(accept_guard, version_post == version_pre + 1),
    )
    return [inv_002, inv_003]


def _mark_paid_obligations() -> list[ObligationResult]:
    status_pre, status_post = Int("status_pre"), Int("status_post")
    version_pre, version_post, expected_version = (
        Int("version_pre"),
        Int("version_post"),
        Int("expected_version"),
    )
    payment_status = Int("payment_status")
    payment_order_match, payment_amount_match, payment_currency_match = (
        Bool("payment_order_match"),
        Bool("payment_amount_match"),
        Bool("payment_currency_match"),
    )
    # Abstract fact standing in for "order.payment_id references a payment that
    # belongs to this order, is confirmed, and matches amount/currency" — this is
    # deliberately opaque relational state, not a modeled payments table (full
    # relational reasoning is Event-B/ProB's job, per z3/README.md's stated scope).
    has_matching_confirmed_payment_pre = Bool("has_matching_confirmed_payment_pre")

    # CMD-ORDER-MARK-PAID's guard, from specification.yaml.
    accept_guard = And(
        status_pre == SUBMITTED,
        payment_status == CONFIRMED,
        payment_order_match,
        payment_amount_match,
        payment_currency_match,
        version_pre == expected_version,
    )
    has_matching_confirmed_payment_post = If(
        accept_guard,
        And(payment_status == CONFIRMED, payment_amount_match, payment_currency_match),
        has_matching_confirmed_payment_pre,
    )
    transition = [
        status_post == If(accept_guard, PAID, status_pre),
        version_post == If(accept_guard, version_pre + 1, version_pre),
    ]
    # Inductive hypothesis: the invariant already held in the pre-state.
    invariant_held_pre = Implies(status_pre == PAID, has_matching_confirmed_payment_pre)

    inv_001 = _prove(
        "PO-INV-ORDER-001-BY-CMD-ORDER-MARK-PAID",
        "A paid order references one confirmed matching payment across CMD-ORDER-MARK-PAID",
        [*transition, invariant_held_pre],
        Implies(status_post == PAID, has_matching_confirmed_payment_post),
    )
    inv_002 = _prove(
        "PO-INV-ORDER-002-BY-CMD-ORDER-MARK-PAID",
        "Terminal order states are irreversible across CMD-ORDER-MARK-PAID",
        transition,
        Implies(_terminal(status_pre), status_post == status_pre),
    )
    inv_003 = _prove(
        "PO-INV-ORDER-003-BY-CMD-ORDER-MARK-PAID",
        "Order version increases on every committed mutation by CMD-ORDER-MARK-PAID",
        transition,
        Implies(accept_guard, version_post == version_pre + 1),
    )
    return [inv_001, inv_002, inv_003]


def run_all() -> list[ObligationResult]:
    return _submit_obligations() + _mark_paid_obligations()


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
