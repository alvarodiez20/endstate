"""The eval runner, and the determinism claim it has to support."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from endstate.evals.report import flake_rate, render_flake_markdown
from endstate.evals.runner import EvalRunner, SuiteResult, TaskResult
from endstate.evals.sandbox import LocalSandbox, Sandbox, SandboxError
from endstate.evals.task import Task, TaskError, Verdict, discover_tasks, load_task
from endstate.providers.fake import FakeProvider
from endstate.types import Message, Response, StopReason, ToolCall, Usage

WRITE_THE_FIX = [
    Response(
        message=Message(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="write",
                    arguments={"path": "pkg/mod.py", "content": "VALUE = 2\n"},
                )
            ],
        ),
        usage=Usage(input_tokens=100, output_tokens=20),
        stop_reason=StopReason.TOOL_USE,
        model="fake-1",
    ),
    Response(
        message=Message(role="assistant", content="fixed it"),
        usage=Usage(input_tokens=120, output_tokens=8),
        stop_reason=StopReason.END_TURN,
        model="fake-1",
    ),
]


def make_task(root: Path, *, graders: list[dict], task_id: str = "demo") -> Task:
    directory = root / task_id
    (directory / "fixture" / "pkg").mkdir(parents=True)
    (directory / "fixture" / "pkg" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (directory / "prompt.md").write_text("Set VALUE to 2.\n", encoding="utf-8")
    (directory / "task.json").write_text(
        json.dumps({"id": task_id, "category": "bug-fix", "graders": graders}),
        encoding="utf-8",
    )
    return load_task(directory)


def value_is_two(sandbox: Sandbox) -> Verdict:
    from endstate.evals.task import Check

    return Verdict.from_checks(
        [Check(name="VALUE == 2", passed=sandbox.read_text("pkg/mod.py") == "VALUE = 2\n")]
    )


VALUE_GRADER = [{"name": f"{__name__}:value_is_two"}]


def runner_for(tmp_path: Path, responses: list[Response], **kwargs: object) -> EvalRunner:
    return EvalRunner(
        provider_factory=lambda task: FakeProvider(list(responses)),
        sandbox_factory=lambda task: LocalSandbox(task.fixture, tmp_path / f"box-{task.id}"),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_passing_task(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    result = runner_for(tmp_path, WRITE_THE_FIX).run_task(task)

    assert result.passed
    assert result.steps == 2
    assert result.usage.input_tokens == 220
    assert result.model == "fake-1"
    assert result.tree_hash


def test_a_failing_task(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    result = runner_for(tmp_path, [Response(message=Message(role="assistant", content="nah"))])
    outcome = result.run_task(task)
    assert not outcome.passed
    assert outcome.verdict.reason == "VALUE == 2"


def test_the_agent_never_sees_the_holdout(tmp_path: Path) -> None:
    """The held-out tests are staged in after the agent has stopped."""
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    assert task.root is not None
    holdout = task.root / "holdout"
    holdout.mkdir()
    (holdout / "extra.py").write_text("# held out\n", encoding="utf-8")
    task = load_task(task.root)

    listing = Response(
        message=Message(
            role="assistant",
            tool_calls=[ToolCall(id="g", name="glob", arguments={"pattern": "**/*"})],
        ),
        stop_reason=StopReason.TOOL_USE,
        model="fake-1",
    )
    provider = FakeProvider([listing, *WRITE_THE_FIX])
    runner = EvalRunner(
        provider_factory=lambda task: provider,
        sandbox_factory=lambda task: LocalSandbox(task.fixture, tmp_path / "box"),
    )
    runner.run_task(task)

    seen = "\n".join(
        result.content
        for messages in provider.calls
        for message in messages
        for result in message.tool_results
    )
    assert "extra.py" not in seen


def test_a_broken_grader_does_not_sink_the_suite(tmp_path: Path) -> None:
    """A grader that raises is reported as a failure, not propagated."""
    task = make_task(tmp_path / "tasks", graders=[{"name": "endstate.evals.graders:paths_exist"}])
    result = runner_for(tmp_path, WRITE_THE_FIX).run_task(task)
    # paths_exist without `paths` raises TypeError inside the grader, which the
    # runner reports rather than letting it sink the suite.
    assert not result.passed
    assert "TypeError" in result.verdict.reason


def test_a_broken_sandbox_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    """ "Docker is not running" must never render as "the model cannot code"."""

    def explode(task: Task) -> Sandbox:
        raise SandboxError("no daemon")

    runner = EvalRunner(provider_factory=lambda task: FakeProvider([]), sandbox_factory=explode)
    result = runner.run_task(make_task(tmp_path / "tasks", graders=VALUE_GRADER))
    assert result.error == "sandbox error: no daemon"
    assert not result.passed


def test_a_provider_that_blows_up_loses_one_task_not_the_suite(tmp_path: Path) -> None:
    """Nineteen good results must survive a 503 on task seven."""

    class Exploding:
        model = "fake-1"

        def complete(self, messages: object, tools: object = None) -> object:
            raise RuntimeError("503 from the provider")

    runner = EvalRunner(
        provider_factory=lambda task: Exploding(),
        sandbox_factory=lambda task: LocalSandbox(task.fixture, tmp_path / f"box-{task.id}"),
    )
    suite = runner.run_suite(two_tasks(tmp_path))
    assert len(suite.errored) == 2
    assert all("RuntimeError: 503" in r.error for r in suite.results)


def test_a_task_that_runs_out_of_time_is_still_graded(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    task.timeout_s = 0.0
    result = runner_for(tmp_path, WRITE_THE_FIX).run_task(task)
    assert result.timed_out
    assert not result.passed
    assert result.tree_hash, "a timed-out run still has an end state"


def test_max_steps_comes_from_the_task(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    task.max_steps = 1
    result = runner_for(tmp_path, WRITE_THE_FIX).run_task(task)
    assert result.steps == 1
    assert result.stop_reason is StopReason.MAX_STEPS


def test_bash_runs_inside_the_sandbox(tmp_path: Path) -> None:
    """Not on the host: the container is the boundary, so the shell must cross it."""
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    responses = [
        Response(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(id="b", name="bash", arguments={"command": "pwd && cat pkg/mod.py"})
                ],
            ),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        ),
        *WRITE_THE_FIX,
    ]
    provider = FakeProvider(responses)
    runner = EvalRunner(
        provider_factory=lambda task: provider,
        sandbox_factory=lambda task: LocalSandbox(task.fixture, tmp_path / "box"),
    )
    runner.run_task(task)

    output = "\n".join(r.content for ms in provider.calls for m in ms for r in m.tool_results)
    assert "VALUE = 1" in output
    assert str(tmp_path / "box") in output


# --- suites ---------------------------------------------------------------


def two_tasks(tmp_path: Path) -> list[Task]:
    root = tmp_path / "tasks"
    return [
        make_task(root, graders=VALUE_GRADER, task_id="a-task"),
        make_task(root, graders=VALUE_GRADER, task_id="b-task"),
    ]


def test_the_verdict_vector_is_identical_across_runs(tmp_path: Path) -> None:
    """The M2 acceptance criterion, stated as an assertion."""
    tasks = two_tasks(tmp_path)
    first = runner_for(tmp_path / "one", WRITE_THE_FIX).run_suite(tasks)
    second = runner_for(tmp_path / "two", WRITE_THE_FIX).run_suite(tasks)

    assert first.verdict_vector == second.verdict_vector
    assert first.verdict_vector == (("a-task", True), ("b-task", True))
    assert first.pass_rate == 1.0


def test_results_stay_in_task_order_under_parallelism(tmp_path: Path) -> None:
    tasks = two_tasks(tmp_path)
    serial = runner_for(tmp_path / "one", WRITE_THE_FIX).run_suite(tasks)
    parallel = runner_for(tmp_path / "two", WRITE_THE_FIX, jobs=4).run_suite(tasks)
    assert serial.verdict_vector == parallel.verdict_vector


def test_on_result_is_called_per_task(tmp_path: Path) -> None:
    seen: list[TaskResult] = []
    runner = EvalRunner(
        provider_factory=lambda task: FakeProvider(list(WRITE_THE_FIX)),
        sandbox_factory=lambda task: LocalSandbox(task.fixture, tmp_path / f"box-{task.id}"),
        on_result=seen.append,
    )
    runner.run_suite(two_tasks(tmp_path))
    assert [r.task_id for r in seen] == ["a-task", "b-task"]


def test_usage_accumulates_across_the_suite(tmp_path: Path) -> None:
    runner = runner_for(tmp_path, WRITE_THE_FIX)
    runner.run_suite(two_tasks(tmp_path))
    assert runner.accountant.total_usage.input_tokens == 440


def test_errored_tasks_are_separated_from_failed_ones(tmp_path: Path) -> None:
    def explode(task: Task) -> Sandbox:
        raise SandboxError("no daemon")

    suite = EvalRunner(
        provider_factory=lambda task: FakeProvider([]), sandbox_factory=explode
    ).run_suite(two_tasks(tmp_path))
    assert len(suite.errored) == 2
    assert suite.pass_rate == 0.0


def test_an_empty_suite_has_a_zero_pass_rate(tmp_path: Path) -> None:
    assert runner_for(tmp_path, WRITE_THE_FIX).run_suite([]).pass_rate == 0.0


# --- loading --------------------------------------------------------------


def test_discover_orders_by_id(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    make_task(root, graders=VALUE_GRADER, task_id="zzz")
    make_task(root, graders=VALUE_GRADER, task_id="aaa")
    assert [t.id for t in discover_tasks(root)] == ["aaa", "zzz"]


def test_duplicate_ids_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    make_task(root, graders=VALUE_GRADER, task_id="one")
    second = root / "two"
    (second / "fixture").mkdir(parents=True)
    (second / "prompt.md").write_text("x\n", encoding="utf-8")
    (second / "task.json").write_text(
        json.dumps({"id": "one", "graders": VALUE_GRADER}), encoding="utf-8"
    )
    with pytest.raises(TaskError, match="duplicate task id"):
        discover_tasks(root)


def test_malformed_tasks_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    with pytest.raises(TaskError, match="no such suite directory"):
        discover_tasks(root / "nope")

    empty = root / "empty"
    empty.mkdir(parents=True)
    with pytest.raises(TaskError, match="no task.json"):
        load_task(empty)

    broken = root / "broken"
    broken.mkdir(parents=True)
    (broken / "task.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(TaskError):
        load_task(broken)

    no_fixture = root / "no-fixture"
    no_fixture.mkdir(parents=True)
    (no_fixture / "task.json").write_text(json.dumps({"graders": VALUE_GRADER}), encoding="utf-8")
    with pytest.raises(TaskError, match="no fixture/"):
        load_task(no_fixture)


def test_a_task_needs_a_prompt_and_a_grader(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    directory = root / "bare"
    (directory / "fixture").mkdir(parents=True)
    (directory / "task.json").write_text(json.dumps({"graders": VALUE_GRADER}), encoding="utf-8")
    with pytest.raises(TaskError, match="no prompt"):
        load_task(directory)

    (directory / "task.json").write_text(json.dumps({"prompt": "do it"}), encoding="utf-8")
    with pytest.raises(TaskError, match="cannot pass or fail"):
        load_task(directory)


def test_an_unknown_category_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    task = make_task(root, graders=VALUE_GRADER)
    assert task.root is not None
    (task.root / "task.json").write_text(
        json.dumps({"id": "demo", "category": "vibes", "graders": VALUE_GRADER}),
        encoding="utf-8",
    )
    with pytest.raises(TaskError, match="unknown category"):
        load_task(task.root)


def test_the_prompt_file_wins_over_the_manifest(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    assert task.root is not None
    (task.root / "task.json").write_text(
        json.dumps({"id": "demo", "prompt": "from json", "graders": VALUE_GRADER}),
        encoding="utf-8",
    )
    assert load_task(task.root).prompt == "Set VALUE to 2."


def test_budget_and_limits_come_from_the_manifest(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    assert task.root is not None
    (task.root / "task.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "graders": VALUE_GRADER,
                "max_steps": 7,
                "timeout_s": 12.5,
                "budget": {"max_context_tokens": 1234},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_task(task.root)
    assert loaded.max_steps == 7
    assert loaded.timeout_s == 12.5
    assert loaded.budget.max_context_tokens == 1234


# --- repeated runs --------------------------------------------------------


def test_repeated_runs_of_a_flaky_agent_are_caught(tmp_path: Path) -> None:
    """The measurement has to fail on a suite that deserves it.

    A determinism check that only ever reports 0% is the same failure the whole
    eval suite is built to avoid: a number that looks like evidence and is not.
    So this drives a provider that fixes the file on odd attempts and shrugs on
    even ones, and asserts the rate comes back at 100%.
    """
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    attempts = itertools.count()

    def flaky(_task: Task) -> FakeProvider:
        return FakeProvider(
            list(WRITE_THE_FIX)
            if next(attempts) % 2 == 0
            else [Response(message=Message(role="assistant", content="looks fine"))]
        )

    def suite_in(box: Path) -> SuiteResult:
        return EvalRunner(
            provider_factory=flaky,
            sandbox_factory=lambda t: LocalSandbox(t.fixture, box),
        ).run_suite([task])

    suites = [suite_in(tmp_path / f"box-{run}") for run in range(2)]

    assert [s.results[0].passed for s in suites] == [True, False]
    assert flake_rate(suites) == 1.0
    assert "did not agree with themselves" in render_flake_markdown(suites)


def test_repeated_runs_of_a_stable_agent_are_clean(tmp_path: Path) -> None:
    task = make_task(tmp_path / "tasks", graders=VALUE_GRADER)
    suites = [
        runner_for(tmp_path / f"run-{run}", WRITE_THE_FIX).run_suite([task]) for run in range(3)
    ]

    assert flake_rate(suites) == 0.0
    assert len({s.verdict_vector for s in suites}) == 1
