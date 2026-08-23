"""T-029: unit tests for the eval-gate decision helpers. The subprocess/DB
orchestration is exercised by CI itself; here we pin the pure logic that
decides pass/fail."""

from __future__ import annotations

import subprocess
from subprocess import CompletedProcess

import pytest

from evals import _git as git_module
from evals import run_gate as run_gate_module
from evals.run_gate import GateReport, absolute_pass, regression_pass


def test_absolute_pass_only_on_zero_exit() -> None:
    assert absolute_pass(0)
    assert not absolute_pass(1)
    assert not absolute_pass(2)


def test_regression_first_run_has_no_baseline_and_passes() -> None:
    passed, detail = regression_pass(0.91, None)
    assert passed
    assert "no baseline" in detail


def test_regression_missing_current_fails_closed() -> None:
    passed, detail = regression_pass(None, 0.90)
    assert not passed
    assert "no current" in detail


def test_regression_improvement_passes() -> None:
    passed, _ = regression_pass(0.95, 0.90)
    assert passed


def test_regression_small_drop_within_tolerance_passes() -> None:
    # 2-point drop, tolerance 3 points.
    passed, _ = regression_pass(0.88, 0.90, tolerance=0.03)
    assert passed


def test_regression_large_drop_beyond_tolerance_fails() -> None:
    # 5-point drop, tolerance 3 points.
    passed, detail = regression_pass(0.85, 0.90, tolerance=0.03)
    assert not passed
    assert "drop" in detail


def test_regression_drop_exactly_at_tolerance_passes() -> None:
    # Exactly the tolerance is not "beyond" it.
    passed, _ = regression_pass(0.87, 0.90, tolerance=0.03)
    assert passed


def test_gate_report_passes_only_when_all_pass() -> None:
    report = GateReport()
    report.add("a", True, "ok")
    report.add("b", True, "ok")
    assert report.passed
    report.add("c", False, "boom")
    assert not report.passed


def test_gate_report_empty_is_vacuously_passing() -> None:
    assert GateReport().passed


async def test_absolute_gates_run_even_when_llm_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G-1 US-3: no flag skips an absolute gate.

    The deterministic evals - the money guardrail matrix (C-4), cross-tenant
    leakage, retrieval recall - are the ones with a fixed floor and no judge in
    the loop. `--skip-llm` exists so the gate is runnable without a key; it must
    never become a way to run the gate without the checks that do not need one.
    """
    ran: list[str] = []

    def _fake_subprocess(module: str, *args: str) -> int:
        ran.append(module)
        return 0

    monkeypatch.setattr(run_gate_module, "_run_eval_subprocess", _fake_subprocess)

    report = await run_gate_module.run_gate(skip_llm=True)

    assert ran == list(run_gate_module._ABSOLUTE_GATES)
    assert "money_guardrail_eval" in ran, "C-4's matrix is an absolute gate"
    assert report.passed

    # And the skip says which reason, so a deliberate --skip-llm run does not
    # read as a broken environment.
    skipped = [r for r in report.results if "skipped" in r.detail]
    assert skipped, "the judged gates should report as skipped, not silently vanish"
    assert all("--skip-llm" in r.detail for r in skipped)


def test_git_sha_is_empty_when_git_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """B-4: the production image and the `test` stage built from it carry no
    git and no `.git/`, so an eval run there must record an empty SHA rather
    than crash on exec. Found by running the suite inside that image, where
    every eval that writes a run row died with FileNotFoundError."""

    def _no_git(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", "git")

    monkeypatch.setattr(subprocess, "run", _no_git)
    assert git_module.git_sha() == ""


def test_git_sha_is_empty_outside_a_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other unknowable case, already covered by check=False: git exists but
    the working tree is not a repository, so it exits non-zero with no stdout."""

    def _not_a_repo(*args: object, **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args=["git"], returncode=128, stdout="", stderr="fatal: not a git")

    monkeypatch.setattr(subprocess, "run", _not_a_repo)
    assert git_module.git_sha() == ""
