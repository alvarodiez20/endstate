# Use a self-hosted model

Anything that speaks the OpenAI protocol works through `--base-url`. No adapter, no config file.

## vLLM

```bash
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --enable-auto-tool-choice --tool-call-parser hermes
```

```bash
endstate run "fix the failing test" \
  --workdir ./sandbox \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen2.5-Coder-7B-Instruct
```

`--model` must match the name vLLM serves it under, which is the full repo id unless you passed
`--served-model-name`.

!!! warning "Tool calling needs to be switched on"

    `--enable-auto-tool-choice` and a `--tool-call-parser` matching the model's template are not
    optional. Without them vLLM ignores the tools you send, the model describes what it would do in
    prose, and the harness sees a response with no `tool_calls` — so the run ends after one step
    with `stop_reason=end_turn` and an empty sandbox.

    This looks exactly like a model that is too weak for the task. It is a serving flag.

## Ollama

```bash
ollama serve
```

```bash
endstate run "fix the failing test" \
  --workdir ./sandbox \
  --base-url http://localhost:11434/v1 \
  --model qwen2.5-coder:7b
```

Ollama's OpenAI-compatible endpoint is at `/v1`. Tool support varies by model — check the model card
before concluding the harness is broken.

## Gateways

LiteLLM, OpenRouter, vLLM behind a proxy, an internal gateway: same shape.

```bash
export OPENAI_API_KEY=your-gateway-key
```

```bash
endstate run "..." --base-url https://gateway.internal/v1 --model claude-sonnet-4-5
```

Note that `--model` names starting with `claude` route to the **Anthropic adapter**, which ignores
`--base-url`. To reach a Claude model through an OpenAI-compatible gateway, use whatever alias your
gateway exposes that does not start with `claude`.

## Set the context window honestly

```bash
endstate run "..." \
  --base-url http://localhost:8000/v1 \
  --model qwen2.5-coder \
  --max-context-tokens 32768
```

`--max-context-tokens` defaults to 128,000, which is wrong for most self-hosted models and wrong in
the dangerous direction: [compaction](../concepts/context-and-compaction.md) never fires, the request
exceeds what the server will accept, and the run dies on a long task after doing most of the work.

Set it to what you actually served, and remember the budget reserves 8,000 tokens for output.

## Why this is one flag and not a plugin system

The loop depends on a [one-method Protocol](../concepts/messages-and-providers.md). Hosted and
self-hosted are the same code path, which is what makes it possible to run **the same eval suite**
against a frontier API and a 7B model on your own GPU and compare the numbers without changing a
single task.

That comparison is the [benchmark](../concepts/evaluation.md), and it is the reason the provider
boundary is drawn where it is.

## What to expect

Smaller models fail differently, not just more often. Common patterns:

- **Malformed tool arguments** — a JSON Schema violation, or arguments as a string instead of an
  object. Surfaces as a tool error the model then has to recover from.
- **Forgetting the task on long runs** — worse when the context window is small and compaction fires
  early. Pinning the first user message helps, but does not fully compensate.
- **Narrating instead of calling** — describing the edit rather than emitting a `tool_call`. Often the
  serving flags above; sometimes the model.
- **Loops** — repeating a failed command unchanged. `--max-steps` is what stops this.

None of these are failures of the harness, and all of them are the sort of thing a
[benchmark](../concepts/evaluation.md) should report rather than hide. A 7B model passing 6 of 20
tasks at a fortieth of the cost is a useful, publishable result.
