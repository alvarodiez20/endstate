"""The report.

Pass rate alone hides too much. A model that passes 80% of tasks in 6 steps for
$0.02 and a model that passes 80% in 34 steps for $1.40 are not the same
product, and only one of them is deployable at volume — so every summary here
carries steps, tokens, cost and latency beside the rate.

Two smaller decisions worth naming. Cost renders as `—` rather than `0.00` when
the model has no price entry, because a wrong number in a published benchmark is
worse than a missing one (**D4**). And errored tasks are counted separately from
failed ones: "Docker was not running" and "the model could not do it" must never
sum into the same column.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

from endstate.evals.runner import SuiteResult, TaskResult
from endstate.telemetry.cost import PriceTable


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile.

    Not `statistics.quantiles`, which interpolates and needs at least two data
    points. A twenty-task suite is a small sample and an interpolated p95 over
    twenty numbers implies a precision that is not there.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil(fraction * len(ordered))))
    return ordered[rank - 1]


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def total_cost(suite: SuiteResult, prices: PriceTable) -> Decimal | None:
    """Suite cost, or None if any model in it has no price."""
    total = Decimal(0)
    for result in suite.results:
        price = prices.get(result.model)
        if price is None:
            return None
        total += price.cost(result.usage)
    return total


def render_markdown(suite: SuiteResult, prices: PriceTable | None = None) -> str:
    """The committed artefact: one suite run, as a markdown page."""
    prices = prices or PriceTable()
    results = suite.results
    cost = total_cost(suite, prices)
    per_task = (cost / len(results)) if cost is not None and results else None

    lines = [
        f"# Eval report — {suite.model or 'unknown model'}",
        "",
        f"- **Run at:** {suite.started_at or 'unknown'}",
        f"- **Provider:** {suite.provider or 'unknown'}",
        f"- **Sandbox:** {suite.sandbox or 'unknown'}",
        f"- **Tasks:** {len(results)}",
        f"- **Wall clock:** {suite.duration_s:.1f}s",
        "",
        "## Summary",
        "",
        "| provider | model | pass rate | median steps | input tok | output tok |"
        " USD/task | p95 latency | compactions/task |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        _summary_row(suite, per_task),
        "",
        "## By category",
        "",
        "| category | passed | tasks | pass rate |",
        "| --- | --- | --- | --- |",
    ]

    for category in sorted({r.category for r in results}):
        rows = [r for r in results if r.category == category]
        passed = sum(1 for r in rows if r.passed)
        lines.append(f"| {category} | {passed} | {len(rows)} | {passed / len(rows):.0%} |")

    lines += [
        "",
        "## Tasks",
        "",
        "| task | category | verdict | steps | tokens | seconds | denied | compactions |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| `{result.task_id}` | {result.category} | {_verdict_cell(result)} | "
            f"{result.steps} | {result.usage.total_tokens:,} | {result.wall_clock_s:.1f} | "
            f"{result.denied_calls} | {result.compaction_events} |"
        )

    failures = [r for r in results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for result in failures:
            lines.append(f"### `{result.task_id}`")
            lines.append("")
            if result.error:
                lines += [f"Harness error: {result.error}", ""]
            for check in result.verdict.checks:
                lines.append(f"- {check}")
            if not result.verdict.checks and result.verdict.reason:
                lines.append(f"- {result.verdict.reason}")
            lines.append("")

    if cost is None:
        lines += [
            "",
            "Cost is unreported: no price entry for every model in this run. Pass `--prices`"
            " with a table covering them rather than reading a zero as free.",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _summary_row(suite: SuiteResult, per_task: Decimal | None) -> str:
    results = suite.results
    steps = median([float(r.steps) for r in results])
    latency = percentile([r.wall_clock_s for r in results], 0.95)
    compactions = sum(r.compaction_events for r in results) / len(results) if results else 0.0
    inputs = sum(r.usage.input_tokens for r in results)
    outputs = sum(r.usage.output_tokens for r in results)
    cost_cell = f"${per_task:.4f}" if per_task is not None else "—"
    return (
        f"| {suite.provider or '—'} | {suite.model or '—'} | {suite.pass_rate:.0%} | "
        f"{steps:.0f} | {inputs:,} | {outputs:,} | {cost_cell} | {latency:.1f}s | "
        f"{compactions:.1f} |"
    )


def _verdict_cell(result: TaskResult) -> str:
    if result.error:
        return "error"
    if result.timed_out:
        return "fail (timeout)"
    return "pass" if result.passed else f"fail — {result.verdict.reason}"


FLAKE_THRESHOLD = 0.05
"""The rate above which a suite cannot support a claim.

