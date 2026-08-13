"""The tool set an eval agent gets.

The split is worth being explicit about, because it is the one place where the
container boundary is not the whole story.

*Shell runs inside the container.* `SandboxBashTool` replaces `BashTool`, so a
command the model asks for is executed by the sandbox backend rather than by the
host's shell. Under `DockerSandbox` that is a `docker exec`; under
`LocalSandbox` it is a subprocess on this machine, which is exactly why that
backend is for development rather than for published numbers.

*File tools run host-side on the bind mount.* They are already confined to the
working directory, and the mount is the same bytes the container sees, so there
is nothing to gain from routing them through the container and a lot of
`cat`-and-`base64` plumbing to lose.
"""

from __future__ import annotations

from typing import Any

from endstate.agent.tools import default_tools
from endstate.agent.tools.base import Tool, ToolContext
from endstate.evals.sandbox import Sandbox


class SandboxBashTool(Tool):
    """`bash`, executed by the sandbox rather than by the host."""

    name = "bash"
    description = "Run a shell command in the working directory. Returns stdout and stderr."
    idempotent = False

    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        result = self.sandbox.run(arguments["command"], timeout_s=ctx.timeout_s)
        if result.timed_out:
            return ctx.truncate(f"exit_code: {result.exit_code}\ntimed out after {ctx.timeout_s}s")
        parts = [f"exit_code: {result.exit_code}"]
        if result.stdout:
            parts.append(f"stdout:\n{result.stdout}")
        if result.stderr:
            parts.append(f"stderr:\n{result.stderr}")
        return ctx.truncate("\n".join(parts))


def sandbox_tools(sandbox: Sandbox) -> list[Tool]:
    """The default tool set with `bash` rerouted through the sandbox."""
    bash = SandboxBashTool(sandbox)
    return [bash if tool.name == "bash" else tool for tool in default_tools()]
