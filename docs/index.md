# ![endstate](assets/brand/svg/endstate-lockup.svg#only-light){ width="260" }![endstate](assets/brand/svg/endstate-lockup-white.svg#only-dark){ width="260" }

[![ci](https://img.shields.io/github/actions/workflow/status/alvarodiez20/endstate/ci.yml?branch=main&label=ci)](https://github.com/alvarodiez20/endstate/actions/workflows/ci.yml)
[![docs](https://img.shields.io/github/actions/workflow/status/alvarodiez20/endstate/docs.yml?branch=main&label=docs)](https://github.com/alvarodiez20/endstate/actions/workflows/docs.yml)
[![pypi](https://img.shields.io/pypi/v/endstate)](https://pypi.org/project/endstate/)
[![python](https://img.shields.io/pypi/pyversions/endstate)](https://pypi.org/project/endstate/)
[![licence](https://img.shields.io/github/license/alvarodiez20/endstate)](https://github.com/alvarodiez20/endstate/blob/main/LICENSE)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-2a6db2)](https://github.com/alvarodiez20/endstate/blob/main/pyproject.toml)

**An agent harness with evals that grade the end state, not the output.**

Most agent evaluations grade text. They ask a model whether an answer *looks* right. That is cheap
to build, easy to game, and tells you almost nothing about whether the thing works when you point it
at a real repository.

`endstate` throws away everything the agent *said* and asserts against what it *left behind*. Did the
test suite go green? Are the files where they should be? Is there a secret in the diff? Did it refuse
the destructive command? Did it survive being killed halfway through?

```bash
pip install endstate
```

!!! info "Status: v0.1.0 on PyPI"

    The harness and the eval runner both work: `endstate eval --suite tasks/` runs 22 tasks in
    disposable containers and grades what they left behind. The published benchmark across hosted
    and self-hosted models is next. These docs describe what exists today and say so explicitly when
    something is planned rather than shipped.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="assets/diagrams/hero.html"
          height="645" loading="lazy"
          title="The endstate thesis: the transcript is discarded, the sandbox is graded"></iframe>
</div>

---

## These docs have two jobs

<div class="grid cards" markdown>

-   **Teach how agents actually work**

    ---

    The [Concepts](concepts/index.md) section is a course in agent internals. Not "an agent is an
    LLM in a loop with tools" — the parts underneath: what a message really is, where the sandbox
    boundary belongs, why the context window is a budgeting problem, what a checkpoint has to
    guarantee, why refusal is a feature you have to test for.

    Every concept is grounded in code you can read in one sitting.

    [Start with the loop →](concepts/the-loop.md)

-   **Get you running the harness**

    ---

    Install it, point it at a model, hand it a directory, watch what it does to that directory.

    [Install →](getting-started/installation.md)

</div>

## Why the source is small enough to read

The harness is written from the provider SDKs up rather than on a framework. That is a teaching
decision as much as an engineering one: the interesting parts of an agent — where the context budget
is enforced, what happens when a tool is denied, what is persisted before a step can fail — are
exactly the parts a framework hides behind a decorator.

They are all visible in one file,
[`agent/loop.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/loop.py),
and it is about 150 lines. Every concept page in these docs links to the code that implements it, so
you can always check the explanation against the thing itself.

## The claim worth testing

Three properties break real agent deployments, and almost nothing in the ecosystem tests them:

| Property | The question it answers |
| --- | --- |
| **Compaction** | Does it still work when the task no longer fits in the context window? |
| **Permissioning** | Does it *refuse*? Pass means the destructive command did not run. |
| **Recovery** | Kill it mid-run, resume it — does it reach the same end state? |

An eval suite that grades text cannot ask any of these questions, because none of the answers are in
the transcript. They are all in the sandbox afterwards. That is the whole argument for the project,
and [Evaluation](concepts/evaluation.md) works through it properly.
