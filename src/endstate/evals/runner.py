"""Running a suite.

The sequence for one task, in the order it has to happen:

1. Copy the fixture into a fresh sandbox and start it.
2. Let the agent work, with the shell wired into the sandbox.
3. **Seal** the end state — hash it, snapshot it.
4. *Then* stage the held-out tests in and grade.

Step 3 before step 4 is the whole reason `seal()` exists. Held-out tests are
files; staging them in before hashing would mean every grader that asserts on
the tree was asserting on a tree the grader itself had modified.

What the runner deliberately does not do is give the grader anything but the
sandbox. The `RunResult` — steps, tokens, transcript — is recorded in the
`TaskResult` for the report, and it is never in scope where a verdict is decided.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from endstate.agent.context import ContextManager
from endstate.agent.loop import AgentLoop
from endstate.agent.permissions import PermissionPolicy, default_policy
from endstate.agent.tools.base import ToolContext
from endstate.evals.graders import Grader, grader_for
from endstate.evals.sandbox import Sandbox, SandboxError
from endstate.evals.task import Task, Verdict
from endstate.evals.tools import sandbox_tools
from endstate.telemetry.cost import CostAccountant, PriceTable
from endstate.types import Message, Response, StopReason, Usage

DEFAULT_SYSTEM_PROMPT = """\
You are working inside a disposable sandbox on a small codebase. There is no
network access. Make the change the task asks for by editing the files, and
verify your work by running the project's tests before you finish.

