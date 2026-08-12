# Non-goals

What this project will not do, written down so the answer is a link rather than an argument.

## Not building

**A web UI.** The output is a report and a table. A UI is a surface to maintain that adds nothing to
the argument.

**A TUI beyond `rich`.** Summary tables and streaming output, no more.

**RAG or vector stores.** Retrieval is a real problem and a different one. The agent reads files with
`grep` and `read`, like a person would. See [Memory](../concepts/memory.md) for why that is a smaller
concession than it sounds.

**Multi-agent orchestration.** A single loop that works is worth more than five that hand work to each
other, and the failure modes covered here — compaction, permissioning, recovery — are unsolved in the
single-agent case. The full argument, including the cases where it *is* the right call, is on
[Subagents and orchestration](../concepts/subagents.md).

**An MCP client.** A fixed, small, auditable tool set is a control variable for the benchmark; if the
catalogue changes between runs, the cost table stops being comparable to itself. See
[MCP and tool discovery](../concepts/mcp-and-tool-discovery.md).

**An IDE plugin.**

**A general-purpose framework.** This is the sharpest one. The moment the goal becomes "support
everyone's use case," every decision in the [log](decisions.md) becomes a configuration option, the
loop grows branches, and the thing that made it worth reading is gone. See D1.

**Beating anyone on a public leaderboard.** The claim is about *what* is measured, not about a score.

## Why write these down

Scope creep into a framework is the highest-likelihood, highest-impact risk in the
[risk register](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md), and it never arrives
announcing itself. It arrives as a reasonable feature request that would only take an afternoon.

A written non-goal converts that conversation from a judgement call into a lookup.

## The cut order

Under time pressure, things get cut in this order — decided in advance, when it is cheap to be
honest:

1. The docs site (the README suffices)
2. The refactor task category
3. The `SummariseMiddle` strategy (`DropOldest` alone still demonstrates budgeting)
4. The third provider (two still make a comparison)
5. Streaming output

!!! note

    You are reading item 1. It got built early because these docs turned out to serve a purpose the
    README cannot: teaching the concepts. That is a change of scope, made deliberately — an
    explanation of why compaction is hard is worth more than an API listing, and it is the same
    material that makes the project legible in 30 seconds.

**Never cut:** the Docker sandbox · end-state graders · the compaction, permissioning and recovery
task categories · the published cost table.

Those four *are* the project. Everything else is packaging.
