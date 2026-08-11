# Tools and the sandbox

A tool is the only way an agent affects anything. Everything else it does is producing text. This
makes the tool layer the security boundary of the entire system, and it deserves to be treated like
one.

## What a tool is

Three things: a name, a JSON Schema describing its arguments, and a function.

```python
class Tool(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool arguments."""

    @abstractmethod
    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        """Execute and return output for the model. Raise ToolError on failure."""
```

The schema is sent to the model so it knows how to call the tool. The function is what actually runs.
The harness ships six: `read`, `write`, `edit`, `glob`, `grep`, `bash`.

Source:
[`agent/tools/`](https://github.com/alvarodiez20/endstate/tree/main/src/endstate/agent/tools).

!!! note "The description is a prompt"

    A tool's `description` goes into the model's context on every single call. It is prompt
    engineering wearing a docstring costume, and it is billed accordingly. Vague descriptions produce
    tools the model uses at the wrong moment; verbose ones cost tokens on every step of every run.

## The confinement problem

Give a model a `read` tool and eventually it will ask for `../../../../etc/passwd`. Not from malice —
from a plausible chain of reasoning about where a config file might live. Give it a `write` tool and
the same reasoning can put a file somewhere you very much did not want a file.

The naive fix is a check inside each tool. That fails for a boring reason: there are six tools now
and there will be twenty later, the check is subtle, and the twelfth one will get it wrong.

## The fix: one boundary, one place

Path confinement lives in `ToolContext`, which every tool receives and none of them can bypass:

```python
@dataclass(frozen=True)
class ToolContext:
    workdir: Path
    timeout_s: float = 30.0
    max_output_chars: int = 20_000

    def resolve(self, relative: str) -> Path:
        """Resolve a path inside the workdir, refusing anything that escapes it."""
        root = self.workdir.resolve()
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ToolError(f"path {relative!r} escapes the working directory")
        return candidate
```

Source:
[`agent/tools/base.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/tools/base.py).

The critical detail is `.resolve()` on *both* sides before comparing. Resolution happens first, then
containment is checked on the resolved result. That is what makes `../` traversal, absolute paths and
symlinks pointing outside the tree all fail the same way — the string never gets a vote, only the
real path does. A check written against the raw string would pass `foo/../../etc/passwd` on the
grounds that it starts with `foo/`.

There is exactly one function to audit, and the test suite attacks it directly with escape attempts.

## Two limits that are not about security

`ToolContext` carries two other fields, and both exist because of the same failure mode.

**`timeout_s`.** A shell command that hangs hangs the agent. Something interactive, something waiting
on a network that will never answer — without a timeout the run is stuck forever, holding whatever it
holds.

**`max_output_chars`.** A `grep` across a large repo can return megabytes. That output goes straight
into the model's context, where it will blow the budget, trigger a
[compaction](context-and-compaction.md) that throws away the actual task, and cost real money on the
way. Output is truncated with an explicit marker:

```
... [48213 chars truncated]
```

The marker matters. Silently truncated output teaches the model that a file ends where it does not,
and it will confidently act on the half it can see.

## `bash` is the honest one

The `bash` tool runs arbitrary shell commands with `cwd` pinned to the workdir. There is no way to
make that safe by inspection, and the module says so:

> Runs with cwd pinned to the workdir and a hard timeout. This is safe to expose only because eval
> runs happen inside a disposable container; outside one, the permission policy is the thing standing
> between the agent and your laptop.

Note that `cwd` pinning is not confinement — a command can still `cd /` on its own. This is why
defence is layered rather than singular:

1. **The sandbox** — one disposable container per eval task, network off by default. Real isolation
   that does not depend on getting a regex right. *(Planned for v0.1.0.)*
2. **[The permission policy](permissions.md)** — the deny-list that runs before the command does.
3. **`ToolContext.resolve()`** — path confinement for every tool that is not `bash`.

Layer 1 is the only one that is actually a boundary. Layers 2 and 3 are what you have when you are
running on a laptop rather than in a container, which is most of the time during development. Be
clear-eyed about which one you are relying on.

## Tools return strings

`run()` returns `str`, not a rich object, because the return value's only destination is a model's
context window. Anything structured has to be serialised eventually, and doing it at the boundary
means there is one representation of a tool result rather than one per tool.

The same applies to errors. `ToolError` is caught by the loop and converted into a `ToolResult` with
`is_error=True` — it never propagates out and kills the run. A tool failing is a normal event in an
agent's life; the model reads the error and tries something else, which is precisely the behaviour
you want and precisely what an uncaught exception would deny you.

## Writing your own

See [Write a custom tool](../guides/custom-tool.md) for the practical version.
