"""The report: the artefact the benchmark is actually judged on."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from endstate.evals.report import (
    FLAKE_THRESHOLD,
    flake_rate,
    median,
    percentile,
    render_flake_markdown,
    render_markdown,
    total_cost,
    write_report,
)
from endstate.evals.runner import SuiteResult, TaskResult
from endstate.evals.task import Check, Verdict
from endstate.telemetry.cost import ModelPrice, PriceTable
from endstate.types import Usage

PRICES = PriceTable(
    prices={"fake-1": ModelPrice(input_per_mtok=Decimal(3), output_per_mtok=Decimal(15))}
)


def result(
    task_id: str,
    *,
    passed: bool = True,
    steps: int = 4,
    seconds: float = 1.0,
    category: str = "bug-fix",
    error: str = "",
) -> TaskResult:
    verdict = (
        Verdict.ok()
        if passed
        else Verdict.from_checks([Check(name="the test suite passes", passed=False, detail="red")])
    )
    return TaskResult(
        task_id=task_id,
        category=category,
        verdict=verdict,
        steps=steps,
        usage=Usage(input_tokens=1_000, output_tokens=200),
        wall_clock_s=seconds,
        model="fake-1",
        error=error,
    )


def suite() -> SuiteResult:
    return SuiteResult(
        model="fake-1",
        provider="openai",
        sandbox="docker:python:3.12-slim",
        started_at="2026-08-13T09:00:00Z",
        duration_s=12.0,
        results=[
            result("a-fix", steps=3, seconds=1.0),
            result("b-fix", passed=False, steps=9, seconds=4.0),
            result("c-feat", steps=5, seconds=2.0, category="feature"),
        ],
    )


def test_percentile_is_nearest_rank() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([5.0], 0.95) == 5.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_median_handles_both_parities() -> None:
    assert median([]) == 0.0
    assert median([3.0, 1.0, 2.0]) == 2.0
    assert median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_the_summary_carries_more_than_a_pass_rate() -> None:
    markdown = render_markdown(suite(), PRICES)
    assert "| openai | fake-1 | 67% |" in markdown
    assert "3,000" in markdown  # input tokens across the suite
    assert "$0.0060" in markdown  # USD per task, priced
    assert "4.0s" in markdown  # p95 latency


def test_categories_are_broken_out() -> None:
    markdown = render_markdown(suite(), PRICES)
    assert "| bug-fix | 1 | 2 | 50% |" in markdown
    assert "| feature | 1 | 1 | 100% |" in markdown


def test_failures_list_the_individual_checks() -> None:
    markdown = render_markdown(suite(), PRICES)
    assert "### `b-fix`" in markdown
    assert "[FAIL] the test suite passes: red" in markdown


def test_an_unpriced_model_reports_nothing_rather_than_zero() -> None:
    """D4: a wrong cost number is worse than a missing one."""
    markdown = render_markdown(suite())
    assert "| — |" in markdown
    assert "Cost is unreported" in markdown
    assert "$0.00" not in markdown


def test_total_cost_is_none_when_any_model_is_unpriced() -> None:
    assert total_cost(suite(), PriceTable()) is None
    assert total_cost(suite(), PRICES) == Decimal("0.018")


def test_harness_errors_are_labelled_as_errors() -> None:
    errored = SuiteResult(results=[result("x", passed=False, error="no daemon")])
    markdown = render_markdown(errored)
    assert "| error |" in markdown
    assert "Harness error: no daemon" in markdown


def test_a_timeout_says_so() -> None:
    timed_out = result("slow", passed=False)
    timed_out.timed_out = True
    markdown = render_markdown(SuiteResult(results=[timed_out]))
    assert "fail (timeout)" in markdown


def test_an_empty_suite_renders(tmp_path: Path) -> None:
    assert "Eval report" in render_markdown(SuiteResult())


def test_write_report_emits_markdown_and_json(tmp_path: Path) -> None:
    markdown_path, json_path = write_report(suite(), tmp_path / "benchmarks", PRICES)

    assert markdown_path.parent == tmp_path / "benchmarks"
    assert markdown_path.name.endswith("-fake-1.md")
    assert "Eval report" in markdown_path.read_text(encoding="utf-8")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert [r["task_id"] for r in payload["results"]] == ["a-fix", "b-fix", "c-feat"]
    assert payload["model"] == "fake-1"


def test_the_filename_slug_survives_an_awkward_model_name(tmp_path: Path) -> None:
    awkward = SuiteResult(model="Qwen/Qwen2.5-Coder-32B-Instruct")
    markdown_path, _ = write_report(awkward, tmp_path / "b")
    assert "qwen-qwen2-5-coder-32b-instruct" in markdown_path.name

    unnamed, _ = write_report(SuiteResult(), tmp_path / "c")
    assert unnamed.name.endswith("-unknown.md")


# --- determinism across repeated runs -------------------------------------


def repeated(*runs: list[bool]) -> list[SuiteResult]:
    """One SuiteResult per run, from pass/fail vectors over the same task ids."""
    return [
        SuiteResult(
            model="fake-1",
            results=[result(f"task-{i}", passed=outcome) for i, outcome in enumerate(outcomes)],
        )
        for outcomes in runs
    ]


def test_a_stable_suite_has_no_flake() -> None:
    suites = repeated([True, False, True], [True, False, True], [True, False, True])
    assert flake_rate(suites) == 0.0
    assert len({s.verdict_vector for s in suites}) == 1


def test_one_task_disagreeing_with_itself_is_the_flake_rate() -> None:
    """One of three tasks flipped, so a third of the suite is untrustworthy."""
    suites = repeated([True, True, True], [True, False, True])
    assert flake_rate(suites) == pytest.approx(1 / 3)


def test_a_single_run_reports_no_rate() -> None:
    """Nothing has been compared yet, and 0% would imply otherwise."""
    assert flake_rate(repeated([True, False])) == 0.0
    assert flake_rate([]) == 0.0


def test_the_flake_report_names_the_unstable_tasks() -> None:
    markdown = render_flake_markdown(repeated([True, True], [True, False]))
    assert "Flake rate:** 50.0% (OVER the 5% threshold)" in markdown
    assert "did not agree with themselves" in markdown
    assert "| `task-1` | pass fail |" in markdown
    assert "Identical verdict vectors:** no" in markdown


def test_the_flake_report_says_so_when_nothing_moved() -> None:
    markdown = render_flake_markdown(repeated([True, False], [True, False]))
    assert "Every task returned the same verdict in every run." in markdown
    assert "within the 5% threshold" in markdown
    assert "Identical verdict vectors:** yes" in markdown


def test_the_threshold_is_the_one_the_plan_asks_for() -> None:
    assert FLAKE_THRESHOLD == 0.05
