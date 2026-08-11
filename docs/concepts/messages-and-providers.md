# Messages and providers

Before anything interesting can happen, you need a definition of "conversation" that survives contact
with more than one vendor. This is unglamorous and it is where a surprising number of agent codebases
acquire a permanent limp.

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
