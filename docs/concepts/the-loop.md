# The loop

Everything an agent does happens inside one `for` loop. This page walks through it line by line,
because every other concept in these docs attaches to a specific point in it.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/the-loop.html"
          height="570" loading="lazy" title="The agent loop, step by step"></iframe>
</div>

## The shape

Strip out the bookkeeping and the whole thing is this:

```python
for step in range(max_steps):
    fitted = context.fit(messages)          # (1)!
    response = provider.complete(fitted, tools)
    messages.append(response.message)       # (2)!

    if not response.message.tool_calls:     # (3)!
        break

    results = []
    for call in response.message.tool_calls:
        decision, reason = policy.check(call.name, call.arguments)  # (4)!
        if decision is not Decision.ALLOW:
            results.append(denied(call, reason))
            continue
        results.append(run(call))           # (5)!

    messages.append(Message(role="tool", tool_results=results))  # (6)!
```

1.  **Context budgeting.** The full history may not fit in the window. What gets sent is not what
    you have. See [Context and compaction](context-and-compaction.md).
2.  **Persistence point.** In the real implementation this is `_record()`, which appends *and*
    checkpoints. See [Durability](durability.md).
3.  **The exit condition.** No tool calls means the model is done talking. This is the only clean
    way out; everything else is a limit being hit.
4.  **The permission check.** Before the tool runs, not after. See [Permissions](permissions.md).
5.  **The side effect.** This is the only line that changes the world.
6.  **Results go back as one message,** and the loop goes round again with the model now able to see
    what happened.

The real version is in
[`agent/loop.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/loop.py).
It is longer only because it also records usage, tracks denials, opens trace spans, and handles
unknown tools.

## Why a loop at all

A single model call cannot do multi-step work, because the model has no way to observe the result of
its own suggestion. It can *write* `pytest -q`, but it cannot know the exit code. The loop exists to
close that gap: the model proposes, the harness executes, the result re-enters the conversation, and
the model gets to react to reality instead of to its own prediction of reality.

That is the entire mechanism. "Agency" is this feedback edge and nothing more.

## The three ways a run ends

This distinction matters more than it looks, and it is why `StopReason` is a real enum
([`types.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/types.py)) rather than
a boolean:

| Stop reason | What happened | Is it a success? |
| --- | --- | --- |
| `END_TURN` | The model stopped asking for tools | Maybe — it finished, or it gave up eloquently |
| `MAX_STEPS` | The loop hit its ceiling | No, but the work so far is still on disk |
| `MAX_TOKENS` | The provider truncated the response | No, and the last message may be half-written |
| `BUDGET_EXCEEDED` | Token budget exhausted | No |
| `ERROR` | The provider or harness failed | No |

Note what is missing: there is no `SUCCESS`. The loop cannot tell you whether the agent did the job,
because the loop only sees messages. Only a [grader](evaluation.md) looking at the sandbox afterwards
can answer that. `END_TURN` means "stopped talking," which is not at all the same as "succeeded" —
and conflating those two is the single most common way agent metrics end up lying.

## Why `max_steps` is not optional

A model that gets a confusing tool result will often try the same thing again. And again. Without a
ceiling, a run is unbounded in both wall-clock and money, and the failure mode is not a crash — it is
a slow, expensive, plausible-looking loop that never terminates.

`max_steps` defaults to 25. It is the cheapest safety property in the whole system.

## What the loop deliberately does not do

- **It does not retry.** A failed tool returns its error to the model as a tool result, and the model
  decides what to do. Retry logic in the harness competes with the model's own recovery behaviour and
  makes runs non-reproducible.
- **It does not parse the model's prose for intent.** Only structured `tool_calls` cause side
  effects. If the model writes "I will now delete the config" in its message text, nothing happens.
- **It does not hide tool errors.** An error is a result like any other. Agents recover from errors
  they can see and fail silently on ones they can't.

## Where to go next

The loop is the skeleton. Every remaining page is one of the numbered annotations above:

- ① is [Context and compaction](context-and-compaction.md)
- ② is [Durability](durability.md)
- ④ is [Permissions](permissions.md)
- ⑤ is [Tools and the sandbox](tools-and-sandbox.md)

Start with [Messages and providers](messages-and-providers.md), though — it is the type system the
rest of it is written in.
