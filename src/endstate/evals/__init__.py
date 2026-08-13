"""Evals that grade the end state of a sandbox rather than the model's text.

The public surface, in the order you meet it:

```python
from endstate.evals import DockerSandbox, EvalRunner, discover_tasks, render_markdown

tasks = discover_tasks(Path("tasks"))
runner = EvalRunner(
    provider_factory=lambda task: my_provider,
    sandbox_factory=lambda task: DockerSandbox(task.fixture),
)
print(render_markdown(runner.run_suite(tasks)))
```
"""

from endstate.evals.graders import Grader, GraderContractError, grader_for, resolve
from endstate.evals.report import render_markdown, write_report
from endstate.evals.runner import EvalRunner, SuiteResult, TaskResult
from endstate.evals.sandbox import (
    DEFAULT_IMAGE,
    DockerSandbox,
    ExecResult,
    LocalSandbox,
    Sandbox,
    SandboxError,
    docker_available,
)
from endstate.evals.task import (
    Check,
    GraderSpec,
    Task,
    TaskError,
    Verdict,
    discover_tasks,
    load_task,
)
from endstate.evals.tools import SandboxBashTool, sandbox_tools

__all__ = [
    "DEFAULT_IMAGE",
    "Check",
    "DockerSandbox",
    "EvalRunner",
    "ExecResult",
    "Grader",
    "GraderContractError",
    "GraderSpec",
    "LocalSandbox",
    "Sandbox",
    "SandboxBashTool",
    "SandboxError",
    "SuiteResult",
    "Task",
    "TaskError",
    "TaskResult",
    "Verdict",
    "discover_tasks",
    "docker_available",
    "grader_for",
    "load_task",
    "render_markdown",
    "resolve",
    "sandbox_tools",
    "write_report",
]
