"""Shell tool.

Runs with cwd pinned to the workdir and a hard timeout. This is safe to expose
only because eval runs happen inside a disposable container; outside one, the
permission policy is the thing standing between the agent and your laptop.
"""

from __future__ import annotations

import subprocess
from typing import Any

from endstate.agent.tools.base import Tool, ToolContext, ToolError


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command in the working directory. Returns stdout and stderr."

    # `git commit`, `>> log`, `pip install`: a shell command is the general case
    # of a side effect, so resume must not replay one whose outcome it lost.
    idempotent = False

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        command = arguments["command"]
        try:
            proc = subprocess.run(  # noqa: S602 - intentional, confined to the sandbox
                command,
                shell=True,
                cwd=str(ctx.workdir),
                capture_output=True,
                text=True,
                timeout=ctx.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"command timed out after {ctx.timeout_s}s") from exc

        parts = [f"exit_code: {proc.returncode}"]
        if proc.stdout:
            parts.append(f"stdout:\n{proc.stdout}")
        if proc.stderr:
            parts.append(f"stderr:\n{proc.stderr}")
        return ctx.truncate("\n".join(parts))
