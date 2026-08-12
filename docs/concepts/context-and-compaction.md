# Context and compaction

Every long-running agent eventually runs out of context window. What it throws away, and whether it
notices, decides whether it can do work that takes an hour.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/context-and-compaction.html"
          height="535" loading="lazy" title="Context growth and what compaction keeps"></iframe>
</div>

## Why this is unavoidable

Context grows monotonically. Each step adds an assistant message and a batch of tool results, and
tool results are the big ones — a file read is thousands of tokens, a test run's output can be tens
of thousands. A twenty-step run on a real repository will exceed any window currently available.

And the growth is not gentle. It is one `grep` away from a step that adds 40,000 tokens.

## The window is not the real limit

Running out of window is the obvious reason to compact. It is not the first one, and framing the
whole problem as a capacity problem gets the design subtly wrong.

Chroma's [context rot](https://research.trychroma.com/context-rot) study evaluated 18 frontier models
— GPT-4.1, Claude 4, Gemini 2.5 and Qwen3 families — on tasks deliberately kept trivial, including
retrieving a single planted fact and replicating text verbatim. Every one of the 18 got worse as
input length grew, and the degradation began **well before the window filled**. This is not overflow;
it is a gradient that starts at a fraction of the advertised capacity.

Three findings are worth carrying into a compaction strategy:

- **Similarity matters more than position.** When the planted fact was worded unlike the question,
  accuracy fell faster with length. Retrieval is not uniform lookup; it is closer to matching, and
  matching degrades.
- **A single distractor hurts.** One plausible-but-wrong passage lowered accuracy, and the more
  semantically similar it was to the right answer, the worse the effect. A long agent history is
  *full* of near-miss distractors: the file you read and rejected, the approach you tried and
  abandoned.
- **Coherent context performed worse than shuffled context.** Across all 18 models, a logically
  ordered haystack was harder than a randomised one. Nobody has a satisfying explanation, and it
  undercuts the intuition that tidier context is automatically better.

