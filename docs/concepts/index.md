# How agents actually work

This section is the part of these docs worth reading even if you never run `endstate`.

An agent, stripped of marketing, is a loop that calls a language model, notices the model asked for
something, does that thing, and hands back the result. That description is accurate and nearly
useless — it fits in a tweet and it hides every decision that determines whether the system works on
day 90.

The useful version is the list of things that break.

## The eight problems

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
