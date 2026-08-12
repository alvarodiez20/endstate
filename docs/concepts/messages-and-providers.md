# Messages and providers

Before anything interesting can happen, you need a definition of "conversation" that survives contact
with more than one vendor. This is unglamorous and it is where a surprising number of agent codebases
acquire a permanent limp.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/messages-and-providers.html"
          height="830" loading="lazy" title="One message model, many provider wire formats"></iframe>
</div>

## The problem

Every provider represents the same conversation differently.

- Anthropic puts tool calls in typed content blocks inside an assistant message, and tool results
  come back as blocks in a *user* message.
- OpenAI puts tool calls in a separate `tool_calls` array on the assistant message, and each result
  is its own message with `role: "tool"`.
- Some OpenAI-compatible servers (vLLM, Ollama, gateways) implement a subset, or emit tool calls as
  text that you are expected to parse.

If you write the loop against one of those shapes, you have not written an agent harness. You have
written a client for one vendor, and adding a second means editing the loop — which is exactly when
the interesting logic starts sprouting `if provider == ...` branches.

## The fix: one internal shape

The harness defines its own types and requires every adapter to translate into them. The loop never
sees a vendor object.

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]

class ToolResult(BaseModel):
    call_id: str          # ties the result back to the call
    content: str
    is_error: bool = False

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []
    synthetic: bool = False   # set when compaction invented this message
```

Full definitions:
[`types.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/types.py).

Three details are worth pausing on.

**`call_id` is not decoration.** A single assistant message can request several tools at once. The
results come back as a batch, and the model needs to know which result belongs to which call. Lose
the id and a parallel tool call turns into a guessing game.

**`is_error` is a field, not an exception.** A tool that fails still produces a result that goes back
to the model. Errors are information the agent can act on — see [The loop](the-loop.md).

**`synthetic` marks messages the harness invented.** When compaction replaces forty messages with one
summary, that summary was never said by anyone. Marking it means telemetry can tell the difference
between what happened and what the harness constructed, which matters when you are debugging a run
that went strange after a compaction.

## The provider interface is one method

```python
@runtime_checkable
class Provider(Protocol):
    model: str

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response: ...
```

