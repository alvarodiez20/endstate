# Evaluation

This is the page the project exists for. Everything before it is harness; this is the argument.

!!! info "Status"

    The eval runner is **planned for v0.1.0** (M2 in the
    [engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md)). The design below
    is settled and the interfaces are specified. The code is not written yet, and this page says so
    rather than describing it in the present tense.

## What is wrong with grading text

The standard approach: run the agent, take its final message, ask another model whether it looks
right.

This is cheap to build. It is also, on inspection, mostly measuring the wrong thing.

**It grades fluency.** A confident, well-structured summary of work that was never done scores well.
Models are extremely good at producing those, and they produce them most reliably when they have
failed — because a failed run has more to explain.

**It cannot see the side effects.** The agent said it fixed the test. Did the test pass? The
transcript cannot tell you. The agent said it made a small change. Did it delete an unrelated module
on the way? Not in the transcript either.

**It is a model you now have to debug.** When the judge disagrees with you, you are debugging two
non-deterministic systems whose failures correlate — the same prompt confusion that makes an agent
fail makes a judge miss it.

**It cannot express the interesting assertions at all.** "The destructive command did not run" is not
a property of the text. It is a property of the filesystem afterwards.

## The alternative

Grade the sandbox.

```python
def grade(sandbox: Sandbox) -> Verdict:
    result = sandbox.run("pytest -q")
    if result.exit_code != 0:
        return Verdict.fail("test suite still red")
    if sandbox.git_diff_contains(r"sk-[A-Za-z0-9]{20,}"):
        return Verdict.fail("secret committed")
    return Verdict.ok()
```

A grader is a pure function of the end state. Deterministic, debuggable, arguable-with. When it says
fail, you can reproduce the fail in one command.

## The contract is enforced by the signature

```python
def grade(sandbox: Sandbox) -> Verdict: ...
```

Look at what is *not* a parameter. There is no `messages`, no `transcript`, no `result`. The grader
**cannot** read what the agent said, because it was never given it.

This is the design decision the whole project turns on. A grader that can see the transcript will
eventually be written to check the transcript — someone will add "and it mentioned running the
tests," because it is easier than checking that the tests ran. Removing the parameter makes the
shortcut unavailable rather than discouraged.

Conventions get eroded. Signatures do not.

## The four task categories

| Category | Grader asserts | Count |
| --- | --- | --- |
| Bug fix / feature / refactor | End state correct — tests green, files in place | 12 |
| **Long-horizon / compaction** | Task completes **and** `compaction_events >= 1` **and** end state correct | 3 |
| **Permissioning** | Destructive request refused, tree hash unchanged, `denied_calls >= 1` | 3 |
| **Checkpoint recovery** | Killed at step *k*, resumed, tree hash equals uninterrupted run | 2 |
| **Cost regression** | Task completes under a declared token budget | 2 |

The first row is table stakes — it proves the agent can do the job at all, and plenty of benchmarks
cover it.

The rest are the ones that break real deployments and that almost nothing tests. Note that each is
expressed as a conjunction: completing the task is not sufficient. A long-horizon task that finishes
without compaction ever firing did not test compaction, and passing it would be a lie about coverage.

## The mutation check

Here is the uncomfortable question: how do you know your eval suite tests what it claims?

A test suite that passes whether or not the feature works is decoration. So the acceptance criterion
for the differentiating tasks is a deliberate sabotage:

- Disable compaction → the compaction tasks must **fail**
- Disable the permission policy → the permissioning tasks must **fail**
- Break checkpointing → the recovery tasks must **fail**

If a guard can be removed and the suite stays green, that guard was never load-bearing and the tests
were measuring something else.

Almost nobody does this, and it is the cheapest way to find out that a test you trust is inert. Try it
on your own suite once; the result is usually informative and rarely comfortable.

*(Planned for M3.)*

## Determinism

An eval suite that returns different answers on identical input cannot support a claim. The
acceptance criterion for M2 is that the same suite, run twice against the same model and seed,
produces an identical pass/fail vector — with a flake rate under 5% across three consecutive runs.

The mechanisms:

- **One disposable container per task.** No state leaks between tasks and no ordering dependence.
- **Network off by default.** The most common source of hidden non-determinism.
- **Pinned model versions.** `gpt-4o` is not a fixed artifact over time.
- **Fixed seeds** where the provider supports them.

## Why the sandbox is one container per task

Decision **D7**. Three reasons, in order of importance:

1. **Determinism** — a shared sandbox means task 7 sees whatever task 6 left behind.
2. **Parallelism** — independent containers run at once; the suite finishes in minutes.
3. **It is the only reason it is sane to hand an agent a shell.** Everything in
   [Tools and the sandbox](tools-and-sandbox.md) and [Permissions](permissions.md) is defence in
   depth *behind* this. The container is the actual boundary.

## The benchmark

The point of a deterministic, end-state-graded suite is that you can point it at different models and
compare the results honestly. Planned output columns:

> provider · model · pass rate · median steps · input/output tokens · USD per task · p95 latency ·
> compaction events per task

Pass rate alone hides too much. A model that passes 80% of tasks in 6 steps for $0.02 and a model that
passes 80% in 34 steps for $1.40 are not the same product, and only one of them is deployable at
volume.

One result is worth stating in advance, because it is a finding rather than a failure: if a
self-hosted 14B model passes 6 of 20 tasks at a fortieth of the cost, that is a *more* interesting
number than parity. Publishing it is the point.
