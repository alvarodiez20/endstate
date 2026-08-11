# Write a custom tool

A tool is a name, a JSON Schema, and a function.

## The minimum

```python
from typing import Any

from endstate.agent.tools.base import Tool, ToolContext, ToolError


class WordCountTool(Tool):
    name = "word_count"
    description = "Count the words in a file. Returns a single integer."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to the working directory.",
                }
            },
            "required": ["path"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = ctx.resolve(arguments["path"])       # (1)!
        if not path.is_file():
            raise ToolError(f"not a file: {arguments['path']}")   # (2)!
        return str(len(path.read_text().split()))   # (3)!
```

1.  **Always resolve through `ctx`.** This is the only thing standing between the model and
    `../../.ssh/id_rsa`. Never build a path with `Path(arguments["path"])`.
2.  **Raise `ToolError` for expected failures.** The loop catches it and returns it to the model as a
    tool result with `is_error=True`. The run continues and the model can react.
3.  **Return a string.** It goes into a context window, so it gets serialised either way.

## Use it

```python
from endstate.agent.loop import AgentLoop
from endstate.agent.tools import default_tools

loop = AgentLoop(
    provider=provider,
    tools=[*default_tools(), WordCountTool()],
    tool_context=ToolContext(workdir=Path("./sandbox")),
)
```

## The four rules

### 1. Resolve every path through `ctx.resolve()`

Path confinement lives in one place so there is one place to audit. A tool that opens a raw path has
quietly removed itself from that guarantee. See
[Tools and the sandbox](../concepts/tools-and-sandbox.md).

### 2. Truncate anything unbounded

If your tool can return a lot, cap it:

```python
return ctx.truncate(output)
```

Untruncated output blows the context budget, triggers a
[compaction](../concepts/context-and-compaction.md) that may discard the task statement, and costs
real money. `ctx.truncate()` appends an explicit `... [N chars truncated]` marker — silent truncation
teaches the model that a file ends where it does not.

### 3. Write the description like a prompt, because it is one

`description` is sent to the model on **every call of every step**. It is the only thing telling the
model when to reach for this tool. Two failure modes:

- Too vague — the tool gets used at the wrong moment, or never.
- Too verbose — you pay for those tokens on every step of every run.

Say what it does, what it returns, and when to use it instead of the obvious alternative. One or two
sentences.

### 4. Name arguments for a reader who cannot see your code

The model only sees the schema. `path` is obvious; `p` is a guess. Add a `description` to any
parameter whose meaning is not clear from its name.

## Add a permission rule if it can do damage

A new tool is unregulated until the policy mentions it — and with a default-deny policy it will be
*denied*, which is the correct failure direction but will confuse you for ten minutes if you forget.

```python
from endstate.agent.permissions import Decision, Rule, default_policy

policy = default_policy()
policy.rules.insert(0, Rule(
    tool="word_count",
    decision=Decision.ALLOW,
))
```

Order matters — see [Write a permission policy](permission-policy.md).

## Test it without a network

Tools are plain objects. No provider, no mocking:

```python
def test_word_count(tmp_path):
    (tmp_path / "a.txt").write_text("one two three")
    ctx = ToolContext(workdir=tmp_path)
    assert WordCountTool().run({"path": "a.txt"}, ctx) == "3"


def test_word_count_refuses_escape(tmp_path):
    ctx = ToolContext(workdir=tmp_path)
    with pytest.raises(ToolError):
        WordCountTool().run({"path": "../../../etc/passwd"}, ctx)
```

Write the second test for every tool you add. It is three lines and it is the one that catches the
mistake that matters.

To test the tool *in* a loop, use
[`FakeProvider`](../concepts/messages-and-providers.md#fakeprovider-the-most-useful-class-in-the-repo)
with a scripted response that calls it.