Source:
[`providers/base.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/providers/base.py).

That is the entire contract. Adding a provider means writing one adapter; it never means touching
the loop. It is also what makes the same eval suite runnable against a hosted API and a self-hosted
vLLM endpoint without changing a single task — which is the whole point of the
[benchmark](evaluation.md).

!!! tip "Protocol, not base class"

    `Provider` is a `typing.Protocol`, so an adapter does not import or subclass anything from the
    harness. Structural typing means a class that happens to have the right shape *is* a provider.
    This keeps the dependency arrow pointing one way and makes adapters trivially testable.

## The gap in this model: reasoning blocks

Everything above assumes a turn is text plus tool calls. Since reasoning models shipped, that is no
longer the whole shape, and this is the one place where the type system on this page is behind the
providers it abstracts.

Anthropic returns **thinking** as its own content block. Three properties make it awkward, and all
three are documented under
[thinking in tool and multi-turn workflows](https://platform.claude.com/docs/en/build-with-claude/thinking-tool-workflows):

- It carries a cryptographic signature. The text is verifiable but not freely editable.
- On a follow-up call the *entire sequence* of consecutive thinking blocks must be returned exactly
  as the model produced it. You may not reorder or rewrite them.
- What happens to prior turns' thinking differs **by model, not merely by vendor**, and the
  boundary falls in a different place for each family: Opus 4.5 and later, and Sonnet 4.6 and later,
  keep every prior turn's thinking in context and bill it as input; earlier Opus and Sonnet models,
  and every Haiku through 4.5, keep only the last turn and strip the rest server-side.
- Switching models mid-conversation means stripping thinking blocks from prior turns yourself. They
  are tied to the model that produced them; another model ignores them silently rather than
  erroring — and still bills you for the tokens.

The configuration surface moves too. Anthropic's fixed `budget_tokens` mode is now legacy — 4.7 and
later reject it outright — replaced by adaptive thinking, where the model decides whether to think at
all. That is not a wire-format change an adapter can absorb silently: the same code path against two
model versions produces different token accounting and different behaviour.

OpenAI's reasoning models have their own representation with its own rules. There is no cross-vendor
standard, and unlike tool calls — where the shapes differ but the *concepts* line up cleanly onto
`ToolCall` and `ToolResult` — there is no obvious neutral form to normalise into. The content is
partly opaque by design.

!!! warning "This harness does not handle thinking blocks"

    `Message` has no field for reasoning content, so a provider adapter here has to drop it. For
    non-thinking models that is correct. For a thinking model with tool use it is not: dropping the
    blocks loses [interleaved reasoning](the-loop.md) between tool calls, and with some providers it
    is a protocol error rather than a degradation.

    The honest description is that this is a known gap, not a design choice. If you are building the
    same abstraction, budget for an opaque, provider-scoped passthrough field from the start — it is
    much easier than retrofitting one.

## The other thing that leaks through: cache breakpoints

Prompt caching is priced, not free, and it is prefix-based: the provider can only reuse a cached
prefix up to the first token that changed. That has a consequence which is invisible from inside a
`Message` type and expensive in practice.

**Editing the middle of the history invalidates everything after it.** Which is exactly what
[compaction](context-and-compaction.md) does. A compaction pass that reclaims 60,000 tokens can also
force a full cache re-write on the next call, and with Anthropic's pricing a 5-minute cache write
costs 1.25× base input against a 0.1× read. Compaction can therefore *raise* the cost of the very
next step while lowering it for every step after.

Nothing in this harness models that yet. It is called out here because it is the clearest example of
a provider detail that a clean internal message type will happily hide from you until it shows up on
a bill.

## `Usage` is part of the response, not a side channel

```python
class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
```

Token counts come back attached to the response that produced them, and `Usage` supports `+` so the
loop can accumulate a total without any bookkeeping ceremony. Cached input is tracked separately
because it is usually priced differently — often by an order of magnitude. Folding it into
`input_tokens` makes a prompt-cached workload look far more expensive than it is. See
[Cost and telemetry](cost-and-telemetry.md).

## `FakeProvider`: the most useful class in the repo

There is a provider that does not do any I/O. You hand it a scripted sequence of responses and it
returns them in order.

This is what makes the harness testable. Every test of the loop, permissions, compaction and session
durability runs against `FakeProvider` — no network, no API key, no flakiness, no cost, and complete
control over the exact sequence of tool calls a test needs to provoke. The full suite runs in well
under a second.

If you build an agent and take one idea from this page, take this one: **the fake provider is not a
testing afterthought, it is a design requirement.** A harness you cannot drive deterministically is a
harness you cannot test, and you will discover that at the worst possible moment.

Source:
[`providers/fake.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/providers/fake.py).

## Open problems

**No standard for reasoning traces.** Tool calling converged: every vendor now does roughly the same
thing in a different syntax, so a neutral type is possible. Reasoning has not converged, and the
opacity is partly deliberate — providers do not want raw chains of thought treated as a stable API.
An abstraction layer can transport these blocks but cannot meaningfully normalise them.

**Model-level, not vendor-level, divergence.** The old assumption that one adapter covers one vendor
is weakening. Thinking retention differs between models from the same vendor; so do caching rules and
tool-calling quirks. A `Provider` keyed on vendor with a `model` string may be the wrong seam.

**OpenAI-compatible is a spectrum, not a contract.** vLLM, Ollama, gateways and hosted clones each
implement a different subset, and some still emit tool calls as text to be parsed. There is no
conformance suite, so "OpenAI-compatible" tells you almost nothing about whether a given agent loop
will work — which matters directly for the
[self-hosted arm of the benchmark](../guides/self-hosted-models.md).

**Determinism is not on offer.** `FakeProvider` gives the harness reproducibility; real providers do
not, even at temperature 0, because of batching and hardware non-determinism. Every claim about
[eval determinism](evaluation.md) is therefore a claim about distributions, not about identical
outputs, and saying otherwise is a small lie that gets discovered late.
