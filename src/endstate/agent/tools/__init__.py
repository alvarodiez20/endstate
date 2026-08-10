from endstate.agent.tools.base import Tool, ToolContext, ToolError
from endstate.agent.tools.fs import EditTool, ReadTool, WriteTool
from endstate.agent.tools.search import GlobTool, GrepTool
from endstate.agent.tools.shell import BashTool


def default_tools() -> list[Tool]:
    return [ReadTool(), WriteTool(), EditTool(), GlobTool(), GrepTool(), BashTool()]


__all__ = [
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ReadTool",
    "Tool",
    "ToolContext",
    "ToolError",
    "WriteTool",
    "default_tools",
]
