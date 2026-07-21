from __future__ import annotations

import re
from dataclasses import dataclass

# Deliberately conservative: unrecognized output must resolve to "inconclusive", never
# "proved" — a false proof is worse than a missed one (docs/17 Phase 8's own rule for
# unsupported constructs). These substrings are a best guess at probcli's phrasing and
# have not been reconciled against a real run; treat as provisional until they have.
_SUCCESS_PATTERNS = (
    "no invariant violation",
    "no counter-example",
    "no counterexample",
    "no deadlock found",
    "no error found",
)
_FAILURE_PATTERNS = (
    "invariant violation",
    "deadlock found",
    "counter-example",
    "counterexample",
    "error occurred",
    "exception",
)
_STATES_RE = re.compile(r"(\d+)\s+states?\b", re.IGNORECASE)
_VERSION_RE = re.compile(r"ProB\s*(?:2\s*)?(?:Command Line Interface\s*)?v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass(slots=True)
class ProbResult:
    status: str  # "proved" | "failed" | "inconclusive"
    explored_states: int | None
    summary: str
    counterexample: str | None
    tool_version: str | None = None


def parse_prob_output(text: str) -> ProbResult:
    stripped = text.strip()
    lowered = stripped.lower()

    explored_states = None
    states_match = _STATES_RE.search(stripped)
    if states_match:
        explored_states = int(states_match.group(1))

    version_match = _VERSION_RE.search(stripped)
    tool_version = version_match.group(1) if version_match else None

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
