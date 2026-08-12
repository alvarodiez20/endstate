# How agents actually work

This section is the part of these docs worth reading even if you never run `endstate`.

An agent, stripped of marketing, is a loop that calls a language model, notices the model asked for
something, does that thing, and hands back the result. That description is accurate and nearly
useless — it fits in a tweet and it hides every decision that determines whether the system works on
day 90.

The useful version is the list of things that break.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../assets/diagrams/concepts-map.html"
          height="800" loading="lazy" title="Map of the eight in-loop concepts and how they connect"></iframe>
</div>

The map covers part one only — each of those eight attaches to a specific step of the loop, which is
what the diagram shows. The five in part two do not attach at a single point, which is the reason
they are a separate list rather than nine through thirteen on the same one.

## Part one: the eight problems in the loop

Each page below takes one problem, explains why the obvious solution fails, and shows the code that
handles it in this harness. Read them in order the first time; they build on each other.

| # | Page | The problem it solves |
| --- | --- | --- |
| 1 | [The loop](the-loop.md) | What the control flow actually is, and where every hard decision attaches to it |
| 2 | [Messages and providers](messages-and-providers.md) | Vendors disagree about what a conversation is. The loop must not care. |
| 3 | [Tools and the sandbox](tools-and-sandbox.md) | You are giving a probabilistic system a filesystem. Where is the fence? |
| 4 | [Permissions and refusal](permissions.md) | An agent that cannot be stopped is not deployable |
| 5 | [Context and compaction](context-and-compaction.md) | The conversation outgrows the window. Something must be thrown away. |
| 6 | [Durability and resume](durability.md) | The process dies at step 14 of 25. Side effects are already on disk. |
| 7 | [Cost and telemetry](cost-and-telemetry.md) | "Is it expensive?" should have a number, not a shrug |
| 8 | [Evaluation](evaluation.md) | How do you know any of the above works? |

## Part two: five problems around the loop

The eight above are the ones this harness solves, and each page points at the code. The five below
are ones it deliberately does **not** solve — and that any agent you actually deploy will hit anyway.

They are here for two reasons. Some of them explain assumptions the first eight quietly depend on:
"six tools, hardcoded" is doing more work in this design than it looks like. And the last one is the
threat model that all of the others feed into, which is a bad thing to leave implicit.

| # | Page | The problem it describes | Status here |
| --- | --- | --- | --- |
| 9 | [Skills](skills.md) | Procedural knowledge does not fit in a system prompt and cannot go in a tool description | Not built |
| 10 | [MCP and tool discovery](mcp-and-tool-discovery.md) | Tools arrive at runtime, from strangers, by the hundred | Not built |
| 11 | [Memory](memory.md) | Compaction decides what to forget. Something has to decide what to keep. | Not built |
| 12 | [Subagents and orchestration](subagents.md) | One context window is sometimes the wrong unit of work — and usually the right one | [Non-goal](../design/non-goals.md) |
| 13 | [Prompt injection and the lethal trifecta](prompt-injection.md) | Every capability above is also an ingredient in the same attack | Partially mitigated |

Read part two after part one, or skip to [prompt injection](prompt-injection.md) if you only have
time for one page — it is the one with consequences.

## The one idea underneath all of them

An agent's output is not its text. **An agent's output is the change it made to the world.**

Once you take that seriously, a lot follows. The transcript stops being the thing you evaluate and
becomes a debugging artifact. Refusal becomes a positive outcome that a test can assert on rather
than a failure to produce output. A crash mid-run becomes a question about the filesystem, not about
the conversation. Cost becomes a property of the work done rather than a line in a dashboard.

It also explains why this project is named after the concept rather than after the loop. The loop is
the boring part. Most of the difficulty is in what the loop is allowed to touch, what it remembers,
what it persists, and how you check afterwards that it did the right thing.

!!! note "A note on honesty in these docs"

    The harness is at v0.0.1 and the eval runner is not built yet. Where a page describes something
    that exists, it links to the source file. Where it describes something planned, it says
    **planned** and points at the milestone in the
    [engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md). No page will
    tell you a thing works because it is going to work later.

    The part two pages describe things this harness does **not** implement at all. Each opens with a
    status box saying so, and cites its sources at the bottom, because there is no source file to
    point at.
