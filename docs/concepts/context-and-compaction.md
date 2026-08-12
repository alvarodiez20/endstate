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
