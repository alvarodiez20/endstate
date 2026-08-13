# Durability and resume

The process dies at step 14 of 25. Fourteen steps of file edits are already on disk. What has to be
true for `--resume` to be correct?

This is the least glamorous concept in agent engineering and the one with the sharpest edges.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/durability.html"
          height="605" loading="lazy" title="Checkpointing and a correct resume"></iframe>
</div>

## Why it matters more than it sounds

Agent runs are long. Minutes to hours, across dozens of model calls. Over that window: laptops sleep,
CI runners get preempted, containers hit memory limits, someone hits Ctrl-C, a provider returns a 500
on step 9 of 25.

Without durability the answer is "start again," which throws away real work and real money. With
*naive* durability the answer is worse: you replay from a checkpoint and re-apply side effects that
already happened.

## The storage decision

SQLite. Not Postgres, not Redis.

> A harness that needs infrastructure to remember what it was doing is a harness nobody will run
> locally.

Checkpointing is a durability problem, not a scale problem. One writer, small records, and a strict
requirement that a write survives the process dying immediately afterwards. That is precisely what
SQLite is for, and requiring `docker compose up` before anyone can try your tool is a real adoption
cost paid for nothing.

Source:
[`agent/session.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/session.py).

## Append and checkpoint are one operation

```python
def append(self, message: Message) -> None:
    """Append and checkpoint in one operation. There is no uncheckpointed state."""
    self.messages.append(message)
    self.store._append(self.id, len(self.messages) - 1, message)
```

There is no `save()` to forget to call. You cannot have in-memory state that has not been persisted,
because the only way to add a message also writes it. The class of bug where a crash loses the last
few steps because someone batched the flush is designed out rather than tested for.

Messages are keyed `(session_id, step)` with `INSERT OR REPLACE`, so writing the same step twice is
idempotent.

## The ordering rule that matters

This is decision **D8** in the project's
[decision log](../design/decisions.md), and it is the crux of the whole page:

> **Checkpoint *after* the tool result, never before.**

Consider a step where the model asks to run `pytest`, and the process is killed mid-step.

**Checkpoint before the tool runs:** on resume the session says "we were about to run pytest." Did it
run? Unknowable. If it ran and wrote a coverage file, running it again is harmless. If the tool was
`git commit`, running it again gives you two commits. The harness cannot tell these apart, because
the record was written before the outcome existed.

**Checkpoint after the tool result:** on resume, a completed step is in the log *with* its outcome,
and an incomplete step is absent entirely. Either the side effect happened and is recorded, or it did
not happen and there is nothing to undo. The ambiguous middle is gone.

The general form: **never persist an intention as though it were a fact.** Persist outcomes.

## How the harness applies it

Two mechanisms, both visible in
[`loop.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/loop.py).

**Results are persisted per call, not per batch.** A model can request several tools in one turn.
Writing all their results at the end would mean a crash after the second of three left no record
that the first two had run — while their side effects were already on disk. Instead each result is
written as it lands, rewriting the tool message at the same step. `SessionStore` keys messages on
`(session_id, step)` with `INSERT OR REPLACE`, so this needs no extra rows and no schema change.

**Resume reconciles outstanding calls.** The assistant message is persisted *before* its tools run —
necessarily, because it is the only record of what was requested. That leaves a transient window
where the history contains `tool_calls` with no matching `tool_results`, which is malformed under
both the Anthropic and OpenAI contracts. So resume repairs it before doing anything else: it finds
calls with no recorded result, executes exactly those, and only then continues the loop.

```python
def _pending(self, messages):
    last = messages[-1]
    if last.role == "assistant" and last.tool_calls:
        return list(last.tool_calls), False          # crashed before any tool ran
    if last.role == "tool":
        requested = messages[-2]
        done = {r.call_id for r in last.tool_results}
        return [c for c in requested.tool_calls if c.id not in done], True   # crashed mid-batch
    return [], False
```

Note that `run()` settles pending calls *before* appending a new user message. Adding the
instruction first would bury the unfinished batch mid-history, where nothing would ever complete it.

!!! note "The window that cannot be closed"

    A crash *inside* a tool call — after the side effect, before any record of it — is irreducible
    without transactional side effects. The harness narrows the ambiguity from a whole batch to a
    single call, and then re-runs that call on resume.

    That converges exactly when the tool is idempotent. `write` is; a tool that appends, or one that
    runs `git commit`, is not. The test suite covers this case explicitly rather than pretending it
    away.

## How you prove resume works

The claim "a killed run resumes to the same end state" is only worth anything if it is checked
mechanically, and the check cannot look at the transcript — two runs can reach an identical
filesystem via different conversations, and an identical conversation can leave different files.

So the test compares filesystems:

1. Run the task to completion. Hash the resulting file tree.
2. Run it again, killing the process at step *k*.
3. Resume from the session.
4. Hash the tree. Assert it equals the first hash.
5. Repeat for randomised values of *k*.

`RunResult.tree_hash()` — a deterministic hash of the sandbox after a run — is the primitive that
makes this expressible. It ignores mtimes and inode numbers, records the executable bit, and hashes
symlinks as their target text rather than following them. It is also what the
[recovery eval category](evaluation.md) grades on.

`tests/test_recovery.py` runs exactly the procedure above at every kill point in a six-call run, in
both variants: killed *before* the side effect, and killed *after* it.

