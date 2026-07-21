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
