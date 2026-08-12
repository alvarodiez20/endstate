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

## Why long runs fail so much more than short ones

The loop is the same code at step 3 and at step 300. Success rate is not.

METR measures this as a model's **time horizon**: the length of task — in human-expert minutes — that
an agent completes with 50% reliability. The 2025 result was that this length had been
[doubling roughly every seven months](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/)
over the preceding six years; METR now maintains a
[live version of the chart](https://metr.org/time-horizons/), which is the one to check rather than
any figure quoted here. It is a capability metric rather than a harness metric, but it is the number
that tells you how ambitious a task your loop can be pointed at.

The more useful result for a harness author is Toby Ord's re-reading of that data. Fitting the same
task suite with the simplest possible model — a **constant probability of failing during each minute
of work** — reproduces it well, which implies success decays *exponentially* with task length and
that each agent has a characteristic
[half-life](https://arxiv.org/abs/2505.05115).

If that model holds, two things follow directly for the code above:

- **Reliability per step is the whole game.** A small improvement in per-step failure rate compounds
  across the run. This is why an unhelpful tool error, a truncated file read, or a lost task
  statement matter far more than they look: each is a bump in the hazard rate, paid on every step.
- **There is no length at which a long run becomes safe.** You cannot fix a long-horizon failure by
  adding steps. You fix it by lowering the per-step failure rate or by shortening the task.

Ord is explicit that whether this generalises beyond that one task suite is unknown. Treat it as a
sharp hypothesis rather than a law — but a hypothesis that predicts the right shape of failure.

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

## What the loop is missing: reasoning state

The five-line loop above assumes a turn is text plus tool calls. That was true when it was written
and it is no longer quite true.

Current models emit **thinking** as a distinct kind of content, and with tool use they can think
*between* tool calls rather than only before them — Anthropic calls this
[interleaved thinking](https://platform.claude.com/docs/en/build-with-claude/thinking#interleaved-thinking).
The harness consequence is not philosophical, it is mechanical: those blocks have to be handed back
on the next call, unmodified, or the provider rejects the request or the model loses its own train
of thought mid-task.

Note what that does to the annotations above. Step ⑥ — "results go back and the loop goes round
again" — was the only place reasoning happened between tool calls in the original design. Now some of
it happens inside the provider's turn, in content the harness must transport but cannot inspect.

`Message` in this harness has no field for that. It is the most significant thing the type model
does not represent, and it is discussed where it belongs, on
[Messages and providers](messages-and-providers.md).

## Open problems

Things the loop does not solve, and that nobody has cleanly solved:

**Knowing when it is done.** `END_TURN` means "stopped asking for tools." There is no reliable
signal for "and the work is correct," which is the entire reason this project grades the
[end state](evaluation.md) instead. Self-verification — asking the model whether it finished — fails
for the obvious reason: the same confusion that produced the wrong answer produces the wrong
self-assessment.

**Whether a step is the right unit.** `max_steps` bounds iterations, not effort. One step can read a
40,000-token file; another can echo a string. Budgeting in tokens or in wall-clock is more honest and
harder to reason about, and no consensus exists on which ceiling should be primary.

**Where recovery should live.** This harness pushes all retry behaviour to the model on the grounds
that harness retries compete with the model's own recovery and destroy reproducibility. That is a
defensible position, not a settled one; production harnesses commonly do both, and there is no
public evidence saying which wins.

**Whether the loop should be a loop at all.** A visible alternative is to let the model write code
that orchestrates several tool calls at once, so control flow executes in a sandbox rather than a
round-trip at a time — see [MCP and tool discovery](mcp-and-tool-discovery.md). That collapses steps
and breaks the property that every side effect is preceded by a permission check the harness made.
Nobody has published a convincing answer on how to keep both.

## Where to go next

The loop is the skeleton. Every remaining page is one of the numbered annotations above:

- ① is [Context and compaction](context-and-compaction.md)
- ② is [Durability](durability.md)
- ④ is [Permissions](permissions.md)
- ⑤ is [Tools and the sandbox](tools-and-sandbox.md)

Start with [Messages and providers](messages-and-providers.md), though — it is the type system the
rest of it is written in.

The [part two pages](index.md) attach to the same annotations from the outside: ⑤ is also where
[tools arrive from strangers](mcp-and-tool-discovery.md) and where
[untrusted text enters the context window](prompt-injection.md), and ① is where
[skills](skills.md) and [memory](memory.md) would earn their keep.
