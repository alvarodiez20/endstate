"""The mutation check: remove a guard, and the tasks that test it must fail.

Here is the uncomfortable question this file exists to answer. A test suite that
passes whether or not the feature works is decoration — so how do you know the
eval suite tests what it claims?

By sabotage. Each differentiating category has a guard behind it, and each guard
is removed here on purpose:

| Guard removed | Category that must notice |
| --- | --- |
| The permission policy | permissioning |
| The context budget | compaction |
| Resume reconciliation | recovery |

If a guard can be taken away and the tasks stay green, that guard was never
load-bearing and the tasks were measuring something else.

The provider is scripted throughout. That is the point rather than a compromise:
a mutation check asks whether the *harness* is load-bearing, and a real model
would add variance without adding evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from endstate.agent.context import TokenBudget
from endstate.agent.permissions import Decision, PermissionPolicy, Rule
from endstate.evals.runner import EvalRunner, TaskResult
from endstate.evals.sandbox import LocalSandbox
from endstate.evals.task import Task, discover_tasks, load_task
from endstate.providers.fake import FakeProvider
from endstate.types import Message, Response, StopReason, ToolCall, Usage

SUITE = Path(__file__).resolve().parent.parent / "tasks"
TASKS = {t.id: t for t in discover_tasks(SUITE)}

ALLOW_EVERYTHING = PermissionPolicy(
    rules=[Rule(tool="*", decision=Decision.ALLOW)], default=Decision.ALLOW
)


def says(*calls: ToolCall, text: str = "done") -> list[Response]:
    """A two-step script: one batch of tool calls, then a final message."""
    return [
        Response(
            message=Message(role="assistant", content="working", tool_calls=list(calls)),
            usage=Usage(input_tokens=200, output_tokens=40),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        ),
        Response(
            message=Message(role="assistant", content=text),
            usage=Usage(input_tokens=220, output_tokens=10),
            stop_reason=StopReason.END_TURN,
            model="fake-1",
        ),
    ]


def run_task(
    task: Task,
    responses: list[Response],
    tmp_path: Path,
    *,
    policy: PermissionPolicy | None = None,
) -> TaskResult:
    runner = EvalRunner(
        provider_factory=lambda t: FakeProvider(list(responses)),
        sandbox_factory=lambda t: LocalSandbox(t.fixture, tmp_path / f"box-{t.id}"),
        policy=policy,
    )
    return runner.run_task(task)


def with_budget(task: Task, max_context_tokens: int) -> Task:
    """The same task with its context budget replaced."""
    return task.model_copy(update={"budget": TokenBudget(max_context_tokens=max_context_tokens)})


# --- guard 1: the permission policy ---------------------------------------


DESTRUCTIVE = ToolCall(id="d1", name="bash", arguments={"command": "rm -rf data"})


def test_the_permissioning_task_passes_while_the_policy_holds(tmp_path: Path) -> None:
    """The agent tries the destructive command; the harness is what stops it."""
    result = run_task(TASKS["deny-recursive-delete"], says(DESTRUCTIVE), tmp_path)

    assert result.passed, [str(c) for c in result.verdict.checks]
    assert result.denied_calls == 1, "the policy did not fire, so nothing was tested"


def test_removing_the_policy_fails_the_permissioning_task(tmp_path: Path) -> None:
    """The mutation. With the deny-list gone, `rm -rf data` runs for real."""
    result = run_task(
        TASKS["deny-recursive-delete"], says(DESTRUCTIVE), tmp_path, policy=ALLOW_EVERYTHING
    )

    assert not result.passed, "the destructive command ran and the task still passed"
    assert result.denied_calls == 0
    failed = {c.name for c in result.verdict.failed_checks}
    assert "the sandbox is untouched" in failed


def test_an_agent_that_simply_ignores_the_request_does_not_pass(tmp_path: Path) -> None:
    """`tree_unchanged` alone cannot tell refusal from inaction.

    This is why the category carries a `requires` block. An agent that never
    attempted the command leaves exactly the same filesystem as one the harness
    stopped, and only `denied_calls >= 1` separates them.
    """
    result = run_task(TASKS["deny-recursive-delete"], says(text="I would rather not"), tmp_path)

    assert not result.passed
    assert result.denied_calls == 0
    assert any("denied calls" in c.name for c in result.verdict.failed_checks)


# --- guard 2: the context budget ------------------------------------------


def chatter(rounds: int) -> list[Response]:
    """A script long-winded enough to overflow a small budget."""
    filler = "thinking about the catalogue in some detail. " * 200
    responses = [
        Response(
            message=Message(
                role="assistant",
                content=filler,
                tool_calls=[
                    ToolCall(id=f"r{i}", name="read", arguments={"path": "catalogue/items.py"})
                ],
            ),
            usage=Usage(input_tokens=400, output_tokens=120),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        )
        for i in range(rounds)
    ]
    fixed = (
        SUITE / "compaction-audit-every-module" / "solution" / "catalogue" / "registry.py"
    ).read_text()
    responses += says(
        ToolCall(
            id="w", name="write", arguments={"path": "catalogue/registry.py", "content": fixed}
        )
    )
    return responses


def test_the_compaction_task_passes_when_the_budget_bites(tmp_path: Path) -> None:
    task = TASKS["compaction-audit-every-module"]
    result = run_task(task, chatter(8), tmp_path)

    assert result.passed, [str(c) for c in result.verdict.checks]
    assert result.compaction_events >= 1, "compaction never fired, so nothing was tested"


def test_removing_the_budget_fails_the_compaction_task(tmp_path: Path) -> None:
    """The mutation. Same work, same end state — but compaction never happened.

    The end state is *correct* here, which is exactly the point: a task graded
    only on its files would pass this and report coverage it does not have.
    """
    task = with_budget(TASKS["compaction-audit-every-module"], 10_000_000)
    result = run_task(task, chatter(8), tmp_path)

    assert result.compaction_events == 0
    assert not result.passed, "compaction was disabled and the task still passed"
    assert any("compaction events" in c.name for c in result.verdict.failed_checks)


# --- guard 3: resume reconciliation ---------------------------------------


def fixes_the_pipeline() -> list[Response]:
    fixed = (
        SUITE / "recovery-killed-before-the-write" / "solution" / "pipeline" / "stages.py"
    ).read_text()
    return [
        Response(
            message=Message(
                role="assistant",
                tool_calls=[
                    ToolCall(id="a", name="read", arguments={"path": "pipeline/stages.py"}),
                    ToolCall(
                        id="b",
                        name="write",
                        arguments={"path": "pipeline/stages.py", "content": fixed},
                    ),
                ],
            ),
            usage=Usage(input_tokens=300, output_tokens=90),
            stop_reason=StopReason.TOOL_USE,
            model="fake-1",
        ),
        Response(
            message=Message(role="assistant", content="fixed"),
            usage=Usage(input_tokens=320, output_tokens=10),
            stop_reason=StopReason.END_TURN,
            model="fake-1",
        ),
    ]


@pytest.mark.parametrize(
    "task_id", ["recovery-killed-before-the-write", "recovery-killed-after-the-write"]
)
def test_the_recovery_tasks_survive_being_killed(task_id: str, tmp_path: Path) -> None:
    """Killed mid-batch, resumed by a fresh loop, and the work still lands."""
    result = run_task(TASKS[task_id], fixes_the_pipeline(), tmp_path)
    assert result.passed, [str(c) for c in result.verdict.checks]


def test_without_resume_the_kill_leaves_the_task_unfinished(tmp_path: Path) -> None:
    """The mutation, done by leaving the reconciliation out.

    A task killed at the same point but never resumed must fail. If it passed,
    the recovery tasks would be proving nothing about resume — only that the
    work happened to land before the crash.
    """
    task = TASKS["recovery-killed-before-the-write"]
    from endstate.evals.recovery import Crash, CrashAt
    from endstate.evals.tools import sandbox_tools

    with LocalSandbox(task.fixture, tmp_path / "box") as sandbox:
        from endstate.agent.loop import AgentLoop
        from endstate.agent.tools.base import ToolContext

        crashing = CrashAt(sandbox_tools(sandbox), 1, after_side_effect=False)
        loop = AgentLoop(
            provider=FakeProvider(fixes_the_pipeline()),
            tools=crashing.tools,
            tool_context=ToolContext(workdir=sandbox.workdir),
        )
        with pytest.raises(Crash):
            loop.run(task.prompt)

        # No resume. The write never happened, so the suite is still red.
        assert not sandbox.run("python -m unittest discover -s tests -t . -q").ok


# --- the check itself is exhaustive ---------------------------------------


def test_every_differentiating_category_has_a_mutation_here() -> None:
    """A guard nobody sabotaged is a guard nobody has shown to be load-bearing."""
    covered = {"permissioning", "compaction", "recovery"}
    categories = {t.category for t in TASKS.values()}
    missing = (categories & {"permissioning", "compaction", "recovery"}) - covered
    assert not missing, f"no mutation test for {missing}"


def test_a_task_manifest_cannot_smuggle_the_transcript_into_a_grader(tmp_path: Path) -> None:
    """The `requires` block is a closed set of counters, not an open door.

    It exists because `compaction_events` is not a property of the filesystem.
    The reason that does not reopen the door the grader signature closed is that
    a task author cannot name anything else here.
    """
    directory = tmp_path / "sneaky"
    (directory / "fixture").mkdir(parents=True)
    (directory / "prompt.md").write_text("do it\n", encoding="utf-8")
    (directory / "task.json").write_text(
        json.dumps(
            {
                "id": "sneaky",
                "graders": [{"name": "endstate.evals.graders:paths_exist", "args": {"paths": []}}],
                "requires": {"final_text": {"min": 1}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="final_text|extra"):
        load_task(directory)
