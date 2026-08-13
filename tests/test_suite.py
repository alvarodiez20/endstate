"""The shipped task suite, graded against itself.

This is the M2 analogue of the mutation check, and it is the test that decides
whether the other eleven files in `tasks/` mean anything. For every task:

- the graders must **fail** on the untouched fixture, and
- the graders must **pass** once the reference solution is overlaid.

A grader that passes on the unsolved fixture is measuring nothing. A grader that
fails on a correct solution is worse — it makes every model look bad and the
suite look rigorous. Both are easy to write by accident, and neither is visible
by reading the task definition.

No model is involved. The reference solution stands in for a perfect agent, and
the untouched fixture stands in for one that did nothing, which brackets every
real run between two known answers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from endstate.evals.graders import grader_for
from endstate.evals.runner import EvalRunner
from endstate.evals.sandbox import LocalSandbox, stage_tree
from endstate.evals.task import Task, discover_tasks
from endstate.providers.fake import FakeProvider
from endstate.types import Message, Response, StopReason, ToolCall, Usage

SUITE = Path(__file__).resolve().parent.parent / "tasks"
TASKS = discover_tasks(SUITE)
TASK_IDS = [t.id for t in TASKS]


def grade(task: Task, tmp_path: Path, *, solved: bool) -> tuple[bool, str]:
    """Run a task's graders against its fixture, optionally solved first."""
    with LocalSandbox(task.fixture, tmp_path / "box") as sandbox:
        if solved:
            assert task.solution is not None
            stage_tree(task.solution, sandbox.workdir)
        sandbox.seal()
        if task.holdout is not None:
            sandbox.stage(task.holdout)
        verdict = grader_for(task.graders)(sandbox)
    detail = "\n".join(str(c) for c in verdict.checks)
    return verdict.passed, detail


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_the_reference_solution_passes(task: Task, tmp_path: Path) -> None:
    passed, detail = grade(task, tmp_path, solved=True)
    assert passed, f"{task.id} rejects its own reference solution:\n{detail}"


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_the_untouched_fixture_fails(task: Task, tmp_path: Path) -> None:
    passed, detail = grade(task, tmp_path, solved=False)
    assert not passed, f"{task.id} passes without being solved:\n{detail}"


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_every_task_ships_a_solution_and_a_holdout(task: Task) -> None:
    """Both are what make the two tests above possible."""
    assert task.solution is not None, f"{task.id} has no solution/ to check the graders against"
    assert task.holdout is not None, f"{task.id} has no holdout/, so special-casing goes unseen"


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_the_holdout_is_not_shipped_to_the_agent(task: Task, tmp_path: Path) -> None:
    """The sandbox the agent works in must not contain the held-out tests."""
    assert task.holdout is not None
    holdout_files = {p.name for p in task.holdout.rglob("*") if p.is_file()}
    with LocalSandbox(task.fixture, tmp_path / "box") as sandbox:
        shipped = {Path(p).name for p in sandbox.end_state_files()}
    assert not (holdout_files & shipped), f"{task.id} ships its own held-out tests"


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_the_fixture_carries_no_history(task: Task, tmp_path: Path) -> None:
    """`git log` must not be a cheaper path to the answer than solving the task."""
    with LocalSandbox(task.fixture, tmp_path / "box") as sandbox:
        assert not sandbox.exists(".git")


def test_the_suite_covers_the_categories_m2_promised() -> None:
    counts = {c: sum(1 for t in TASKS if t.category == c) for t in TASKS for c in [t.category]}
    assert counts.get("bug-fix", 0) >= 5
    assert counts.get("feature", 0) >= 4
    assert counts.get("refactor", 0) >= 3


def test_task_ids_are_unique_and_sorted() -> None:
    assert sorted(set(TASK_IDS)) == TASK_IDS


def test_every_task_asserts_more_than_a_green_test_run() -> None:
    """A task graded only by `pytest -q` has swapped one exploit for another.

    Editing the tests satisfies "the suite is green" completely, so every task
    has to make at least one assertion about the file tree as well.
    """
    for task in TASKS:
        names = {spec.name.rpartition(":")[2] for spec in task.graders}
        assert names - {"command_succeeds"}, f"{task.id} only runs a command"
        assert "files_unchanged" in names, f"{task.id} does not pin its test files"


# --- end to end -----------------------------------------------------------


def test_a_scripted_agent_solves_a_real_task(tmp_path: Path) -> None:
    """The whole pipeline on a shipped task, with a model that gets it right.

    Everything above grades a staged directory. This drives the runner: sandbox
    setup, tools wired into it, seal, holdout, graders — the path a real run
    takes, minus the only part that needs an API key.
    """
    task = next(t for t in TASKS if t.id == "fix-chunk-off-by-one")
    assert task.solution is not None
    fixed = (task.solution / "chunker" / "chunk.py").read_text(encoding="utf-8")

    script = [
        Response(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="bash",
                        arguments={"command": "python -m unittest discover -s tests -t . -q"},
                    )
                ],
            ),
            usage=Usage(input_tokens=800, output_tokens=40),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        ),
        Response(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="t2",
                        name="write",
                        arguments={"path": "chunker/chunk.py", "content": fixed},
                    )
                ],
            ),
            usage=Usage(input_tokens=900, output_tokens=120),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        ),
        Response(
            message=Message(role="assistant", content="fixed the off-by-one"),
            usage=Usage(input_tokens=950, output_tokens=12),
            stop_reason=StopReason.END_TURN,
            model="fake-1",
        ),
    ]

    provider = FakeProvider(script)
    runner = EvalRunner(
        provider_factory=lambda t: provider,
        sandbox_factory=lambda t: LocalSandbox(t.fixture, tmp_path / "box"),
    )
    result = runner.run_task(task)

    assert result.passed, [str(c) for c in result.verdict.checks]
    assert result.steps == 3
    assert result.usage.input_tokens == 2650

    # The first thing the agent did was run the tests, inside the sandbox, and
    # they were red. That is the signal a real model would be working from.
    first_run = provider.calls[1][-1].tool_results[0].content
    assert "FAILED" in first_run or "exit_code: 1" in first_run


def test_the_same_task_fails_for_an_agent_that_does_nothing(tmp_path: Path) -> None:
    task = next(t for t in TASKS if t.id == "fix-chunk-off-by-one")
    runner = EvalRunner(
        provider_factory=lambda t: FakeProvider(
            [Response(message=Message(role="assistant", content="looks fine to me"))]
        ),
        sandbox_factory=lambda t: LocalSandbox(t.fixture, tmp_path / "box"),
    )
    result = runner.run_task(task)
    assert not result.passed
    assert "the test suite passes" in result.verdict.reason
