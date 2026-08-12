# Cost and telemetry

"Is the agent expensive?" is a question that should have a number. In most agent codebases it has a
shrug, or worse, a confidently wrong number.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/cost-and-telemetry.html"
          height="960" loading="lazy" title="From token usage to a cost number"></iframe>
</div>

## Usage is not cost

Two separate things, deliberately kept separate.

**Usage** is token counts, reported by the provider, always available and always true. The loop
accumulates it per model:

```python
class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
```

**Cost** is usage multiplied by a price you have to know from somewhere else. It is derived, and it
is only as good as your price table.

Conflating them is how you get a dashboard that is confidently wrong. Usage is a measurement; cost is
a claim.

## Prices are data, not code

They change often, they vary by region and by contract, and a hardcoded table goes stale the week
after you write it. So prices live in a JSON file the user supplies:

```json
{
  "gpt-4o-mini": {
    "input_per_mtok": "0.15",
    "output_per_mtok": "0.60",
    "cached_input_per_mtok": "0.075"
  }
}
```

See [Price a model](../guides/pricing.md) for the practical version.

## Unknown prices raise

This is the opinionated bit, and it is decision **D4**:

```python
def cost_for(self, model: str) -> Decimal:
    price = self.price_table.get(model)
    if price is None:
        raise UnknownModelPriceError(model)
    return price.cost(self._usage_by_model.get(model, Usage()))
```

The alternative — returning `0.0` for an unpriced model — is the kind of default that seems polite
and is actually a liability. A benchmark table that reports `$0.00` for the self-hosted model does not
read as "unknown," it reads as "free," and someone will make a decision on it.

> **A wrong cost number is worse than a missing one.**

A missing number prompts a question. A wrong number ends the conversation.

The accountant also exposes `priced_models()` and `unpriced_models()`, so a report can say exactly
which models it can and cannot cost, rather than silently summing a subset.

Source:
[`telemetry/cost.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/telemetry/cost.py).

## `Decimal`, not `float`

Money arithmetic in binary floating point accumulates error, and this is a case where you multiply
small rates by large token counts and then sum across hundreds of tasks. `Decimal` throughout, and
prices are parsed from JSON *strings* so they never touch a float on the way in.

Cheap to do correctly at the start; genuinely annoying to retrofit.

## Cached input is tracked separately

`cached_input_tokens` is its own field with its own rate, because prompt-cached input is often priced
around an order of magnitude below fresh input. Fold it into `input_tokens` and a cache-heavy
workload looks dramatically more expensive than it is — which will lead you to optimise the wrong
thing, or to abandon caching that was working.

When no cached rate is configured, the accountant falls back to the full input rate.

!!! warning "One field is not enough, and the fallback is not always conservative"

    Providers report caching as **two** counters with opposite economics. Anthropic's shape is
    representative:

    | Counter | Price, relative to base input |
    | --- | --- |
    | `cache_creation_input_tokens` (write, 5-minute TTL) | **1.25×** |
    | `cache_creation_input_tokens` (write, 1-hour TTL) | **2×** |
    | `cache_read_input_tokens` | **0.1×** |

    `Usage` has a single `cached_input_tokens` field and `ModelPrice` a single
    `cached_input_per_mtok`, so an adapter has to pick one meaning. Neither choice is right:

    - Count only reads and the write premium disappears from the total.
    - Count both and the same rate is applied to tokens that differ in price by 12.5× to 20×.

    The documented fallback compounds it. Falling back to the *full input rate* over-reports a read
    (0.1× billed as 1×) but **under**-reports a write (1.25× or 2× billed as 1×). The claim that the
    fallback errs safely holds for reads and fails for writes.

    This matters most for exactly the workload this project measures. An agent loop re-sends a
    growing prefix every step, so writes and reads are both frequent — and every
    [compaction](context-and-compaction.md) invalidates the prefix and forces another write. Getting
    the two rates wrong in either direction changes which model looks cheaper.

    The fix is small and not yet made — split the field, split the rate. See
    [Anthropic's prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
    for the counters as reported.

## Tracing

`Trace` records in-process spans for provider calls, tool runs, and denials:

```python
with self.trace.span("provider.complete", step=steps):
    response = self.provider.complete(fitted, specs)

with self.trace.span("tool.run", tool=call.name):
    output = tool.run(call.arguments, self.tool_context)

with self.trace.span("tool.denied", tool=call.name, reason=reason):
    pass
```

Note the third one. A denial produces a span even though nothing runs, because "the agent tried to do
something forbidden" is exactly the event you want a record of. A near-miss that leaves no trace is a
near-miss you will never learn from.

Deliberately in-process and dependency-free — no OpenTelemetry, no collector, no exporter. Spans are
objects in a list you can assert on in a test. The span names are OTel-*shaped* — dotted, verb-last,
one span per unit of work — so exporting later is a translation rather than a rewrite.

!!! note "What that translation would actually look like"

    OpenTelemetry does now have GenAI semantic conventions, and they model an agent as a span tree
    rather than a flat list of model calls: an `invoke_agent` span containing `chat` spans for model
    calls and `execute_tool` spans for tool runs, with `gen_ai.operation.name` covering
    `create_agent`, `invoke_agent`, `execute_tool`, `retrieval`, `plan` and a family of memory
    operations. Token counts are recorded as span attributes — `gen_ai.usage.input_tokens`,
    `gen_ai.usage.output_tokens`, and separate `gen_ai.usage.cache_creation.input_tokens` and
    `gen_ai.usage.cache_read.input_tokens`, which is the split this module does not yet make.

    So the mapping is real but not free: `provider.complete` → `chat`, `tool.run` → `execute_tool`,
    and the run itself would need a wrapping `invoke_agent` span that does not currently exist.
    `tool.denied` has no counterpart at all.

    Worth knowing before adopting them: every `gen_ai.*` span and attribute still carries the
    **Development** stability badge — none are Stable — and the conventions have been moved out of
    the main semantic-conventions repository into
    [one of their own](https://github.com/open-telemetry/semantic-conventions-genai), which is a
    faster release cadence rather than a graduation. Instrumenting against them today means tracking
    a moving target. That is an argument for keeping the internal representation independent and the
    translation thin, which is the position this module already takes, for a reason it did not
    originally state.

Source:
[`telemetry/trace.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/telemetry/trace.py).

