# Tools and the sandbox

A tool is the only way an agent affects anything. Everything else it does is producing text. This
makes the tool layer the security boundary of the entire system, and it deserves to be treated like
one.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/tools-and-sandbox.html"
          height="665" loading="lazy" title="A tool call crossing the sandbox boundary"></iframe>
</div>

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

    Six tools makes this a rounding error. It stops being one the moment tools arrive at runtime by
    the hundred — see [MCP and tool discovery](mcp-and-tool-discovery.md) — and the standard escape
    hatch for knowledge too large to live in a description is [skills](skills.md).

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

!!! note "This ordering is a known production bug class"

    Getting it backwards is not a hypothetical. Anthropic lists it among the gotchas from building
    Claude Cowork's file mounts:
    [symlink resolution has to happen *before* path validation](https://www.anthropic.com/engineering/how-we-contain-claude),
    not after, or a symlink inside an authorised folder can point outside it and escape.

    Validate-then-resolve reads almost identically to resolve-then-validate and is wrong. If you
    write this function yourself, that is the line to review twice.

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

Layering also has a second justification that has nothing to do with the model misbehaving: the text
a tool *returns* can contain instructions. A `read` tool is an untrusted-content channel, and that
turns the container from a convenience into the control. See
[Prompt injection](prompt-injection.md).

## What containment looks like in shipped products

"One disposable container" is not the only shape, and it is worth knowing the alternatives before
committing to it. Anthropic's
[write-up of how it contains Claude](https://www.anthropic.com/engineering/how-we-contain-claude)
describes three, chosen by how much the user can be expected to supervise:

| Pattern | Mechanism | Blast radius | Where it fits |
| --- | --- | --- | --- |
| Ephemeral container | gVisor, server-side, per-session filesystem | Their infrastructure, not your machine | The agent never touches the user's files |
| OS-level sandbox | Seatbelt (macOS) / bubblewrap (Linux); reads allowed, writes confined to the workspace, network denied by default | The local workspace | The user can read bash and judge an exception |
| Sealed VM | Vendor hypervisor, own kernel, only the chosen folder mounted, credentials never enter the guest | The mounted folder | The user cannot be expected to judge anything |

The middle row is the interesting one for a harness like this. It is cheaper than a container — no
image, no daemon, native latency — and it is
[open source](https://github.com/anthropic-experimental/sandbox-runtime), so the boundary is
auditable. Anthropic reports it cut permission prompts by 84%, which is the practical argument: a
real perimeter is what lets you stop asking.

Three lessons from that piece transfer directly, and all three are uncomfortable:

**An egress allowlist is a capability grant, not a destination filter.** Cowork allowed
`api.anthropic.com` because the product cannot function without it. A malicious file in the workspace
carried hidden instructions and an attacker's API key; Claude read other files and uploaded them
through the Files API to the attacker's account. The proxy checked the destination, saw an approved
domain, and passed it. *The sandbox worked perfectly and the data still left.* Every function
reachable through any allowed domain is inside your perimeter.

**The weakest layer is the one you built yourself.** Across every deployment described, gVisor,
seccomp and the hypervisors held. The custom allowlist proxy is what broke — twice. Prefer boring
primitives that have absorbed more adversarial attention than your code ever will.

**Isolation costs you visibility.** Enterprise security teams asked why their endpoint detection
could not see inside the VM; the answer is that the same boundary keeps EDR out. If something is
going to run agents inside your organisation, the observability conversation arrives right behind the
containment one.

## Tools return strings

`run()` returns `str`, not a rich object, because the return value's only destination is a model's
context window. Anything structured has to be serialised eventually, and doing it at the boundary
means there is one representation of a tool result rather than one per tool.

The same applies to errors. `ToolError` is caught by the loop and converted into a `ToolResult` with
`is_error=True` — it never propagates out and kills the run. A tool failing is a normal event in an
agent's life; the model reads the error and tries something else, which is precisely the behaviour
you want and precisely what an uncaught exception would deny you.

## Open problems

**Tool output is an attack surface and inspecting it is expensive.** A `read` of a poisoned README
is indistinguishable, at the type level, from a `read` of a good one. The current best practice is to
route tool results through a small fast classifier before they enter the model's context — which adds
latency to every call and is a probabilistic defence in front of a probabilistic system. The
alternative, checking afterwards, does not work: once a poisoned result has steered the agent into
exfiltrating data, the log shows a successful authorised call and nothing else. See
[Prompt injection](prompt-injection.md).

**Remote tools cannot be pinned.** A locally installed tool is auditable — read the code, pin the
version, know it will not change. A hosted MCP server can change behaviour any time after you
approved it, so install-time trust does not survive. Nobody has a good answer beyond ongoing review
and running unknown tools against fake data first.

**Nobody agrees on what a tool result should be.** This harness returns `str` on the grounds that a
model context is the only destination. Structured returns, resource references and out-of-band
artefacts all have advocates, and the choice constrains what the harness can filter or truncate
without understanding the payload.

**Confinement and usefulness genuinely trade off.** `cwd` pinning is not confinement, network-off
breaks dependency installation, and read-only mounts break the tasks people actually want. Each
tightening removes a class of real work, and there is no principled way to pick the line — only the
observation that the right answer depends on whether a human who can read bash is watching.

## Writing your own

See [Write a custom tool](../guides/custom-tool.md) for the practical version.
