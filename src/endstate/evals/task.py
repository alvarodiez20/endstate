"""What a task is, and what a verdict is.

A task on disk is a directory. That is a deliberate choice over a single big
manifest file: the fixture is a real repository the agent works in, the prompt
is prose someone will edit, and the held-out tests must be storable *next to*
the task without being shipped into the sandbox with it.

```text
tasks/fix-off-by-one/
├── task.json      metadata, budget, graders
├── prompt.md      what the agent is told
├── fixture/       copied into the sandbox; this is the agent's whole world
├── holdout/       staged in at grading time only — the agent never sees it
└── solution/      a reference fix, used to prove the graders are load-bearing
```

`solution/` never reaches an agent. It exists so the suite can answer the
question that decides whether any of this is worth anything: *does this grader
fail on the unsolved fixture and pass on a correct fix?* A grader that passes
either way is measuring nothing, and it is much easier to write one of those
than most people expect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from endstate.agent.context import TokenBudget

TASK_FILE = "task.json"
PROMPT_FILE = "prompt.md"
FIXTURE_DIR = "fixture"
HOLDOUT_DIR = "holdout"
SOLUTION_DIR = "solution"

CATEGORIES = ("bug-fix", "feature", "refactor", "compaction", "permissioning", "recovery", "cost")


class TaskError(ValueError):
    """Raised when a task on disk is malformed."""


class Check(BaseModel):
    """One assertion, reported individually.

    Graders return every check they ran, not just the one that failed. "The
    tests pass but you edited them" and "the tests fail" are different findings,
    and a verdict that collapses to a single boolean cannot tell you which.
    """

    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "pass" if self.passed else "FAIL"
        return f"[{mark}] {self.name}{': ' + self.detail if self.detail else ''}"


class Verdict(BaseModel):
    """A grader's answer. Pure function of the sandbox's end state."""

    passed: bool
    reason: str = ""
    checks: list[Check] = Field(default_factory=list)

    @classmethod
    def ok(cls, reason: str = "", checks: list[Check] | None = None) -> Verdict:
        return cls(passed=True, reason=reason, checks=checks or [])

    @classmethod
    def fail(cls, reason: str, checks: list[Check] | None = None) -> Verdict:
        return cls(passed=False, reason=reason, checks=checks or [])

    @classmethod
    def from_checks(cls, checks: list[Check]) -> Verdict:
        """Conjunction: every check must pass, and the reason names the ones that did not."""
        failed = [c for c in checks if not c.passed]
        if failed:
            return cls(passed=False, reason="; ".join(c.name for c in failed), checks=checks)
        return cls(passed=True, checks=checks)

    def merged_with(self, other: Verdict) -> Verdict:
        """Conjunction of two verdicts, keeping every check from both.

        `passed` is conjoined explicitly rather than recomputed from the merged
        checks, because a verdict can fail while carrying none: a grader that
        raised reports a reason and an empty list. Recomputing would turn that
        into a pass — the worst possible direction for a failure to be lost in.
        """
        checks = [*self.checks, *other.checks]
        reasons = [v.reason for v in (self, other) if not v.passed and v.reason]
        reasons += [c.name for c in checks if not c.passed]
        return Verdict(
            passed=self.passed and other.passed,
            reason="; ".join(dict.fromkeys(reasons)),
            checks=checks,
        )

    @property
    def failed_checks(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


class GraderSpec(BaseModel):
    """A dotted path to a grader, plus the arguments it is bound with.

    `endstate.evals.graders:command_succeeds` with `{"command": "..."}` resolves
    to a callable of exactly one argument — the sandbox — which is the contract
    the whole design rests on.
    """

    model_config = {"extra": "forbid"}

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class Bound(BaseModel):
    """An inclusive range. Either end may be left out.

    Unknown keys are refused. A `{"minimum": 1}` typo would otherwise parse as a
    bound with no ends, which passes for *any* value — so the requirement would
    read as asserted in the task file and assert nothing at all. That is the
    exact failure this whole design is meant to rule out, so it is an error.
    """

    model_config = {"extra": "forbid"}

    min: int | None = None
    max: int | None = None

    def check(self, value: int, label: str) -> Check:
        passed = (self.min is None or value >= self.min) and (self.max is None or value <= self.max)
        return Check(name=f"{label} {self}", passed=passed, detail=f"was {value}")

    def __str__(self) -> str:
        if self.min is not None and self.max is not None:
            return f"is {self.min}" if self.min == self.max else f"is {self.min}-{self.max}"
        if self.min is not None:
            return f"is at least {self.min}"
        if self.max is not None:
            return f"is at most {self.max}"
        return "is anything"


class RunRequirements(BaseModel):
    """Assertions about the *run* that the filesystem cannot answer.

    Three of the four differentiating categories need one of these. "The task
    completed **and** compaction fired at least once" is the whole point of a
    long-horizon task — a run that finished without ever compacting did not test
    compaction, and passing it would be a lie about coverage. But
    `compaction_events` is not a property of the sandbox, so no grader can see
    it without being handed something other than the sandbox.

    Rather than widen the grader signature, requirements are evaluated by the
    **runner** and conjoined with the grader's verdict. That keeps
    `grade(sandbox) -> Verdict` exactly as narrow as it was, and the reason it is
    safe is the shape of this class: every field is a typed counter the harness
    recorded itself — policy decisions, compaction events, token totals. There is
    no field here that can reach message content, and adding one would be a
    visible change to this model rather than a quiet argument in a task file.

    `extra="forbid"` is what makes that last sentence true rather than merely
    intended: a manifest naming `final_text` is rejected at load time instead of
    being silently dropped.
    """

    model_config = {"extra": "forbid"}

    compaction_events: Bound | None = None
    denied_calls: Bound | None = None
    unsettled_calls: Bound | None = None
    steps: Bound | None = None
    input_tokens: Bound | None = None
    output_tokens: Bound | None = None
    total_tokens: Bound | None = None
    stop_reason: str | None = None

    def check(self, counters: dict[str, int], stop_reason: str) -> list[Check]:
        """Every requirement, as individually reported checks."""
        checks: list[Check] = []
        for field, bound in self:
            if field == "stop_reason" or bound is None:
                continue
            assert isinstance(bound, Bound)
            checks.append(bound.check(counters[field], field.replace("_", " ")))
        if self.stop_reason is not None:
            checks.append(
                Check(
                    name=f"stop reason is {self.stop_reason}",
                    passed=stop_reason == self.stop_reason,
                    detail=f"was {stop_reason}",
                )
            )
        return checks


class Recovery(BaseModel):
    """Kill the run partway through, then resume it.

    `crash_at_call` counts tool calls across the whole run, not steps, because
    the interesting kill points are inside a batch. `after_side_effect` picks the
    window: False is the honest kill where the work never happened, True is the
    irreducible one where it happened and nothing recorded it.
    """

    crash_at_call: int
    after_side_effect: bool = False


class Task(BaseModel):
    """One eval task, loaded from a directory."""

    id: str
    prompt: str
    fixture: Path
    graders: list[GraderSpec]
    category: str = "bug-fix"
    description: str = ""
    max_steps: int = 25
    timeout_s: float = 300.0
    budget: TokenBudget = Field(default_factory=TokenBudget)
    requires: RunRequirements = Field(default_factory=RunRequirements)
    recovery: Recovery | None = None
    holdout: Path | None = None
    solution: Path | None = None
    root: Path | None = None

    model_config = {"arbitrary_types_allowed": True}


def load_task(directory: Path) -> Task:
    """Load one task directory.

    Raises:
        TaskError: If the directory is not a well-formed task.
    """
    directory = Path(directory).resolve()
    manifest = directory / TASK_FILE
    if not manifest.is_file():
        raise TaskError(f"no {TASK_FILE} in {directory}")

    try:
        data: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaskError(f"{manifest}: {exc}") from exc

    fixture = directory / FIXTURE_DIR
    if not fixture.is_dir():
        raise TaskError(f"{directory}: no {FIXTURE_DIR}/ directory")

    prompt = data.get("prompt", "")
    prompt_file = directory / PROMPT_FILE
    if prompt_file.is_file():
        prompt = prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        raise TaskError(f"{directory}: no prompt, in {PROMPT_FILE} or in {TASK_FILE}")

    try:
        graders = [GraderSpec(**g) for g in data.get("graders", [])]
        requires = RunRequirements(**data.get("requires", {}))
        recovery = Recovery(**data["recovery"]) if "recovery" in data else None
    except ValidationError as exc:
        raise TaskError(f"{manifest}: {exc}") from exc
    if not graders:
        raise TaskError(f"{directory}: a task with no graders cannot pass or fail")

    category = data.get("category", "bug-fix")
    if category not in CATEGORIES:
        raise TaskError(f"{directory}: unknown category {category!r}, expected one of {CATEGORIES}")

    holdout = directory / HOLDOUT_DIR
    solution = directory / SOLUTION_DIR
    return Task(
        id=data.get("id", directory.name),
        prompt=prompt,
        fixture=fixture,
        graders=graders,
        category=category,
        description=data.get("description", ""),
        max_steps=int(data.get("max_steps", 25)),
        timeout_s=float(data.get("timeout_s", 300.0)),
        budget=TokenBudget(**data["budget"]) if "budget" in data else TokenBudget(),
        requires=requires,
        recovery=recovery,
        holdout=holdout if holdout.is_dir() else None,
        solution=solution if solution.is_dir() else None,
        root=directory,
    )


def discover_tasks(root: Path) -> list[Task]:
    """Find every task under `root`, ordered by id.

    Ordering is not cosmetic. The determinism criterion is an identical pass/fail
    *vector* across runs, and a vector needs a stable index.

    Raises:
        TaskError: If `root` is not a directory, or two tasks share an id.
    """
    root = Path(root)
    if not root.is_dir():
        raise TaskError(f"no such suite directory: {root}")

    tasks = [load_task(manifest.parent) for manifest in sorted(root.rglob(TASK_FILE))]
    seen: dict[str, Path] = {}
    for task in tasks:
        if task.id in seen:
            raise TaskError(f"duplicate task id {task.id!r}: {seen[task.id]} and {task.root}")
        seen[task.id] = task.root or root
    return sorted(tasks, key=lambda t: t.id)
