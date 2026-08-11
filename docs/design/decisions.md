# Decision log

Recorded so the reasoning survives contact with the future, and so that anyone reading the code can
find out why it looks like this instead of guessing.

Each row names the alternative that was rejected, because a decision with no rejected alternative is
not a decision.

## D1 — Build the loop from primitives

**Rejected:** LangGraph, or any agent framework.

The harness *is* the artifact. A framework hides exactly the parts worth examining — where the context
budget is enforced, what happens when a tool is denied, what is persisted before a step can fail —
and building on one would demote the project to "a LangGraph demo."

There is a real cost: things a framework gives you free are hand-written here, and the harness has
fewer features than any mature framework. That is the trade. See [The loop](../concepts/the-loop.md).

## D2 — Deterministic graders, no LLM judge in the primary path

**Rejected:** LLM-as-judge.

Credibility and reproducibility. A judge is another non-deterministic system to debug, and its
failures correlate with the agent's. A grader that runs `pytest` and checks the exit code is harder to
write and impossible to argue with.

[Evaluation](../concepts/evaluation.md) has the long version.

## D3 — SQLite for sessions

**Rejected:** Postgres, Redis.

Checkpointing is a durability problem, not a scale problem: one writer, small records, must survive
the process dying. Requiring infrastructure before anyone can try the tool is an adoption cost paid
for nothing.

[Durability](../concepts/durability.md).

## D4 — Prices are user-supplied data; an unknown price raises

**Rejected:** a hardcoded price table, or returning zero for unknown models.

Prices change often and vary by region and contract. A wrong cost number is worse than a missing one —
`$0.00` reads as "free," not as "unknown," and someone will make a decision on it.

[Cost and telemetry](../concepts/cost-and-telemetry.md).

## D5 — Default-deny permission policy

**Rejected:** default-allow with a deny-list.

The failure modes are asymmetric. A wrongly denied command is an annoyance; a wrongly allowed one is
an incident. A policy that treats them symmetrically is wrong.

[Permissions](../concepts/permissions.md).

## D6 — Heuristic token counter by default

**Rejected:** per-provider tokenisers as a hard dependency.

The harness must work against providers whose tokeniser is not public — including most self-hosted
models. `TokenCounter` is a Protocol, so an exact counter is a one-line swap where it matters.

[Context and compaction](../concepts/context-and-compaction.md).

## D7 — One disposable container per eval task

**Rejected:** a shared sandbox with subprocess isolation.

Determinism, parallelism, and the fact that it is the only reason it is sane to hand an agent a shell.
Everything else in the tool layer is defence in depth behind this boundary.

[Tools and the sandbox](../concepts/tools-and-sandbox.md).

## D8 — Checkpoint *after* the tool result

**Rejected:** checkpointing before the step.

Re-applying an already-applied side effect on resume is the classic bug. Persist outcomes, never
intentions.

Applied at per-call granularity rather than per batch, with resume reconciling anything left
outstanding. See [how the harness applies it](../concepts/durability.md#how-the-harness-applies-it).

---

## On writing these down

The value is less in the decisions than in the rejected alternatives. Six months on, the question is
never "what did we do" — the code answers that. It is "did we consider X," and without a log the
answer is a shrug and a re-litigation.

The full engineering plan, including milestones, risk register and cut order, lives in
[PLAN.md](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md).
