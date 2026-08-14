# Decision log

Recorded so the reasoning survives contact with the future, and so that anyone reading the code can
find out why it looks like this instead of guessing.

Each entry names the alternative that was rejected, because a decision with no rejected
alternative is not a decision.

The diagram covers D1–D8, the decisions that shaped the harness. D9–D12 came out of building the
eval runner and are recorded below it.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/decisions.html"
          height="535" loading="lazy"
          title="The core design decisions and their rejected alternatives"></iframe>
</div>

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

## D9 — The grader signature is checked, not just documented

**Rejected:** a convention that graders take only the sandbox.

`grade(sandbox: Sandbox) -> Verdict` is the contract the project turns on, so resolving a grader
inspects its signature and refuses one whose first parameter is not a positional `sandbox`, or that
takes `messages`, `transcript`, `result` or `history`.

A grader that *can* read the transcript eventually gets written to check the transcript — someone
adds "and it mentioned running the tests," because that is easier than checking that they ran.
Conventions erode. Signatures do not.

[Evaluation](../concepts/evaluation.md#the-contract-is-enforced-by-the-signature).

## D10 — Run-level assertions live in the task manifest, not in the grader

**Rejected:** passing the `RunResult` to graders that need it.

"Compaction fired at least once" is not a property of the filesystem, and neither is "the policy
refused something" — an agent that ignored the request leaves the same tree as one the harness
stopped. Three of the four differentiating categories need an assertion of that kind.

Handing the grader the run result would answer it and undo D9 in the same move. Instead the task
declares what the run must have done and the **runner** checks it, conjoined with the grader's
verdict. What keeps this from being the same loophole by another name is that `RunRequirements` is a
closed set of typed counters the harness recorded itself, with unknown keys refused at load time —
so a manifest naming `final_text` is an error rather than a field that is silently ignored.

[What the sandbox cannot answer](../concepts/evaluation.md#what-the-sandbox-cannot-answer).

## D11 — Seal the end state before grading stages anything into it

**Rejected:** hashing the sandbox lazily, whenever a grader asks.

Held-out tests are files. Copying them in before the tree is hashed would mean every assertion about
the file tree was an assertion about a tree the grader itself had just modified. So the runner
freezes the end state the moment the agent stops — hash and snapshot — and serves every later
question from that, then stages the held-out tests and grades.

## D12 — A non-idempotent tool call is not replayed on resume

**Rejected:** re-running every outstanding call, and trusting tools to be idempotent.

A crash inside a tool call — after the side effect, before any record of it — leaves the harness
unable to tell "done" from "about to". For `write` that is harmless: re-running converges. For a
shell command it is a second side effect.

Tools now declare `idempotent`, and resume reads it: an outstanding call to one that says False is
answered "outcome unknown, check the state" rather than repeated. That is safe rather than correct —
a run that died before its `git commit` leaves work undone and the harness cannot tell which case it
is in. Closing that needs idempotency keys, which this harness does not have.

[Durability and resume](../concepts/durability.md#open-problems).

---

## On writing these down

The value is less in the decisions than in the rejected alternatives. Six months on, the question is
never "what did we do" — the code answers that. It is "did we consider X," and without a log the
answer is a shrug and a re-litigation.

The full engineering plan, including milestones, risk register and cut order, lives in
[PLAN.md](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md).
