#!/usr/bin/env python3
"""Prove totality and mutual exclusivity of command outcomes.

Install optional dependency:
    pip install 'z3-solver>=4.13,<5'
"""
from __future__ import annotations

from itertools import combinations

from z3 import And, Bool, Not, Or, Solver, sat


def assert_unsat(name: str, formula) -> None:
    solver = Solver()
    solver.add(formula)
    if solver.check() == sat:
        raise SystemExit(f"FAILED: {name}; counterexample={solver.model()}")
    print(f"PROVED: {name}")


def main() -> None:
    exists = Bool("exists")
    owner = Bool("owner")
    draft = Bool("draft")
    version_ok = Bool("version_ok")

    outcomes = {
        "accepted": And(exists, owner, draft, version_ok),
        "not_found": Not(exists),
        "forbidden": And(exists, Not(owner)),
        "wrong_state": And(exists, owner, Not(draft)),
        "stale_version": And(exists, owner, draft, Not(version_ok)),
    }

    # A counterexample to totality would satisfy none of the outcomes.
    assert_unsat("outcomes are total", Not(Or(*outcomes.values())))

    # A counterexample to determinism would satisfy two outcomes simultaneously.
    for (left_name, left), (right_name, right) in combinations(outcomes.items(), 2):
        assert_unsat(f"{left_name} and {right_name} are mutually exclusive", And(left, right))


if __name__ == "__main__":
    main()
