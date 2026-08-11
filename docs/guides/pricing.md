# Price a model

`endstate` ships no prices. Until you supply them, runs report `cost (USD): unknown`.

That is deliberate — see [Cost and telemetry](../concepts/cost-and-telemetry.md). A hardcoded price
table is stale the week after it is written, and a wrong cost is worse than a missing one.

## Write a price table

```bash
cp prices.example.json prices.json
```

```json
{
  "gpt-4o-mini": {
    "input_per_mtok": "0.15",
    "output_per_mtok": "0.60",
    "cached_input_per_mtok": "0.075"
  },
  "self-hosted-l4": {
    "input_per_mtok": "0.00",
    "output_per_mtok": "0.00"
  }
}
```

Keys are model ids exactly as you pass them to `--model`. Values are **USD per million tokens**.

```bash
endstate run "..." --prices ./prices.json
```

Now the summary table reports a number instead of `unknown`.

## Three details that matter

**Quote the numbers.** They are parsed as `Decimal`, and strings never round-trip through a float on
the way in. Bare JSON numbers work, but you have re-introduced binary floating point into money
arithmetic that then gets multiplied by token counts and summed across hundreds of tasks.

**No comment keys.** JSON has no comments, and every top-level key is parsed as a model price — a
`"_comment"` entry raises a `TypeError` on load. Keep notes outside the file.

**`cached_input_per_mtok` is optional but worth setting.** Prompt-cached input is often priced around
an order of magnitude below fresh input. Omit it and the accountant falls back to the full input rate,
which over-reports a cache-heavy workload — safe, but it will make caching look like it is not
working.

## Pricing a self-hosted model

The honest per-token price of a self-hosted model is not zero, and it is not on a pricing page. It is:

```
(GPU hourly cost × hours) / tokens produced in those hours
```

Which depends on your utilisation, so it is a number you measure rather than look up. Two workable
approaches:

**Zero, labelled as such.** Set both rates to `"0.00"` and report GPU-hours separately. Honest as long
as the report says "self-hosted, GPU-hours reported separately" rather than implying free inference.

**Amortised.** Take your spot GPU rate, divide by measured throughput over a real run, use that. More
useful for a genuine cost comparison, and the number a
[benchmark](../concepts/evaluation.md) should carry — the interesting claim is "a fortieth of the
cost," and you cannot make it with a placeholder.

## Reading cost in Python

```python
from endstate.telemetry.cost import CostAccountant, PriceTable, UnknownModelPriceError

accountant = CostAccountant(PriceTable.from_file("prices.json"))
# ... run the loop with accountant=accountant ...

print(accountant.total_usage)          # always available
print(accountant.priced_models())      # models with a known price
print(accountant.unpriced_models())    # models without one

try:
    print(f"${accountant.total_cost():.4f}")
except UnknownModelPriceError as exc:
    print(f"no price for {exc}")
```

`total_cost()` raises rather than skipping unpriced models, so a total is either complete or it is an
exception. Check `unpriced_models()` first if you want to report partial coverage — which is what the
CLI does.
