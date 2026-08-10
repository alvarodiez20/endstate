"""Filesystem tools."""

from __future__ import annotations

from typing import Any

from endstate.agent.tools.base import Tool, ToolContext, ToolError


class ReadTool(Tool):
    name = "read"
    description = "Read a UTF-8 text file relative to the working directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = ctx.resolve(arguments["path"])
        if not path.is_file():
            raise ToolError(f"no such file: {arguments['path']}")
        return ctx.truncate(path.read_text(encoding="utf-8", errors="replace"))


class WriteTool(Tool):
    name = "write"
    description = "Write a UTF-8 text file, creating parent directories as needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = ctx.resolve(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = arguments["content"]
        path.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {arguments['path']}"


class EditTool(Tool):
    name = "edit"
    description = "Replace an exact string in a file. Fails if the string is absent or ambiguous."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
            },
            "required": ["path", "old", "new"],
        }

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = ctx.resolve(arguments["path"])
        if not path.is_file():
            raise ToolError(f"no such file: {arguments['path']}")
        text = path.read_text(encoding="utf-8")
        old = arguments["old"]
        occurrences = text.count(old)
        if occurrences == 0:
            raise ToolError("old string not found")
        if occurrences > 1:
            raise ToolError(f"old string is ambiguous ({occurrences} matches)")
        path.write_text(text.replace(old, arguments["new"], 1), encoding="utf-8")
        return f"edited {arguments['path']}"
