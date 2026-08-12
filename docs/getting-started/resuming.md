# Resuming a run

Every run is a session, checkpointed to SQLite after each step. Nothing needs to be enabled.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/resuming.html"
          height="500" loading="lazy"
          title="The two forms of --resume"></iframe>
</div>

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

Two forms, and the difference matters.

**Finish an interrupted run** — omit the prompt:

```bash
endstate run --resume a3f9c211d4e0 --workdir /tmp/endstate-demo
```

Any tool calls that were requested but never executed are run first, then the agent carries on. No
new instruction is added; it picks up what it was doing.

**Continue the conversation** — pass a prompt:

```bash
endstate run "now add a test for the edge case" --resume a3f9c211d4e0 --workdir /tmp/endstate-demo
```

The stored history is loaded, any outstanding calls are settled, then your prompt is appended and the
run continues with full knowledge of what happened before.

Pass the same `--workdir` you used originally. The session stores the conversation, not the
filesystem — point it somewhere else and the agent will be reasoning about files that are not there.

## What this is good for

**Continuing a conversation.** The run finished, you want a follow-up change with the context intact.

**Picking up after an interruption.** You hit Ctrl-C, or the process died. Every completed step is on
disk; you keep the work rather than paying for it twice.

**Inspecting what happened.** The session is a queryable record of every message, including tool calls
and their results.

## The one case to know about

A killed-and-resumed run reaches the same end state as an uninterrupted one — that is verified at
every kill point in the test suite, by comparing hashes of the sandbox rather than by reading the
transcript.

The exception is narrow and worth knowing:

!!! note "A crash *inside* a tool call"

    If the process dies after a tool's side effect but before anything records it, the only option on
    resume is to run that call again. Nothing can distinguish "it never ran" from "it ran and the
    record was lost" — that would need transactional side effects.

    So resume converges when the tool is idempotent. `write` is: writing the same file twice leaves
    the same bytes. `git commit` is not — you would get two commits.

    In practice, if a run died mid-`bash` and the command was not idempotent, check the state before
    resuming. Everything else — Ctrl-C between steps, a kill mid-batch, a crash before a tool ran —
    resumes exactly.

## Why sessions are SQLite

Short version: checkpointing is a durability problem, not a scale problem, and a harness that needs
`docker compose up` before it can remember anything is a harness nobody runs locally.

Longer version, including why `append()` and "checkpoint" are deliberately the same operation:
[Durability and resume](../concepts/durability.md).

## Next

You have run the harness. The interesting part is why it is built this way —
[How agents actually work](../concepts/index.md).
