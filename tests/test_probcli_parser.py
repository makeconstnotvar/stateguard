from __future__ import annotations

from stateguard.probcli_parser import parse_prob_output


def test_recognized_success_phrase_yields_proved() -> None:
    result = parse_prob_output(
        "ProB Command Line Interface 1.12.1\n"
        "Model checking OrderWorkflow...\n"
        "1234 states processed.\n"
        "No invariant violation found.\n"
    )
    assert result.status == "proved"
    assert result.explored_states == 1234
    assert result.tool_version == "1.12.1"
    assert result.counterexample is None


def test_recognized_failure_phrase_yields_failed_with_counterexample() -> None:
    text = "Model checking OrderWorkflow...\nInvariant violation found!\nTrace: submit; submit\n"
    result = parse_prob_output(text)
    assert result.status == "failed"
    assert result.counterexample == text.strip()


def test_unrecognized_output_is_inconclusive_not_proved() -> None:
    result = parse_prob_output("Something unexpected happened that this parser has never seen.")
    assert result.status == "inconclusive"
    assert result.counterexample is None


def test_empty_output_is_inconclusive() -> None:
    result = parse_prob_output("")
    assert result.status == "inconclusive"


# Captured verbatim (ANSI colour codes included) from a real run of
# `event-b/run-prob.sh event-b/OrderWorkflow.mch` against probcli 1.15.1-final on
# 2026-07-22 — this is the actual stdout text cycle.py's _stage_event_b feeds to
# parse_prob_output (run-prob.sh's `tee` only captures probcli's stdout, not stderr).
_REAL_ORDERWORKFLOW_SUCCESS = (
    "ProB Command Line Interface\n"
    "  VERSION 1.15.1-final (d86821c2f59eef7a899ee35d6e3d30bafa2fa347)\n"
    "  Sun Dec 21 07:57:00 2025 +0100\n"
    "  Prolog (sicstus): SICStus 4.8.0 (arm64-darwin-20.1.0): Sun Dec  4 14:17:07 CET 2022\n"
    "  COMPILE TIME FLAGS: [prob_release]\n"
    "4c8243112e8ae53810738093eef70bcab2f17e7bf3d739a89921b1875cda9fa0  event-b/OrderWorkflow.mch\n"
    "\n"
    "ALL OPERATIONS COVERED\n"
    "% Model checking finished, all open states visited\n"
    "Model checking time: 21 ms (22 ms walltime)\n"
    "States analysed: 81\n"
    "Transitions fired: 199\n"
    "\x1b[32mNo counter example found. ALL states visited.\x1b[0m\n"
)

# Captured the same way against a scratch copy of OrderWorkflow.mch whose INVARIANT was
# deliberately broken (payment_confirmed flipped to payment_rejected in the paid-implies-
# confirmed conjunct) — the negative control proving the parser isn't vacuously trusting
# output it doesn't understand. Real probcli genuinely found the induced violation.
_REAL_ORDERWORKFLOW_VIOLATION = (
    "ProB Command Line Interface\n"
    "  VERSION 1.15.1-final (d86821c2f59eef7a899ee35d6e3d30bafa2fa347)\n"
    "  Sun Dec 21 07:57:00 2025 +0100\n"
    "  Prolog (sicstus): SICStus 4.8.0 (arm64-darwin-20.1.0): Sun Dec  4 14:17:07 CET 2022\n"
    "  COMPILE TIME FLAGS: [prob_release]\n"
    "5d3d01c60b06326b36087a0066697af1823ee12da34ef4af143f0eb672eb85dc  "
    "/tmp/sg_scratch/OrderWorkflow_broken.mch\n"
    "\n"
    "ALL OPERATIONS COVERED\n"
    "\n"
    "Model checking time: 10 ms (10 ms walltime)\n"
    "States analysed: 26\n"
    "Transitions fired: 84\n"
    "\x1b[31m*** COUNTER EXAMPLE FOUND ***\x1b[0m\n"
    "\n"
    "invariant_violation\n"
    "*** TRACE (length=7):\n"
    " 1: INITIALISATION(payment_of={},payment_order={(p1|->o1),(p2|->o2)},"
    "payment_status={(p1|->payment_pending),(p2|->payment_pending)},"
    "status={(o1|->draft),(o2|->draft)},version={(o1|->1),(o2|->1)})\n"
    " 2: submit(o1,1)\n"
    " 3: confirm_payment(p2)\n"
    " 4: cancel(o1,2)\n"
    " 5: confirm_payment(p1)\n"
    " 6: submit(o2,1)\n"
    " 7: mark_paid(o2,p2,2)\n"
    "*** Invariant 6 (Line:22 Col:4) is false (in state with id 49):\n"
    " !o.(status(o) = paid => o : dom(payment_of) & payment_status(payment_of(o)) = "
    "payment_rejected & payment_order(payment_of(o)) = o)\n"
)


def test_real_probcli_success_output_yields_proved() -> None:
    result = parse_prob_output(_REAL_ORDERWORKFLOW_SUCCESS)
    assert result.status == "proved"
    assert result.explored_states == 81
    assert result.tool_version == "1.15.1"
    assert result.counterexample is None
    assert "no counter example found" in result.summary.lower()


def test_real_probcli_violation_output_yields_failed_negative_control() -> None:
    result = parse_prob_output(_REAL_ORDERWORKFLOW_VIOLATION)
    assert result.status == "failed"
    assert result.explored_states == 26
    assert result.tool_version == "1.15.1"
    assert result.counterexample is not None
    assert "invariant_violation" in result.counterexample
    assert "mark_paid(o2,p2,2)" in result.counterexample