From the engineering plan's M2 metric. Determinism is aspirational rather than
achievable — providers do not offer bit-identical output even at temperature 0 —
so the criterion is a low rate, not zero.
"""


def flake_rate(suites: Sequence[SuiteResult]) -> float:
    """Fraction of tasks that did not return the same verdict in every run.

    The number the whole determinism claim reduces to, and it is only meaningful
    over identical inputs: same suite, same model, same seed. One run per task
    cannot tell capability from luck, and providers do not offer bit-identical
    output even at temperature 0 — so what is achievable is a low rate, not zero,
    and every result below the threshold is still a distribution rather than a
    fact.

    Returns 0.0 for fewer than two runs: nothing has been compared yet, and
    reporting a rate for a single run would imply otherwise.
    """
    if len(suites) < 2:
        return 0.0
    outcomes = _outcomes(suites)
    if not outcomes:
        return 0.0
    flaky = sum(1 for results in outcomes.values() if len(set(results)) > 1)
    return flaky / len(outcomes)


def _outcomes(suites: Sequence[SuiteResult]) -> dict[str, list[bool]]:
    """Pass/fail per task per run, keyed by task id."""
    outcomes: dict[str, list[bool]] = {}
    for suite in suites:
        for result in suite.results:
            outcomes.setdefault(result.task_id, []).append(result.passed)
    return outcomes


def determinism_established(suites: Sequence[SuiteResult]) -> tuple[bool, str]:
    """Whether these runs can support a determinism claim at all.

    A low flake rate is necessary and nowhere near sufficient, because the most
    reassuring number this module can produce is also what a completely broken
    run produces. A suite where the container never started fails every task,
    identically, every time — perfectly reproducible and evidence of nothing.

    So the rate is reported *under* this: if any task hit a harness error, or
    there is only one run, the answer is "not established" no matter how stable
    the verdicts looked.
    """
    if len(suites) < 2:
        return False, "fewer than two runs — nothing has been compared"
    if not _outcomes(suites):
        return False, "no tasks ran"
    errored = {r.task_id for s in suites for r in s.results if r.error}
    if errored:
        listed = ", ".join(sorted(errored)[:5])
        return False, f"{len(errored)} task(s) hit a harness error, not a verdict: {listed}"
    return True, ""


def render_flake_markdown(suites: Sequence[SuiteResult], threshold: float = FLAKE_THRESHOLD) -> str:
    """Report determinism across repeated runs of the same suite."""
    rate = flake_rate(suites)
    outcomes = _outcomes(suites)
    vectors = {s.verdict_vector for s in suites}
    established, why_not = determinism_established(suites)

    model = next((s.model for s in suites if s.model), "unknown model")
    lines = [
        f"# Flake report — {model}",
        "",
        f"- **Runs:** {len(suites)}",
        f"- **Tasks:** {len(outcomes)}",
        f"- **Flake rate:** {rate:.1%} ({'within' if rate <= threshold else 'OVER'}"
        f" the {threshold:.0%} threshold)",
        f"- **Identical verdict vectors:** {'yes' if len(vectors) == 1 else 'no'}",
        "",
    ]

    if not established:
        lines += [
            f'!!! danger "Determinism not established — {why_not}"',
            "",
            "    The rate above is real and it certifies nothing. A run where the sandbox never"
            " started fails every task identically every time, which is perfectly reproducible and"
            " evidence of nothing at all. Fix the errors and run it again before quoting a number.",
            "",
        ]

    unstable = {t: r for t, r in outcomes.items() if len(set(r)) > 1}
    if unstable:
        lines += [
            "## Tasks that did not agree with themselves",
            "",
            "| task | runs |",
            "| --- | --- |",
        ]
        for task_id, results in sorted(unstable.items()):
            lines.append(f"| `{task_id}` | {' '.join('pass' if r else 'fail' for r in results)} |")
        lines += [
            "",
            "A task in this table is not evidence about the model. It is evidence that the number"
            " next to it in any benchmark table is a coin flip, and it has to be fixed or dropped"
            " before the suite can support a claim.",
            "",
        ]
    else:
        lines += ["Every task returned the same verdict in every run.", ""]

    lines += [
        "## Outcomes",
        "",
        "| task | " + " | ".join(f"run {i + 1}" for i in range(len(suites))) + " |",
        "| --- |" + " --- |" * len(suites),
    ]
    for task_id, results in sorted(outcomes.items()):
        cells = " | ".join("pass" if r else "fail" for r in results)
        lines.append(f"| `{task_id}` | {cells} |")

    return "\n".join(lines).rstrip() + "\n"


def write_report(
    suite: SuiteResult, out_dir: Path, prices: PriceTable | None = None
) -> tuple[Path, Path]:
    """Write the markdown report and the machine-readable results beside it.

    Both, not either. The markdown is what a person reads in a pull request; the
    JSON is what the next run diffs against to answer "did anything regress?".
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"results-{date.today().isoformat()}-{_slug(suite.model)}"

    markdown_path = out_dir / f"{stem}.md"
    markdown_path.write_text(render_markdown(suite, prices), encoding="utf-8")

    json_path = out_dir / f"{stem}.json"
    json_path.write_text(
        json.dumps(json.loads(suite.model_dump_json()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return markdown_path, json_path


def _slug(text: str) -> str:
    cleaned = "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "unknown"


__all__ = [
    "FLAKE_THRESHOLD",
    "determinism_established",
    "flake_rate",
    "median",
    "percentile",
    "render_flake_markdown",
    "render_markdown",
    "total_cost",
    "write_report",
]
