#!/usr/bin/env python3
"""A bounded proof for a reservation transition preserving capacity."""
from z3 import And, Int, Not, Solver, sat


def main() -> None:
    capacity = Int("capacity")
    reserved = Int("reserved")
    requested = Int("requested")
    next_reserved = reserved + requested

    invariant = And(capacity >= 0, reserved >= 0, reserved <= capacity)
    guard = And(requested > 0, requested <= capacity - reserved)
    next_invariant = And(next_reserved >= 0, next_reserved <= capacity)

    solver = Solver()
    solver.add(invariant, guard, Not(next_invariant))
    if solver.check() == sat:
        raise SystemExit(f"Invariant violation: {solver.model()}")
    print("PROVED: reserve transition preserves 0 <= reserved <= capacity")


if __name__ == "__main__":
    main()
