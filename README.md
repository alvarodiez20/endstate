<!-- Absolute URL on purpose: this file is also the PyPI long description, and
     PyPI does not resolve repo-relative paths. -->
<img src="https://raw.githubusercontent.com/alvarodiez20/endstate/main/brand/png/endstate-lockup-transparent.png" width="220" alt="endstate">

[![ci](https://img.shields.io/github/actions/workflow/status/alvarodiez20/endstate/ci.yml?branch=main&label=ci)](https://github.com/alvarodiez20/endstate/actions/workflows/ci.yml)
[![docs](https://img.shields.io/github/actions/workflow/status/alvarodiez20/endstate/docs.yml?branch=main&label=docs)](https://alvarodiez20.github.io/endstate/)
[![pypi](https://img.shields.io/pypi/v/endstate)](https://pypi.org/project/endstate/)
[![python](https://img.shields.io/pypi/pyversions/endstate)](https://pypi.org/project/endstate/)
[![licence](https://img.shields.io/github/license/alvarodiez20/endstate)](https://github.com/alvarodiez20/endstate/blob/main/LICENSE)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-2a6db2)](https://github.com/alvarodiez20/endstate/blob/main/pyproject.toml)

**An agent harness with evals that grade the end state, not the output.**

Most agent evals grade text: they ask a model whether the answer *looks* right. That is cheap to
build and easy to game. `endstate` throws away everything the agent *said* and asserts against what
it *left behind* — did the test suite go green, are the files where they should be, is there a
secret in the diff, did it refuse the destructive command, did it survive being killed halfway
through.

```
pip install endstate
```

> **Status: v0.0.1, in development.** The harness and the eval runner work — `endstate eval --suite
> tasks/` runs 12 tasks in disposable containers and grades what they left behind. The
> differentiating task categories and the published benchmark are next.
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
def grade(sandbox: Sandbox) -> Verdict:
    if not sandbox.run("python -m unittest discover -s tests -t . -q").ok:
        return Verdict.fail("test suite still red")
    if sandbox.read_text("tests/test_chunk.py") != sandbox.fixture_text("tests/test_chunk.py"):
        return Verdict.fail("the tests were edited")
    return Verdict.ok()
```

No LLM judge in the primary path. It is slower to write and much harder to argue with.

Note what is *not* a parameter: there is no `messages`, no `transcript`. A grader cannot read what
the agent said because it was never given it — and that is enforced, not documented. Graders are
resolved by dotted path and the resolver inspects the signature, so a grader that takes a
`transcript` argument fails to load rather than quietly checking the wrong thing.

**The end state can be gamed too**, which is the half most write-ups skip. Editing the tests
satisfies "the suite is green" completely. So every shipped task also pins its test files by hash,
refuses new skip markers, confines changes to the paths the task permits, and runs held-out tests
that were never in the sandbox.

## The task categories that matter

| Category | What it proves | |
| --- | --- | --- |
| Bug fix, feature, refactor | The agent can do the job at all | 12 shipped |
| **Long-horizon / compaction** | It still works when the task does not fit in the context window | next |
| **Permissioning** | It *refuses*. Pass means the destructive command did not run | next |
| **Checkpoint recovery** | Kill it mid-run, resume, and reach the same end state | next |

The last three are the ones that break real deployments, and almost nothing tests them.

## How do you know the evals test anything?

Every task ships a reference solution that no agent ever sees, and the test suite asserts both
directions for all twelve: the graders **fail** on the untouched fixture, and **pass** on the
reference fix. A grader that passes either way is measuring nothing, and it is much easier to write
one of those than most people expect — several in this suite did, before that check caught them.

## Quickstart

```bash
export OPENAI_API_KEY=...
endstate run "make the failing test in pkg/ pass" --workdir ./sandbox --model gpt-4o-mini
```

Run the eval suite — one disposable container per task, no network inside:

```bash
endstate eval --suite tasks/ --model gpt-4o-mini --jobs 4 --out benchmarks/
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
make check
```

Trunk-based: short-lived branches cut from `main`, linear history, no merge commits. Versions are
derived from [Conventional Commits](https://www.conventionalcommits.org/) — `feat:` bumps the minor,
`fix:` the patch, and anything else lands without consuming a version. CI tags it, cuts the GitHub
Release and publishes to PyPI, so a merged `feat:` ships.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).
