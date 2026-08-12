# Skills

A tool is a capability. A skill is knowing when to reach for it and what to do with it. The gap
between those two things is where a surprising share of agent failure lives, and it is not a gap you
can close by adding more tools.

!!! info "Status"

    `endstate` has **no skill loader**, and one is not on the roadmap. This page is here because
    skills are now the standard answer to a problem the harness *does* have — where procedural
    knowledge lives — and because the mechanism is a context-management trick worth understanding
    even if you never write a `SKILL.md`. Where the section describes what this harness does, it
    links to source. Everything else is described as what it is: someone else's design.

## The problem skills solve

Your agent has a `bash` tool. Your organisation has a deployment procedure with eleven steps, four of
which are counter-intuitive and two of which will page someone at 3am if done in the wrong order.

The `bash` tool cannot express that. Neither can a longer tool description, because a tool
description is [sent on every single call](tools-and-sandbox.md) — it is billed on every step of
every run, including the ten thousand runs that have nothing to do with deployment.

So the knowledge goes in the system prompt. Then the next procedure goes in the system prompt. Then
the third. Within a month the system prompt is nine thousand tokens of mostly-irrelevant instructions
that the model reads in full before answering "what time is it," and the ones that matter are buried
in the middle where [attention is worst](context-and-compaction.md).

Every fix for this is a variant of the same idea: **load the instructions only when they are
relevant.**

## What a skill actually is

A directory with a `SKILL.md` file in it. That is the whole format.

```
pdf-processing/
├── SKILL.md          # required: YAML frontmatter + markdown instructions
├── scripts/          # optional: executable code
├── references/       # optional: docs loaded on demand
└── assets/           # optional: templates, schemas, data
```

The frontmatter is where the design lives:

| Field | Required | What it is for |
| --- | --- | --- |
| `name` | Yes | Lowercase, hyphenated, must match the directory name. Max 64 chars. |
| `description` | Yes | What it does **and when to use it**. Max 1024 chars. This is the router — see below. |
| `license` | No | License name, or a reference to a bundled file. |
| `compatibility` | No | Environment requirements: needs `docker`, needs network, needs Python 3.14. Max 500 chars. |
| `metadata` | No | Arbitrary string map, for whatever the client wants to track. |
| `allowed-tools` | No | Space-separated pre-approved tools, e.g. `Bash(git:*) Read`. Experimental. |

