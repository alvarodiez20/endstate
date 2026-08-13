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

from pydantic import BaseModel, Field

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
        return Verdict.from_checks([*self.checks, *other.checks])

    @property
    def failed_checks(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


class GraderSpec(BaseModel):
    """A dotted path to a grader, plus the arguments it is bound with.

    `endstate.evals.graders:command_succeeds` with `{"command": "..."}` resolves
    to a callable of exactly one argument — the sandbox — which is the contract
    the whole design rests on.
    """

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


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

    graders = [GraderSpec(**g) for g in data.get("graders", [])]
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
