# Resuming a run

Every run is a session, checkpointed to SQLite after each step. Nothing needs to be enabled.

## List sessions

```bash
endstate sessions
```

Newest first:

```
a3f9c211d4e0
7b1e08cc39a2
```

Sessions live in `.endstate/sessions.sqlite3`, relative to where you invoke the CLI. It is an
ordinary SQLite file — open it with any client if you want to read the raw message log.

## Resume

```bash
endstate run "continue" --resume a3f9c211d4e0 --workdir /tmp/endstate-demo
```

The stored history is loaded, your new prompt is appended, and the run continues with full knowledge
of what happened before.

Pass the same `--workdir` you used originally. The session stores the conversation, not the
filesystem — point it somewhere else and the agent will be reasoning about files that are not there.

## What this is good for

**Continuing a conversation.** The run finished, you want a follow-up change with the context intact.

**Picking up after an interruption.** You hit Ctrl-C, or the process died. Every completed step is on
disk; you keep the work rather than paying for it twice.

**Inspecting what happened.** The session is a queryable record of every message, including tool calls
and their results.

## The honest limitation

!!! warning "Resume restores the conversation, not guaranteed end-state equivalence"

    At v0.0.1, `--resume` reliably restores message history. It does **not** yet guarantee that a
    killed-and-resumed run reaches the same end state as an uninterrupted one.

    The gap is in checkpoint ordering: an assistant message is persisted *before* its tool calls run,
    so a crash in that window leaves a session recording an intention with no recorded outcome. The
    detail is in [Durability and resume](../concepts/durability.md#the-ordering-rule-that-matters).

    Closing it — plus `tree_hash()` and a randomised kill-point test that proves it — is M1 of the
    [engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md).

In practice: resuming after **Ctrl-C between steps** is fine, which is the common case. Resuming after
a crash *during* a tool call may leave the agent unaware of a side effect that already landed. If the
tool was `git commit` or anything else non-idempotent, check the state before continuing.

## Why sessions are SQLite

Short version: checkpointing is a durability problem, not a scale problem, and a harness that needs
`docker compose up` before it can remember anything is a harness nobody runs locally.

Longer version, including why `append()` and "checkpoint" are deliberately the same operation:
[Durability and resume](../concepts/durability.md).

## Next

You have run the harness. The interesting part is why it is built this way —
[How agents actually work](../concepts/index.md).
