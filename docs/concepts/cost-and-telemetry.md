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

When no cached rate is configured, the accountant falls back to the full input rate. That errs
towards over-reporting, which is the safe direction for a cost estimate.

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
objects in a list you can assert on in a test. The span names are OTel-shaped (`provider.complete`,
`tool.run`) so exporting later is a translation rather than a rewrite.

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