Do not modify the existing tests to make them pass. If a test fails, the code is
what is wrong.\
"""

ProviderFactory = Callable[[Task], Any]
SandboxFactory = Callable[[Task], Sandbox]


class TaskResult(BaseModel):
    """Everything recorded about one task run.

    The verdict is the answer; the rest is what makes a benchmark table more
    informative than a pass rate. A model that passes in 6 steps for $0.02 and
    one that passes in 34 steps for $1.40 are not the same product.
    """

    task_id: str
    category: str
    verdict: Verdict
    steps: int = 0
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = StopReason.END_TURN
    compaction_events: int = 0
    denied_calls: int = 0
    unsettled_calls: int = 0
    wall_clock_s: float = 0.0
    tree_hash: str = ""
    model: str = ""
    timed_out: bool = False
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict.passed


class SuiteResult(BaseModel):
    """The outcome of a whole suite against one model."""

    model: str = ""
    provider: str = ""
    sandbox: str = ""
    started_at: str = ""
    duration_s: float = 0.0
    results: list[TaskResult] = Field(default_factory=list)

    @property
    def verdict_vector(self) -> tuple[tuple[str, bool], ...]:
        """The determinism criterion, as a value you can compare with `==`.

        Task id and pass/fail only. Wall clock, token counts and step counts all
        vary between identical runs; if any of them were in here, the criterion
        would be untestable rather than merely hard.
        """
        return tuple((r.task_id, r.passed) for r in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def errored(self) -> list[TaskResult]:
        """Tasks where the *harness* failed, which is not the same as a fail."""
        return [r for r in self.results if r.error]


class _DeadlineProvider:
    """Wraps a provider and stops the loop once the task's clock runs out.

    Returning an ordinary end-of-turn response rather than raising is what keeps
    a timeout gradeable: the loop unwinds normally, the `RunResult` is intact,
    and the sandbox still gets hashed. A task that ran out of time has an end
    state, and it is usually the interesting part of why it ran out.
    """

    def __init__(self, provider: Any, timeout_s: float) -> None:
        self.provider = provider
        self.deadline = time.monotonic() + timeout_s
        self.expired = False

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response:
        if time.monotonic() >= self.deadline:
            self.expired = True
            return Response(
                message=Message(role="assistant", content="task timed out"),
                stop_reason=StopReason.ERROR,
                model=str(getattr(self.provider, "model", "")),
            )
        return self.provider.complete(messages, tools)  # type: ignore[no-any-return]


class EvalRunner:
    """Runs tasks. One sandbox per task, one provider per task, no shared state."""

    def __init__(
        self,
        provider_factory: ProviderFactory,
        sandbox_factory: SandboxFactory,
        *,
        policy: PermissionPolicy | None = None,
        prices: PriceTable | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        tool_timeout_s: float = 60.0,
        jobs: int = 1,
        provider_name: str = "",
        sandbox_name: str = "",
        on_result: Callable[[TaskResult], None] | None = None,
    ) -> None:
        self.provider_factory = provider_factory
        self.sandbox_factory = sandbox_factory
        self.policy = policy or default_policy()
        self.prices = prices or PriceTable()
        self.system_prompt = system_prompt
        self.tool_timeout_s = tool_timeout_s
        self.jobs = max(1, jobs)
        self.provider_name = provider_name
        self.sandbox_name = sandbox_name
        self.on_result = on_result
        self.accountant = CostAccountant(self.prices)
        self._lock = threading.Lock()

    def run_task(self, task: Task) -> TaskResult:
        started = time.monotonic()
        try:
            return self._run_task(task, started)
        except Exception as exc:  # noqa: BLE001 - a batch job survives one bad task
            # A sandbox that will not start or a provider that returns 503 is a
            # *harness* problem, and `error` keeps it out of the pass rate:
            # reporting it as a task failure would quietly turn "Docker is not
            # running" into "this model cannot code". Catching broadly is the
            # right trade for a suite — losing the other nineteen results to an
            # exception on task seven is worse than recording it and moving on.
            label = "sandbox error" if isinstance(exc, SandboxError) else type(exc).__name__
            return TaskResult(
                task_id=task.id,
                category=task.category,
                verdict=Verdict.fail(f"{label}: {exc}"),
                wall_clock_s=time.monotonic() - started,
                error=f"{label}: {exc}",
            )

    def _run_task(self, task: Task, started: float) -> TaskResult:
        provider = self.provider_factory(task)
        deadline = _DeadlineProvider(provider, task.timeout_s)
        accountant = CostAccountant(self.prices)

        with self.sandbox_factory(task) as sandbox:
            loop = AgentLoop(
                provider=deadline,
                tools=sandbox_tools(sandbox),
                tool_context=ToolContext(workdir=sandbox.workdir, timeout_s=self.tool_timeout_s),
                policy=self.policy,
                context=ContextManager(budget=task.budget),
                accountant=accountant,
                max_steps=task.max_steps,
                system_prompt=self.system_prompt,
            )
            run = loop.run(task.prompt)

            end_state = sandbox.seal()
            if task.holdout is not None:
                sandbox.stage(task.holdout)
            verdict = self._grade(task, sandbox)

        # Per-task accounting is merged into the suite total under a lock: with
        # jobs > 1 the merge is a read-modify-write on a shared dict.
        with self._lock:
            for model, usage in accountant.usage_by_model.items():
                self.accountant.record(model, usage)

        return TaskResult(
            task_id=task.id,
            category=task.category,
            verdict=verdict,
            steps=run.steps,
            usage=run.usage,
            stop_reason=run.stop_reason,
            compaction_events=len(run.compaction_events),
            denied_calls=len(run.denied_calls),
            unsettled_calls=len(run.unsettled_calls),
            wall_clock_s=time.monotonic() - started,
            tree_hash=end_state,
            model=str(getattr(provider, "model", "")),
            timed_out=deadline.expired,
        )

    def _grade(self, task: Task, sandbox: Sandbox) -> Verdict:
        try:
            grader: Grader = grader_for(task.graders)
            return grader(sandbox)
        except Exception as exc:  # noqa: BLE001 - a broken grader must not sink the suite
            return Verdict.fail(f"grader raised {type(exc).__name__}: {exc}")

    def run_suite(self, tasks: Sequence[Task]) -> SuiteResult:
        """Run every task and return the results in task order.

        Order is independent of completion order even with `jobs > 1`, because
        the pass/fail vector is only comparable between runs if its index is
        stable.
        """
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.jobs == 1:
            results = [self._collect(task) for task in tasks]
        else:
            with ThreadPoolExecutor(max_workers=self.jobs) as pool:
                results = list(pool.map(self._collect, tasks))

        return SuiteResult(
            model=next((r.model for r in results if r.model), ""),
            provider=self.provider_name,
            sandbox=self.sandbox_name,
            started_at=started_at,
            duration_s=time.monotonic() - started,
            results=results,
        )

    def _collect(self, task: Task) -> TaskResult:
        result = self.run_task(task)
        if self.on_result is not None:
            self.on_result(result)
        return result
