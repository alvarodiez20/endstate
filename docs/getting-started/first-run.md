# Your first run

## Give it something to fix

The agent works on a directory. Make a small one with a deliberately failing test:

```bash
mkdir -p /tmp/endstate-demo && cd /tmp/endstate-demo
```

```bash
cat > test_math.py <<'EOF'
from mathlib import add

def test_add():
    assert add(2, 3) == 5
EOF
```

```bash
cat > mathlib.py <<'EOF'
def add(a, b):
    return a - b
EOF
```

`pytest -q` fails. Now hand the problem over:

```bash
endstate run "the test in this directory fails. find out why and fix it" --workdir /tmp/endstate-demo
```

## What you get back

The final message, then a summary table:

```
╭───────── run ─────────╮
│ session      a3f9c211 │
│ steps        4        │
│ stop reason  end_turn │
│ input tokens 8,412    │
│ output tokens 391     │
│ compactions  0        │
│ denied calls 0        │
│ cost (USD)   unknown  │
╰───────────────────────╯
```

Every row is a claim you can check.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/first-run.html"
          height="535" loading="lazy"
          title="The run summary table, row by row"></iframe>
</div>

**`steps`** — model calls, not tools. Four means it read, edited, verified, and reported. Twenty
would mean it thrashed.

**`stop reason`** — `end_turn` means the model stopped asking for tools. It does **not** mean success;
see [The loop](../concepts/the-loop.md). The only real check is the obvious one:

```bash
cd /tmp/endstate-demo && pytest -q
```

That is the whole thesis in miniature. The table tells you what the run cost; the filesystem tells you
whether it worked. Grading the first as though it were the second is the mistake
[endstate exists to avoid](../concepts/evaluation.md).

**`compactions`** — how many times history was squeezed to fit the window. Non-zero on a short task
means your budget is too small.

**`denied calls`** — tool calls the [permission policy](../concepts/permissions.md) refused. Non-zero
is not necessarily bad; it means a guard fired.

**`cost (USD)`** — `unknown` until you supply a price table, on purpose. See
[Price a model](../guides/pricing.md).

## Watch a guard fire

```bash
endstate run "delete everything in this directory with rm -rf" --workdir /tmp/endstate-demo
```

`denied calls` goes to 1 and the files are still there. The agent sees the refusal as a tool result
and can respond to it, rather than the run dying.

## The options that matter

```bash
endstate run "..." \
  --workdir ./sandbox \
  --model gpt-4o-mini \
  --max-steps 25 \
  --max-context-tokens 128000 \
  --prices ./prices.json
```

| Option | Why you would change it |
| --- | --- |
| `--workdir` | The only directory tools may touch. Defaults to the current one — be careful. |
| `--model` | Names starting with `claude` route to Anthropic; everything else is OpenAI-compatible |
| `--max-steps` | The ceiling on model calls. Your main defence against an expensive infinite loop. |
| `--max-context-tokens` | Set to your model's real window so compaction fires at the right time |
| `--prices` | Path to a JSON price table; without it, cost reports `unknown` |
| `--base-url` | Point at vLLM, Ollama, or a gateway |

!!! warning "`--workdir` defaults to the current directory"

    Tools are confined to it, and the [permission policy](../concepts/permissions.md) blocks the
    obvious destructive commands — but on a laptop those are the *only* things between the agent and
    your files. Run against a scratch directory, or a container, until you trust it.

## Next

[Resuming a run →](resuming.md)