Two required fields and a markdown body. The format was published by Anthropic in October 2025 and
released as an [open standard](https://agentskills.io/specification) that December. Claude Code,
Cursor, Codex, Gemini CLI, Copilot and several dozen other products now read the format; the standard
keeps a [client showcase](https://agentskills.io/clients).

## The actual mechanism: three levels of disclosure

This is the part worth stealing, and it has nothing to do with the file format.

| Level | What loads | Roughly | When |
| --- | --- | --- | --- |
| 1 | `name` + `description` of *every* installed skill | ~100 tokens each | At startup, always |
| 2 | The full `SKILL.md` body | <5,000 tokens recommended | When the agent decides the skill applies |
| 3 | `references/`, `scripts/`, `assets/` | Unbounded | Only the specific file the task needs |

Level 1 is a table of contents. Level 2 is a chapter. Level 3 is the appendix you look up once a
year.

Because levels 2 and 3 are read with the agent's own `read` tool from its own filesystem, the amount
of knowledge you can attach to an agent is effectively unbounded while the *fixed* cost stays at a
hundred tokens per skill. A hundred skills cost ten thousand tokens of always-on context and give
access to arbitrarily many megabytes of instruction.

That is the trick. Everything else about skills is packaging.

!!! note "This is the same idea as `glob` and `grep`"

    An agent with a filesystem does not need its knowledge pre-loaded any more than it needs the
    repository pre-loaded. Anthropic calls the general version
    [just-in-time context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
    keep lightweight identifiers — file paths, names, descriptions — and dereference them at runtime.
    A skill is that pattern applied to instructions rather than to data. This harness already does the
    data half; see [Tools and the sandbox](tools-and-sandbox.md).

## The description is the entire routing layer

Level 1 is the only thing the model sees when deciding whether a skill is relevant. That makes
`description` a classifier prompt with a 1024-character budget, and it is where skills go wrong.

```yaml
# Poor — the model has no idea when this applies
description: Helps with PDFs.

# Good — says what it does AND when to reach for it
description: Extracts text and tables from PDF files, fills PDF forms, and merges
  multiple PDFs. Use when working with PDF documents or when the user mentions
  PDFs, forms, or document extraction.
```

The failure mode of a vague description is not an error. It is a skill that silently never fires, and
an agent that keeps solving the problem the hard way while you wonder why the skill you wrote made no
difference.

## Skills, tools, and MCP are three different things

They get conflated constantly, and the distinction is clean once stated:

| | What it is | Who provides it | Cost when idle |
| --- | --- | --- | --- |
| **Tool** | A verb the harness can execute | The harness | Its schema, on every call |
| **MCP server** | Where verbs come from at runtime | A third party | Its schemas, on every call — see [MCP and tool discovery](mcp-and-tool-discovery.md) |
| **Skill** | Instructions for using the verbs you have | Anyone with a folder | ~100 tokens |

A skill does not add capability. It adds *judgement about existing capability* — plus, optionally,
scripts, which is where it starts to blur.

## Why skills carry code, and why that matters

A skill may ship executable scripts. This is not a convenience feature; it is a correctness one.

Sorting a list by generating tokens is expensive and occasionally wrong. Sorting a list by calling
`sorted()` is neither. Anywhere a task has a deterministic answer, running code beats predicting the
answer — and a script inside a skill lets the agent run that code without either the script or its
input ever entering the context window.

This is the same argument as [grading the end state](evaluation.md) rather than the transcript:
prefer the mechanism that is checkable and repeatable over the one that is merely usually right.

## The security problem, stated plainly

A skill is instructions and code, from a third party, that your agent will read and follow inside
your sandbox.

That is a supply chain. A malicious `SKILL.md` does not need an exploit — it just needs the model to
do what the file says, which is the file's entire purpose. Anthropic's guidance is to install skills
only from trusted sources and to audit anything else before use, paying particular attention to
bundled scripts, dependencies, and instructions that reach out to the network.

Which is correct advice and also not a control. The controls are the ones on the pages either side of
this one: a [deny-by-default policy](permissions.md) that a skill cannot talk its way around, a
disposable sandbox that bounds the damage — [planned for v0.1.0](tools-and-sandbox.md), not shipped —
and an understanding of the [lethal trifecta](prompt-injection.md) so you notice when a skill quietly
completes it.

## Where this would attach in the loop

If this harness grew skills, the seam is narrow and worth naming:

- **Level 1** would be system prompt assembly — one line per skill, added before the first
  `provider.complete()`.
- **Level 2 and 3** need no new code at all. They are `read` calls against
  [`agent/tools/fs.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/tools/fs.py),
  already path-confined by `ToolContext`.
- **Scripts** are `bash` calls, already subject to
  [`agent/permissions.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/permissions.py).

That is the honest reason skills are cheap to adopt and expensive to secure: the loading mechanism is
just the file tools you already have, which means the trust boundary is exactly where it always was.

## What to check in your own agent

- Is your always-on context proportional to what the agent is doing right now, or to everything it
  might ever do?
- Can you name the token cost of a skill that never fires? If not, it is not progressively disclosed.
- Does each description say *when to use it*, or only what it does?
- If a skill can be installed by anyone, what stops one from being a
  [confused deputy](prompt-injection.md)?

## Sources

- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — Anthropic, October 2025
- [Agent Skills specification](https://agentskills.io/specification) — the open standard, December 2025
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, September 2025