Note that this is the same shape as the whole project's thesis: the assertion is about the end state,
not about what was said.

### And how you know the test is real

Both guards were checked by removing them, per
[the mutation argument](evaluation.md#the-mutation-check):

| Guard removed | Result |
| --- | --- |
| Resume reconciliation | 11 of 20 tests fail, including every kill point |
| Per-call persistence | 1 test fails — the one that inspects the session mid-batch |

The second row is worth dwelling on. Batch-only persistence is *invisible* in the end state when
tools are idempotent, because losing the record of a completed call just means resume re-runs it and
lands in the same place. It shows up only in the recorded history — and it would show up in the end
state the moment a non-idempotent tool was involved.

## Where this sits in the wider durable-execution world

None of this is new. It is workflow engineering, rediscovered by agent builders, and the vocabulary
already exists — which is useful, because it makes the gaps easier to name.

The distinction that matters is **checkpointing versus durable execution**, and the two get conflated
constantly:

| | Checkpointing | Durable execution |
| --- | --- | --- |
| What is saved | A state snapshot after each step | A full event history of every step |
| How recovery works | Load the snapshot, continue | Replay the history to rebuild in-memory state, then continue |
| Re-execution on recovery | Anything after the last checkpoint runs again | Completed steps return cached results and never re-run |
| Who does it | LangGraph, CrewAI, most agent frameworks | Temporal, Restate, DBOS, Inngest, Cloudflare Workflows |

The engines in the right column give exactly-once semantics for completed steps by caching results in
the event history. The frameworks in the left column do not — after a crash, nodes past the
checkpoint re-execute, which makes idempotency mandatory for anything with a side effect rather than
merely desirable.

This harness is in the left column and knows it. The D8 ordering rule above is the poor-man's version
of the same insight the engines encode: **a completed step must be recorded with its outcome, or the
system cannot tell "done" from "about to."** Getting that right buys most of the benefit at a
fraction of the operational cost, and requiring `docker compose up` before anyone can try a CLI tool
is not a trade this project is willing to make.

What it does *not* buy is the last mile. Durable-execution engines wrap side effects in a recorded
activity so the result is cached; here, a re-run tool genuinely re-runs. The standard mitigation at
the agent layer is an **idempotency key** per tool call — the tool checks whether that key has
already been applied before doing anything. Nothing in this harness does that today, and it is what a
`git commit` tool would need before resume could be called correct in general rather than correct for
idempotent tools.

## Resume is not the same as continue

A subtlety worth naming, because the CLI surface makes it easy to miss.

Restoring a session's message history is easy. Finishing an interrupted run is not: it means
resolving pending tool calls and carrying on *without* a new instruction. Both are useful, and
`endstate run` distinguishes them by whether you pass a prompt:

```bash
endstate run --resume <session-id>              # finish what it was doing
```

```bash
endstate run "now add a test" --resume <session-id>   # continue the conversation
```

The second form settles any outstanding calls first, then takes the new instruction.

!!! note "Durability is not memory"

    Both write to disk and both survive process death, which is why they get conflated. A checkpoint
    is a verbatim transcript written by the harness so *this* run can continue; a memory is a curated
    claim written by the agent so a *future* run knows something. The second can be wrong in a way
    the first cannot. See [Memory](memory.md).

## What to check in your own agent

- Is there any state in memory that is not on disk? What is lost if you `kill -9` right now?
- Do you persist intentions or outcomes?
- If a tool is not idempotent, can a resume run it twice?
- Do you verify resume by comparing *end states*, or by eyeballing that it didn't crash?

## Open problems

**A filesystem has no transactions.** The window inside a tool call — after the side effect, before
any record of it — is irreducible without transactional side effects, and a shell does not offer
them. Idempotency keys narrow it; compensating actions ("undo the commit") are the other standard
answer and are unreliable in exactly the cases you need them. Nobody has a clean solution for agents
holding a shell.

**Resume across a changed world is undefined.** Every guarantee on this page assumes the tool set,
the model and the environment are unchanged between crash and resume. Resume a week-old session
against a re-pinned model and the history is valid while the behaviour is not. No harness known to us
records the provider, model version and tool schemas alongside the checkpoint and refuses to resume
across a mismatch — which is probably what correctness requires.

**Non-idempotent tools are declared, not solved.** Tools now carry an `idempotent` flag, and the
resume path reads it: an outstanding call to a tool that declares itself non-idempotent — `bash`,
for one — is *not* replayed. It is answered with an error saying the outcome is unknown, so the
conversation stays well-formed and the model checks the state instead of the harness silently
committing twice.

That is a real mechanism where there was none, and it is still only half the problem. The flag is a
claim the tool author makes, and nothing verifies it. Refusing to replay is the safe default, but it
is not *correct*: a run that died before its `git commit` ran leaves work undone, and the harness
cannot tell that case from the one where it ran. Distinguishing them needs idempotency keys —
recording an identifier with the side effect so the tool can ask "did I already do this?" — which
is where the durable-execution engines in the table above start.

**Long-running agents change the shape of the problem.** Everything above assumes a run that starts,
crashes and resumes. Scheduled agents and always-on agents have no such boundary; their state
directory *is* the durable artifact, and it accumulates indefinitely. At that point durability starts
overlapping with [memory](memory.md) and inherits its problems, including
[poisoning that survives every restart](prompt-injection.md).