The design consequence: **compaction is not only a capacity mechanism, it is a quality mechanism.**
Dropping forty superseded tool results can make the model better even when the full history would
have fit. Anthropic's framing is that context is an
[attention budget](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
with diminishing returns, and that the goal is the smallest set of high-signal tokens rather than the
largest set that fits.

`TokenBudget` below encodes only the capacity half of that. Nothing in this harness currently
compacts because the context has gone stale rather than long — a gap worth naming rather than
glossing.

## Why the naive fix fails

The obvious approach is a sliding window: keep the last N messages. Now watch what happens on a long
task.

Step 1 is the user saying *"migrate the auth module to the new session API and keep the tests
green."* By step 30, that message has slid out of the window. The agent is now looking at twenty
tool results about session handling with no statement of what it is supposed to be doing. It does not
error. It keeps working — on whatever the recent context implies, which is usually "keep editing
files near the ones you were editing."

This is the most common failure mode in long-horizon agents, and from the outside it looks like the
model getting dumber over time.

## The fix: pin what matters, drop the middle

```python
class DropOldest:
    """Keep the system prompt, the first user message, and the newest tail that fits.

    The first user message is pinned because it usually contains the task; losing
    it is the most common way a long-horizon agent forgets what it was doing.
    """
```

The system prompt and the first user message are pinned. Then the newest messages are added, oldest
first, until the next one would exceed the budget. What gets dropped is the *middle* — old tool
results, superseded file reads, the exploratory dead ends — which is exactly the material with the
worst value-per-token in the whole conversation.

Source:
[`agent/context.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/context.py).

## The budget is an object

```python
class TokenBudget(BaseModel):
    max_context_tokens: int = 128_000
    reserve_output_tokens: int = 8_000

    @property
    def usable_tokens(self) -> int:
        return max(0, self.max_context_tokens - self.reserve_output_tokens)
```

`reserve_output_tokens` is the part people forget. The context window is shared between what you send
and what the model generates. Fill 128k of a 128k window with input and there is no room left for a
reply — you get a truncated response or a provider error, at the worst moment, on the longest and
most expensive run.

Reserving output space up front makes the failure impossible rather than rare.

## Compaction is measured, not silent

This is the part most implementations skip, and it is the reason this module exists as its own
concept rather than as a utility function:

```python
class CompactionEvent(BaseModel):
    strategy: str
    tokens_before: int
    tokens_after: int
    messages_before: int
    messages_after: int
    dropped_messages: int

    @property
    def tokens_reclaimed(self) -> int:
        return self.tokens_before - self.tokens_after
```

Every compaction is recorded with counts before and after, and the events end up on `RunResult`. So
"what did compaction cost you?" has a number instead of a shrug, and — more importantly — an eval
task can assert `compaction_events >= 1`.

That assertion is what turns compaction from a hidden mechanism into a tested one. A long-horizon
eval task passes only if the agent completed the work **and** compaction actually fired. If it never
fired, the task was not long enough to test the thing it claimed to test.

## Two strategies, and the difference between them

**`DropOldest`** throws the middle away. Cheap, deterministic, no extra model call. The agent loses
the details of what it already did.

**`SummariseMiddle`** replaces the dropped middle with one synthetic message summarising it. The
agent keeps a lossy trace of its own history — which matters when step 40 needs to know that step 12
already tried something and it didn't work.

The design detail worth stealing:

```python
def __init__(self, summariser: Callable[[list[Message]], str]) -> None:
    self.summariser = summariser
```

It takes a **callable**, not a provider. A test can pass `lambda msgs: "summary"` and assert on the
structural behaviour — that the summary lands in the right position, that pinned messages survive,
that the event is recorded — with no network call and no non-determinism. The expensive dependency is
injected at the edge rather than reached for in the middle.

Summary messages are marked `synthetic=True`, so telemetry can distinguish what the agent was told
from what actually happened.

### The third strategy this harness does not have

Both of the above operate on *messages*. The cheapest useful strategy operates on **tool results**
specifically: once a tool has been called deep in the history, the agent rarely needs its raw output
again — only the conclusion it drew from it. Clearing old tool results while leaving the reasoning
intact is the lightest-touch compaction available, and it is now a first-class
[platform feature](https://www.anthropic.com/news/context-management) rather than a trick.

It is attractive here because tool results are precisely the material that dominates an agent's
context and has the worst value-per-token. A `DropOldestToolResults` strategy would fit the existing
`Compactor` interface without touching the loop. It is not implemented; it is the first thing to
build if this module is extended.

A related idea from the same direction is **context awareness** — telling the model how much of its
budget remains, so it can decide to write notes or wrap up rather than being truncated mid-thought.
That one changes the prompt, not the compactor.

## Counting tokens without a tokeniser

```python
class HeuristicTokenCounter:
    """Chars/4 approximation.

    Deliberately not a tokeniser: the harness must work against any provider,
    including ones whose tokeniser is not public.
    """
```

This is approximate and that is a deliberate trade. A real tokeniser means a hard dependency per
provider, and it is simply unavailable for some — including most self-hosted models you might put in
a [benchmark](evaluation.md). `TokenCounter` is a Protocol, so swapping in an exact counter is a
one-line change when exactness matters.

The approximation is fine for its actual job. It decides *when* to compact, and it is guarded by
`reserve_output_tokens`, which is far larger than the error.

## Compaction is not the only lever

Compaction keeps a run under a limit. It does not help a run that has already ended — the losses are
gone, and the next run starts from nothing. The complementary technique is to write things *outside*
the window on purpose rather than choosing what to delete from inside it. See [Memory](memory.md),
and [Subagents](subagents.md) for the version where the thing kept outside the window is an entire
second context.

## What to check in your own agent

- Does anything survive compaction unconditionally, or can the task statement be evicted?
- Is output space reserved, or does the window fill until a response gets truncated?
- Is there a record that compaction happened, or does it occur invisibly?
- Can you write a test that fails when compaction is broken? If not, it is untested.

## Open problems

**Nobody can measure what a compaction cost.** `CompactionEvent` records tokens reclaimed, which is
the easy half. The hard half — what capability was lost — has no metric. Anthropic's practical advice
is to tune the summariser prompt for recall first and precision second, which is sound and is still
prompt-tuning against traces rather than measurement.

**Compaction fights prompt caching.** Editing the middle of a history invalidates the cached prefix
from that point on, so a pass that reclaims tokens can force a full cache re-write on the very next
call. With a 1.25× write against a 0.1× read, the arithmetic is not obviously in compaction's favour
at the margin. See [Messages and providers](messages-and-providers.md); no harness known to us models
this trade-off explicitly.

**Longer windows do not dissolve the problem.** The Chroma result is that degradation is a gradient,
not a cliff, and it appears at a fraction of the advertised window. Every model generation makes the
capacity argument for compaction weaker and the quality argument stronger, which suggests strategies
should eventually be driven by *what the context contains* rather than by how big it is. There is no
accepted way to detect that.

**Compaction quality has no benchmark.** There is no shared task suite that fails specifically when a
compactor is bad. This project's answer is a conjunction — a long-horizon task passes only if it
completes *and* `compaction_events >= 1` — which proves compaction fired, not that it kept the right
things. That is a weaker claim than it looks and is worth stating plainly.
