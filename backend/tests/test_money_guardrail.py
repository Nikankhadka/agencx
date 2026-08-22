"""C-4: the money guardrail matrix, with teeth.

RELEASE CRITERION: never deleted, never skipped, no flag turns it off. A single
invented figure reaching a customer is the product's stop-the-panel failure
(PRD section 7), and C-1/C-2 changed both the guardrail's allowed set and its
coverage - this is what keeps those changes honest.

The cases themselves live in ``evals/money_guardrail_eval.py`` so that pytest
and ``make eval`` grade the same matrix rather than two that drift. This file
parameterizes over them, and adds the part an eval runner cannot do: breaking
the guardrail on purpose to prove the matrix notices.
"""

from __future__ import annotations

import pytest

from app.pricing import validation_gate
from evals import money_guardrail_eval
from evals.money_guardrail_eval import CASES, GuardrailCase, evaluate, run


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_guardrail_matrix(case: GuardrailCase) -> None:
    ok, violations = evaluate(case)
    expected = "pass" if case.should_pass else "fail"
    assert ok, f"expected {case.id} to {expected} - {case.why}; got violations={violations}"


def test_the_matrix_covers_both_verdicts() -> None:
    """A matrix that only asserts passes proves the guardrail is off; one that
    only asserts failures proves it refuses everything."""
    assert sum(1 for case in CASES if case.should_pass) >= 5
    assert sum(1 for case in CASES if not case.should_pass) >= 10


def test_case_ids_are_unique() -> None:
    assert len({case.id for case in CASES}) == len(CASES)


# --- teeth: a weakened guardrail must fail the matrix ------------------------


def test_a_guardrail_that_allows_everything_fails_the_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The break-then-restore check. Without it a matrix can quietly rot into
    asserting nothing - every case still 'passes' because the thing under test
    stopped objecting to anything."""
    # Patched where it is used: the eval module bound the name at import, so
    # replacing it on validation_gate would leave the old reference in place.
    monkeypatch.setattr(money_guardrail_eval, "validate", lambda *args, **kwargs: [])
    passed, total, failures = run()
    assert failures, "a guardrail that allows every figure must fail this matrix"
    assert passed < total


def test_a_guardrail_that_forgets_owner_material_fails_the_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-1's specific regression: dropping the material source would send the
    guardrail back to engine-only, refusing every honest verbatim answer."""
    original = validation_gate.allowed_cents
    monkeypatch.setattr(
        validation_gate,
        "allowed_cents",
        lambda engine_quote, provenance, material=(): original(engine_quote, provenance),
    )
    _passed, _total, failures = run()
    assert any("verbatim" in failure for failure in failures)


def test_a_guardrail_that_stops_checking_hedges_fails_the_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-1's other half: hedged figures pass the allowed-set check by
    definition, so only the hedge rule catches them."""
    monkeypatch.setattr(validation_gate, "is_hedged", lambda text, figure: False)
    _passed, _total, failures = run()
    assert any("hedged" in failure for failure in failures)