## What ends up on `RunResult`

```python
class RunResult(BaseModel):
    session_id: str | None
    messages: list[Message]
    usage: Usage
    stop_reason: StopReason
    steps: int
    compaction_events: list[CompactionEvent]
    denied_calls: list[DeniedCall]
    final_text: str
```

Every field except `messages` and `final_text` is something an eval can assert on:

- `steps` — did it take 3 attempts or 24?
- `compaction_events` — did the long-horizon task actually exercise compaction?
- `denied_calls` — did the permissioning task actually get refused?
- `usage` — did it stay inside the declared token budget?
- `stop_reason` — did it finish, or hit a ceiling?

This is the machinery that lets the [benchmark](evaluation.md) report pass rate *and* median steps
*and* cost per task *and* compaction events per task. A pass rate on its own hides the model that
succeeds by burning forty steps and six dollars.

## Open problems

**Reasoning tokens are billed but not visible.** Thinking is charged as output, and on newer models
prior turns' thinking is retained and charged again as input, while on older ones it is stripped.
That means two models with identical `input_tokens`/`output_tokens` can have had materially different
amounts of hidden work done, and the same model can change its billing behaviour across a version
bump. `Usage` has no field for it. See [Messages and providers](messages-and-providers.md).

**Cross-provider cost comparison is not apples to apples.** A per-token price and a GPU-hour are
different units, and the benchmark this project is building deliberately puts a hosted API next to a
self-hosted endpoint. Amortising hardware, idle time and batching into a per-task dollar figure
requires assumptions that will not survive scrutiny, and the honest options are to publish the
assumptions or publish two incomparable columns.

**Cost per task is the wrong denominator, and the right one is contested.** Cost per *resolved* task
is more useful and rewards a model that fails fast, but it hides the spend on failures. Cost per
attempt hides the opposite. Both are needed and no convention exists for reporting them together.

**There is no accepted unit of agent work.** Steps, tokens, tool calls and wall-clock all measure
something and none is dominant, which is why cross-harness comparisons are mostly rhetorical. A
number is only comparable inside one harness — a limitation this project should state louder than it
currently does.
