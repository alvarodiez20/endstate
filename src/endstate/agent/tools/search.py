"""Search tools."""

from __future__ import annotations

import re
from typing import Any

from endstate.agent.tools.base import Tool, ToolContext, ToolError


class GlobTool(Tool):
    name = "glob"
    description = "List files matching a glob pattern, relative to the working directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        root = ctx.workdir.resolve()
        matches = sorted(str(p.relative_to(root)) for p in root.glob(arguments["pattern"]))
        return ctx.truncate("\n".join(matches) if matches else "(no matches)")


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents for a regex. Returns path:line:text."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "glob": {"type": "string", "default": "**/*"},
            },
            "required": ["pattern"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        try:
            regex = re.compile(arguments["pattern"])
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from exc

        root = ctx.workdir.resolve()
        hits: list[str] = []
        for path in sorted(root.glob(arguments.get("glob", "**/*"))):
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                if regex.search(line):
                    hits.append(f"{path.relative_to(root)}:{number}:{line.strip()}")
        return ctx.truncate("\n".join(hits) if hits else "(no matches)")
