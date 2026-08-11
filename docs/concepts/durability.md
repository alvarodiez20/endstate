# Durability and resume

The process dies at step 14 of 25. Fourteen steps of file edits are already on disk. What has to be
true for `--resume` to be correct?

This is the least glamorous concept in agent engineering and the one with the sharpest edges.

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

!!! danger "Known gap at v0.0.1"

    The loop does not fully implement D8 yet. The assistant message is checkpointed *before* its
    tool calls execute
    ([`loop.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/loop.py)),
    so a crash between the provider response and tool execution leaves a session whose last message
    contains `tool_calls` with no matching `tool_results` — malformed under both the Anthropic and
    OpenAI contracts.

    A second gap: results for a batch of tool calls are recorded as a single message *after the whole
    batch*. Crash after tool 2 of 3 and the session has no record that tools 1 and 2 already ran,
    while their side effects are on disk.

    Closing both is M1 of the
    [engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md). Until then,
    `--resume` reliably restores conversation history but does not guarantee end-state equivalence
    with an uninterrupted run.

    These docs would be worth less if they described the intended design as though it were finished.

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
makes this expressible. It is also what the [recovery eval category](evaluation.md) grades on.

*(Both planned for M1. `tree_hash()` does not exist yet.)*

Note that this is the same shape as the whole project's thesis: the assertion is about the end state,
not about what was said.

## Resume is not the same as continue

A subtlety worth naming, because the CLI surface makes it easy to miss.

Restoring a session's message history is easy. But an interrupted run needs to *continue from where
it stopped* — with pending tool calls resolved and no new instruction. Today `--resume` loads the
session and then takes a new prompt, which is "carry on with this conversation," a genuinely useful
thing, but not the same as "finish what you were doing."

The distinction only shows up under a real crash, which is why the randomised kill-point test is the
acceptance criterion for M1 rather than a nice-to-have.

## What to check in your own agent

- Is there any state in memory that is not on disk? What is lost if you `kill -9` right now?
- Do you persist intentions or outcomes?
- If a tool is not idempotent, can a resume run it twice?
- Do you verify resume by comparing *end states*, or by eyeballing that it didn't crash?
