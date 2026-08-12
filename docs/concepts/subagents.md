# Subagents and orchestration

The fastest way to make an agent look smarter is to make several of them. It is also the fastest way
to turn one debuggable failure into five correlated ones, and it costs several times as much.

Both of those are true at once, which is why this page is mostly about when *not* to.

!!! info "Status"

    Multi-agent orchestration is an explicit [non-goal](../design/non-goals.md) of this project. The
    reasoning is on that page and the short version is here: the failure modes this harness is about
    — compaction, permissioning, recovery — are unsolved in the single-agent case, and a second agent
    does not solve them. This page is here so that the non-goal is an informed decision rather than
    an omission.

## The problem it actually solves

Not "the task is complicated." Context.

A research task that touches forty sources will read a few hundred thousand tokens to produce a
two-page answer. Nearly all of that reading is *intermediate* — dead ends, near-misses, pages that
turned out to be irrelevant. Keep it in one context window and you pay for it on every subsequent
step and you [degrade the model's attention](context-and-compaction.md) on the part that matters.

A subagent is a way to spend a hundred thousand tokens somewhere the main agent will never see them.

## The shape: orchestrator and workers

```
lead agent
  ├── plans, writes the plan to memory
  ├── spawns subagent A ──→ own context window, own tools ──→ returns ~1,500 tokens
  ├── spawns subagent B ──→ own context window, own tools ──→ returns ~1,500 tokens
  ├── spawns subagent C ──→ own context window, own tools ──→ returns ~1,500 tokens
  └── synthesises, decides whether to spawn more
```

Each worker explores extensively and returns a distilled summary — Anthropic puts the typical return
at 1,000–2,000 tokens from a subagent that may have consumed tens of thousands. The lead agent's
context stays small because it only ever sees conclusions.

That asymmetry is the entire value proposition. **A subagent is a lossy compressor with a tool
budget.**

## The number that should govern the decision

Anthropic's multi-agent research system — Claude Opus 4 as the lead agent, Claude Sonnet 4 as the
subagents — beat single-agent Claude Opus 4 by **90.2%** on their internal research eval. On
BrowseComp, token usage alone explained **80% of the performance variance** between systems.

Read those two figures together rather than separately. The architecture works, and a large part of
why it works is that it spends much more. The multiplier is worth getting right, because it is
routinely quoted wrong: Anthropic's figure is that agents use about **4× the tokens of a chat**, and
multi-agent systems about **15×**. Against a *single agent* — the thing you would otherwise
build — that is roughly 4× the spend, and Anthropic's later guidance puts the same comparison at
3–10×.

So the honest question before adopting it is not "is this better?" but "is this better than spending
four times as much on one agent?" — a comparison that is rarely run and often uncomfortable.

## When it works and when it does not

The discriminator is whether the task decomposes into *independent* strands.

| Fits | Does not fit |
| --- | --- |
| Breadth-first search: "find the board members of every S&P 500 IT company" — each company is a separate, self-contained lookup | Coding: change a function signature and every caller's context changes |
| Independent evaluation of many candidates | Anything where agents must share the same evolving state |
| Parallel investigation of unrelated hypotheses | Tightly sequenced work where step *n+1* depends on the outcome of step *n* |

Domains that require all agents to share context, or that have many dependencies between agents, are
a bad fit today. Coding is the canonical bad fit, which is worth noticing given how much multi-agent
tooling is aimed at coding.

## The failure modes are new ones

Anthropic's own account of moving this to production is candid about early behaviour: agents spawning
*fifty* subagents for simple queries, scouring the web endlessly for sources that did not exist, and
distracting each other with excessive updates. Add the structural problems and you get a list that
has no single-agent equivalent:

- **Delegation is a prompt-engineering problem in itself.** A vague instruction to a subagent
  produces a confident, irrelevant summary — and the lead agent has no way to tell, because it never
  saw the work.
- **Errors compound silently.** Compression is lossy by design. A subagent that misread its source
  returns a clean, wrong paragraph, and the lead agent treats it as a finding.
- **Cost is superlinear and hard to cap.** `max_steps` bounds one loop. Bounding a tree of loops
  requires a budget that is shared, which means it is contended.
- **Debugging loses the trace.** The single most useful property of a one-loop agent is that the
  transcript is a total order. Fan out and it is not.

## The one pattern worth taking without the architecture

Strip away the orchestration and what remains is the **context firewall**: run a bounded piece of
work somewhere its intermediate output cannot pollute the main context, and return only the
conclusion.

You do not need a second agent for that. A `bash` command that greps a large log and prints three
lines is a context firewall. So is
[code execution against MCP tools](mcp-and-tool-discovery.md), which filters 10,000 rows down to
five before the model ever sees them. So is a script bundled in a [skill](skills.md).

Most of the reliability gain attributed to multi-agent systems is available inside a single agent,
at 1× the token cost, by being disciplined about what is allowed into the context window. Reach for
the full topology only when the task is provably breadth-first.

## What it means for permissions and injection

Two consequences that are easy to miss, and both of them are security-relevant.

**Permission checks must live in the harness, not in the lead agent.** If a subagent gets its own
loop, it gets its own tool calls, and a [policy](permissions.md) enforced by prompting the lead agent
is no policy at all. Deny-by-default has to hold at the point of execution for every loop.

**Compression launders provenance.** A subagent that read an attacker-controlled web page returns a
tidy summary with no marker saying so. The lead agent then acts on text that originated with an
attacker, having lost every signal that it was untrusted. Fan-out makes the
[lethal trifecta](prompt-injection.md) harder to reason about, because the three properties may be
distributed across different agents while the *system* still has all three.

## What to check before adding a second agent

- Can the task be split into strands that genuinely do not need to see each other's work? If not,
  stop here.
- Would four times the budget on one agent do as well? Have you tried?
- What bounds the total number of subagents, and where is that enforced?
- When a subagent returns something wrong, how would you find out?
- Does every subagent's tool call pass the same permission policy as the lead's?

## Sources

- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — Anthropic, June 2025
- [When to use multi-agent systems (and when not to)](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) — Anthropic
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, September 2025
