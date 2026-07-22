from __future__ import annotations

import re
from dataclasses import dataclass

# Deliberately conservative: unrecognized output must resolve to "inconclusive", never
# "proved" — a false proof is worse than a missed one (docs/17 Phase 8's own rule for
# unsupported constructs). Reconciled against real probcli 1.15.1-final output (see
# tests/test_probcli_parser.py for the captured excerpts): a clean model check prints
# "No counter example found. ALL states visited." (no hyphen, three words) and a real
# violation prints "*** COUNTER EXAMPLE FOUND ***" plus "invariant_violation" on stdout —
# probcli's "! *** error occurred ***" trailer that a naive reading might expect to key
# off is written to stderr, not stdout, and run-prob.sh's `tee` only captures stdout, so
# cycle.py's _stage_event_b (which prefers the tee'd log file over captured stderr) never
# sees it. The original patterns below (hyphenated/concatenated "counter-example",
# "counterexample", space-joined "invariant violation") never matched real output at all,
# silently falling through to "inconclusive" for both a genuine proof and a genuine
# violation — safe (never a false "proved") but useless. Kept alongside the real-phrasing
# patterns in case other probcli versions/modes use them.
_SUCCESS_PATTERNS = (
    "no counter example found",
    "no invariant violation",
    "no counter-example",
    "no counterexample",
    "no deadlock found",
    "no error found",
)
_FAILURE_PATTERNS = (
    "counter example found",
    "invariant_violation",
    "invariant violation",
    "deadlock found",
    "counter-example",
    "counterexample",
    "error occurred",
    "exception",
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_STATES_RE = re.compile(r"states\s+analysed:\s*(\d+)|(\d+)\s+states?\b", re.IGNORECASE)
_VERSION_RE = re.compile(
    r"VERSION\s+(\d+\.\d+(?:\.\d+)?)|ProB\s*(?:2\s*)?(?:Command Line Interface\s*)?v?(\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ProbResult:
    status: str  # "proved" | "failed" | "inconclusive"
    explored_states: int | None
    summary: str
    counterexample: str | None
    tool_version: str | None = None


def parse_prob_output(text: str) -> ProbResult:
    stripped = _ANSI_RE.sub("", text).strip()
    lowered = stripped.lower()

    explored_states = None
    states_match = _STATES_RE.search(stripped)
    if states_match:
        explored_states = int(states_match.group(1) or states_match.group(2))

    version_match = _VERSION_RE.search(stripped)
    tool_version = (version_match.group(1) or version_match.group(2)) if version_match else None

    last_line = stripped.splitlines()[-1].strip() if stripped else ""

    if any(pattern in lowered for pattern in _SUCCESS_PATTERNS):
        return ProbResult("proved", explored_states, last_line, None, tool_version)
    if any(pattern in lowered for pattern in _FAILURE_PATTERNS):
        return ProbResult("failed", explored_states, last_line, stripped, tool_version)
    return ProbResult(
        "inconclusive",
        explored_states,
        last_line or "probcli output did not match a recognized success or failure pattern.",
        None,
        tool_version,
    )
