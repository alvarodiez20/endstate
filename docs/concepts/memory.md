# Memory

[Compaction](context-and-compaction.md) decides what to throw away. Memory decides what to keep
somewhere the context window cannot evict it. They sound like the same problem and they fail in
opposite directions.

!!! info "Status"

    `endstate` has **no memory system**. It has [durability](durability.md) — a SQLite checkpoint of
    the message history so a killed run can resume — which is a different thing wearing similar
    clothes, and the distinction is the first section below. Retrieval and vector stores are an
    explicit [non-goal](../design/non-goals.md).

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/memory.html"
          height="740" loading="lazy"
          title="Durability compared with memory across a context reset"></iframe>
</div>

## Durability is not memory

Both write to disk. Both survive process death. They answer different questions:

| | Durability | Memory |
| --- | --- | --- |
| Question | "Where was I in *this* run?" | "What did I learn that outlives this run?" |
| Written by | The harness, automatically | The agent, deliberately |
| Read by | The resume path | The agent, when it decides to |
| Content | Everything, verbatim | A curated subset, in the agent's own words |
| Lifetime | One run | Many runs |
| Failure mode | Replayed side effects | Confidently acting on a stale note |

A checkpoint is a transcript. A memory is a *claim*. The second one can be wrong in a way the first
cannot, and that is the whole difficulty.

## Why compaction alone is not enough

A run long enough to compact will compact several times. Each pass is lossy by construction —
`DropOldest` deletes the middle, `SummariseMiddle` compresses it — and the losses stack. By the fifth
compaction the agent's account of what it has already tried is a summary of a summary.

For a forty-minute task that is survivable. For a codebase migration that runs for hours, or a task
resumed tomorrow, it is not: the single most valuable fact in the whole history is often *"I already
tried that and it did not work,"* and that is precisely the kind of detail compaction discards as
old tool noise.

Compaction is a strategy for staying under a limit. It is not a strategy for remembering.

## The mechanism, which is boringly simple

Structured note-taking, sometimes called agentic memory: the agent writes to a file outside the
context window and reads it back later.

```
NOTES.md          # what I have tried, what worked, what is still broken
PLAN.md           # the decomposition, with items ticked off
findings/         # one file per investigated thread
```

No infrastructure, no embeddings, no retrieval model. A file and the `read`/`write` tools the agent
already has. Anthropic's example of how far this goes is
[Claude playing Pokémon](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
across thousands of steps the agent maintained tallies ("for the last 1,234 steps I've been training
on Route 1"), drew maps of explored regions, and kept notes on which attacks worked against which
opponents. After each context reset it read its own notes and continued a multi-hour training
sequence. Nobody prescribed the structure; it invented one because it had a filesystem.

The Claude Developer Platform now ships a file-backed
[memory tool](https://www.anthropic.com/news/context-management) that formalises this, but the
formalisation is not the insight. The insight is that a directory is already a memory system, and
that an agent with `read`, `write` and `glob` has one whether you designed it or not.

## Three techniques, three different jobs

They get treated as competitors. They are not.

| Technique | Best at | Cost |
| --- | --- | --- |
| **Compaction** | Conversational tasks with a lot of back-and-forth | Lossy; costs a model call for `SummariseMiddle` |
| **Note-taking** | Iterative work with clear milestones | The agent must remember to write, and to re-read |
| **[Subagents](subagents.md)** | Parallel exploration where each thread can be summarised independently | Coordination, and several times the tokens of a single agent |

Most real agents want compaction plus notes. Reaching for the third when the first two would do is
the most common over-engineering in this space.

## What makes memory hard

**It has to be written before it is needed.** The agent must decide, at step 12, that something will
matter at step 40. Models are mediocre at this by default and much better when the harness makes it
routine — a to-do file that is always updated, a findings file that is always appended to. Rely on
spontaneous note-taking and you get notes on the runs that did not need them.

**It has to be read back.** A file nobody opens is not memory. Which means the memory has to be
discoverable: a predictable path, or a line in the system prompt saying it exists. This is the
[level-1 disclosure](skills.md) problem again — an unlisted capability is an absent one.

**It goes stale, and staleness is invisible.** A note saying *"the auth tests are red"* is a fact
about a moment. Read three runs later it is an assertion about the present, indistinguishable in the
context window from something the agent just observed. Timestamps in notes are not decoration.

**It is a persistence surface, so it is an attack surface.** Anything the agent reads can contain
instructions, and memory is content the agent reads *and trusts more than average*. A poisoned note
survives every context reset — it is the one part of the system explicitly designed not to be
forgotten. See [Prompt injection](prompt-injection.md).

**It grows.** A NOTES.md that is only appended to becomes, in a month, a document too large to load
— at which point you need compaction for your memory, and the recursion is not a joke.

## Memory and retrieval are not the same argument

Vector stores answer "find me text similar to this query" over a corpus. Memory answers "what do I
already know about the thing I am doing." They overlap and they are not interchangeable, and
conflating them is how projects end up with an embedding pipeline to solve a problem a text file
solves.

This project does neither, deliberately. The agent reads files with `grep` and `read`, like a person
would; see [Non-goals](../design/non-goals.md). The relevant observation for anyone who *is* building
memory is that filesystem structure is itself signal — `test_utils.py` in `tests/` means something
different from the same filename in `src/core_logic/`, and folder hierarchies, naming conventions and
timestamps carry information that an embedding of the file contents throws away.

## Why memory is an end-state problem

Worth stating explicitly, because it connects to the [one idea](index.md) underneath this section.

Memory is not conversational state. It is a **file the agent wrote**, which makes it a side effect,
which makes it part of the end state — and therefore something a [grader](evaluation.md) can inspect
without reading a single message.

That has a pleasant consequence. "Did the agent record what it learned?" is not a judgement call
about a transcript. It is `assert (workdir / "NOTES.md").exists()` and an assertion about its
contents. Memory, unlike most things on this page, is straightforwardly testable — and if you are
building it, that is where the tests should live.

## What to check in your own agent

- If you killed a run and started a new one tomorrow, what would the agent know? Anything?
- Is note-taking a habit the harness enforces, or a behaviour you are hoping for?
- Can the agent tell how old a memory is?
- What stops a memory file from growing without bound?
- Who else can write to it?

## Sources

- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, September 2025
- [Managing context on the Claude Developer Platform](https://www.anthropic.com/news/context-management) — the memory tool
