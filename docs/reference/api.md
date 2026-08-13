# Python API

Generated from the source. For the reasoning behind these shapes, start with
[How agents actually work](../concepts/index.md).

## Running a loop directly

```python
from pathlib import Path

from endstate.agent.loop import AgentLoop
from endstate.agent.context import ContextManager, TokenBudget
from endstate.agent.permissions import default_policy
from endstate.agent.session import SessionStore
from endstate.agent.tools import default_tools
from endstate.agent.tools.base import ToolContext
from endstate.providers.openai_compat import OpenAICompatProvider

store = SessionStore()
loop = AgentLoop(
    provider=OpenAICompatProvider(model="gpt-4o-mini"),
    tools=default_tools(),
    tool_context=ToolContext(workdir=Path("./sandbox")),
    policy=default_policy(),
    context=ContextManager(budget=TokenBudget(max_context_tokens=128_000)),
    session=store.create(model="gpt-4o-mini"),
    max_steps=25,
)

result = loop.run("fix the failing test")
print(result.stop_reason, result.steps, result.usage.total_tokens)
```

## Running an eval suite

```python
from pathlib import Path

from endstate.evals import DockerSandbox, EvalRunner, discover_tasks, render_markdown
from endstate.providers.openai_compat import OpenAICompatProvider

tasks = discover_tasks(Path("tasks"))
runner = EvalRunner(
    provider_factory=lambda task: OpenAICompatProvider(model="gpt-4o-mini"),
    sandbox_factory=lambda task: DockerSandbox(task.fixture),
)
suite = runner.run_suite(tasks)
print(render_markdown(suite))
```

Both factories take the task, so a suite can vary the model or the image per task. Nothing in
`SuiteResult` reaches a grader: the verdict is decided before the result is assembled.

---

## Core types

::: endstate.types

---

## The loop

::: endstate.agent.loop

---

## Context and compaction

::: endstate.agent.context

---

## Permissions

::: endstate.agent.permissions

---

## Sessions

::: endstate.agent.session

---

## Tools

::: endstate.agent.tools.base

---

## Providers

::: endstate.providers.base

::: endstate.providers.fake

---

## Evals: tasks and verdicts

::: endstate.evals.task

---

## Evals: the sandbox

::: endstate.evals.sandbox

---

## Evals: graders

::: endstate.evals.graders

---

## Evals: the runner

::: endstate.evals.runner

---

## Evals: the report

::: endstate.evals.report

---

## Cost

::: endstate.telemetry.cost

---

## Tracing

::: endstate.telemetry.trace
