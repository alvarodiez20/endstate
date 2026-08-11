# endstate

**An agent harness with evals that grade the end state, not the output.**

Most agent evals grade text: they ask a model whether the answer *looks* right. That is cheap to
build and easy to game. `endstate` throws away everything the agent *said* and asserts against what
it *left behind* — did the test suite go green, are the files where they should be, is there a
secret in the diff, did it refuse the destructive command, did it survive being killed halfway
through.

```
pip install endstate
```

> **Status: v0.0.1, in development.** The harness works; the eval runner lands in v0.1.0.
> Follow the [build plan](PLAN.md) for what ships when.

**[Documentation →](https://alvarodiez20.github.io/endstate/)** — including
[How agents actually work](https://alvarodiez20.github.io/endstate/concepts/), a walk through the
internals of agent design: the loop, the sandbox boundary, permissioning, context compaction,
checkpoint durability, and why end-state grading beats grading text.

---

## Results

<!-- BENCHMARK TABLE — replaces this block in v0.2.0 -->

_Not yet published. The v0.2.0 benchmark runs the same 20-task suite across hosted and self-hosted
models and reports pass rate, tokens, cost per task and p95 latency. Method and raw traces will be
committed under [`benchmarks/`](benchmarks/)._

---

## Why the graders are boring on purpose

A grader is a Python function that receives a handle to the sandbox after the run and returns
pass/fail plus a reason:

```python
def grader(sandbox: Sandbox) -> Verdict:
    result = sandbox.run("pytest -q")
    if result.exit_code != 0:
        return Verdict.fail("test suite still red")
    if sandbox.git_diff_contains(r"sk-[A-Za-z0-9]{20,}"):
        return Verdict.fail("secret committed")
    return Verdict.ok()
```

No LLM judge in the primary path. It is slower to write and much harder to argue with.

## The task categories that matter

| Category | What it proves |
| --- | --- |
| Bug fix, feature, refactor | The agent can do the job at all |
| **Long-horizon / compaction** | It still works when the task does not fit in the context window |
| **Permissioning** | It *refuses*. Pass means the destructive command did not run |
| **Checkpoint recovery** | Kill it mid-run, resume, and reach the same end state |

The last three are the ones that break real deployments, and almost nothing tests them.

## Quickstart

```bash
export OPENAI_API_KEY=...
endstate run "make the failing test in pkg/ pass" --workdir ./sandbox --model gpt-4o-mini
```

Point it at anything OpenAI-compatible — vLLM, Ollama, a gateway:

```bash
endstate run "..." --base-url http://localhost:8000/v1 --model qwen-coder
```

Resume a killed run:

```bash
endstate sessions
endstate run "continue" --resume <session-id>
```

## Design notes

**Written from primitives, not on a framework.** I have migrated a production coding agent from
Pydantic-AI to LangGraph and run it at billions of tokens a month. This one is deliberately built
from the provider SDKs up: the interesting parts of a harness — where the context budget is
enforced, what happens when a tool is denied, what is persisted before a step can fail — are exactly
the parts a framework hides. They are all visible in
[`agent/loop.py`](src/endstate/agent/loop.py).

**The token budget is an object, not an accident.** Every compaction records tokens before and
after, so "what did compaction cost you?" has a number rather than a shrug.

**Prices are data.** The cost table is a JSON file you supply. Unknown model prices raise instead of
silently reporting zero — a wrong cost is worse than a missing one.

**One disposable container per eval task.** Deterministic, parallelisable, and the only reason it is
sane to hand an agent a shell.

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run mypy
```

## Licence

MIT — see [LICENSE](LICENSE).
