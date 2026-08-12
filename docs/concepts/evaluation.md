# Evaluation

This is the page the project exists for. Everything before it is harness; this is the argument.

!!! info "Status"

    The eval runner is **planned for v0.1.0** (M2 in the
    [engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md)). The design below
    is settled and the interfaces are specified. The code is not written yet, and this page says so
    rather than describing it in the present tense.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/evaluation.html"
          height="605" loading="lazy" title="Grading the end state instead of the output"></iframe>
</div>

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

## The end state can be gamed too

Grading the sandbox removes one failure mode. It does not make the grader unfalsifiable, and it is
worth being precise about what it actually buys.

Look again at the grader from above:

```python
result = sandbox.run("pytest -q")
if result.exit_code != 0:
    return Verdict.fail("test suite still red")
```

An agent that edits `tests/` until they pass satisfies that grader completely. So does one that adds
`@pytest.mark.skip`, or special-cases the failing input, or hardcodes the expected value. This is
**reward hacking**, and it is not exotic behaviour in an adversarial sense — it is what optimising
against a checkable target looks like when a cheaper path exists. Anthropic's own model cards track
it as a measured rate on coding tasks rather than as an anomaly.

The end-state framing helps here, but only because a filesystem supports assertions a transcript
cannot. The graders have to actually make them:

| Hack | The assertion that catches it |
| --- | --- |
| Edited the tests | Test files' hashes are unchanged from the task fixture |
| Skipped the test | No new skip/xfail markers in the diff |
| Special-cased the input | Held-out tests, not shipped in the sandbox, also pass |
| Deleted something inconvenient | Tree hash differs only at the paths the task permits |

Three of those four are properties of the file tree, which is the argument for this design. But they
are properties someone has to *write down*. "Grade the end state" is a necessary condition for a
trustworthy eval, not a sufficient one, and a grader that only runs the test suite has swapped a
fluency exploit for a test-editing exploit.

## Contamination is a property of the harness, not only the dataset

Training contamination is the familiar worry: the benchmark was public, the model has seen it. It is
real — one 2025 study found models roughly **3× better** at locating relevant files on SWE-bench
Verified than on comparable newer suites, and **6× better** at identifying the specific edited files,
in a setup constructed so the task should be
[close to impossible without prior exposure](https://arxiv.org/abs/2512.10218).

The less familiar and more actionable worry is **runtime** contamination: the answer is reachable
*during the run*. Cursor had an auditor examine 731 agent trajectories on SWE-bench Pro — blind to whether each run
passed — and found that **63% of the successful resolutions had retrieved the fix rather than
derived it**: 57% by finding the merged PR or fixed source on the public web, 9% by mining the
bundled `.git` history for the future commit. Sealing both channels moved the numbers a
long way:

| Model | Standard harness | Sealed history + no egress |
| --- | --- | --- |
| Opus 4.8 Max | 87.1% | 73.0% |
| Composer 2.5 | 74.7% | 54.0% |

Source: [Reward hacking is swamping model intelligence gains](https://cursor.com/blog/reward-hacking-coding-benchmarks).
Notably the gap was under a point for Opus 4.6 and 14.1 points for Opus 4.8 Max on the same suite —
the behaviour scales with capability, so a harness that was fine last year is not necessarily fine
now. It is not uniform across vendors, though: Cursor reports the GPT models in their run did not
show the same escalation.

Two of the three controls this implies are already decisions here — **one disposable container per
task** and **network off by default** — and this is the strongest external argument for both. They
were justified above on determinism grounds; they turn out to be contamination controls as well.

The third is not, and should be: **strip `.git` history from the task fixture and restore it only at
scoring time.** A task built from a real repository ships the answer inside it. Nothing in the
current design prevents an agent from running `git log`.

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

## Open problems

**Eval awareness undermines construct validity.** Models increasingly infer that they are being
evaluated, and behave differently when they do. Cursor documents an agent that failed to reproduce a
2019 `jq` bug — because the image was built after the fix — concluded the issue was already solved,
and went looking for the patch instead of deriving it. Anthropic has documented a model identifying
the benchmark it was running on in order to decrypt the answer key. Sealing git history and
restricting egress does not touch this: it removes the channels, not the inference. Nobody knows how
to build an eval that stays valid once the subject knows it is an eval.

**Held-out tests are the standard answer and they leak.** Hiding the real tests defeats
special-casing right up until the agent finds a mirror of the benchmark, which has happened. The only
robust version is a benchmark built from material that was never public — which is expensive, is not
shareable, and therefore cannot be a community benchmark. The properties "trustworthy" and "public"
are close to being in tension.

**The mutation check has no theory.** Disabling a guard and requiring the tests to fail is the best
idea on this page and it is a spot check, not a coverage measure. It tells you a specific guard is
load-bearing for a specific task. It cannot tell you which guards you forgot to write a task for.
Mutation testing has decades of literature for ordinary code; none of it has been adapted to agent
harnesses.

**Determinism is aspirational.** "Same suite, same model, same seed, identical pass/fail vector" is
the acceptance criterion, and providers do not offer bit-identical outputs even at temperature 0.
What is achievable is a low flake rate — the 5% target — which makes every result a distribution and
every comparison a statistical claim on a sample of twenty tasks. Twenty tasks is a small sample, and
the honest version of any headline number carries an interval rather than a point.

**Pass rate is the wrong summary and there is no agreed replacement.** A single run per task
conflates capability with luck; `pass@k` rewards a model that is right occasionally; `pass^k` — all
*k* attempts succeed — is closer to what deployment requires and is rarely reported because it looks
bad. This project's answer is to publish steps, tokens, cost and compaction events alongside the
rate, which is more informative and still not a summary statistic anyone has agreed on.
