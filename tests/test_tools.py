from pathlib import Path

import pytest

from endstate.agent.tools import BashTool, EditTool, GlobTool, GrepTool, ReadTool, WriteTool
from endstate.agent.tools.base import ToolContext, ToolError


def test_read_returns_contents(ctx: ToolContext) -> None:
    assert "hello world" in ReadTool().run({"path": "hello.txt"}, ctx)


def test_read_missing_file_raises(ctx: ToolContext) -> None:
    with pytest.raises(ToolError):
        ReadTool().run({"path": "nope.txt"}, ctx)


@pytest.mark.parametrize("escape", ["../outside.txt", "../../etc/passwd", "pkg/../../x"])
def test_paths_cannot_escape_the_workdir(ctx: ToolContext, escape: str) -> None:
    with pytest.raises(ToolError, match="escapes"):
        ctx.resolve(escape)


def test_write_creates_parents(ctx: ToolContext, workdir: Path) -> None:
    WriteTool().run({"path": "a/b/c.txt", "content": "x"}, ctx)
    assert (workdir / "a" / "b" / "c.txt").read_text() == "x"


def test_edit_replaces_unique_string(ctx: ToolContext, workdir: Path) -> None:
    EditTool().run({"path": "pkg/mod.py", "old": "a - b", "new": "a + b"}, ctx)
    assert "a + b" in (workdir / "pkg" / "mod.py").read_text()


def test_edit_refuses_ambiguous_match(ctx: ToolContext, workdir: Path) -> None:
    (workdir / "dup.txt").write_text("x\nx\n")
    with pytest.raises(ToolError, match="ambiguous"):
        EditTool().run({"path": "dup.txt", "old": "x", "new": "y"}, ctx)


def test_glob_lists_matches(ctx: ToolContext) -> None:
    assert "pkg/mod.py" in GlobTool().run({"pattern": "**/*.py"}, ctx)


def test_grep_finds_lines(ctx: ToolContext) -> None:
    out = GrepTool().run({"pattern": "def add"}, ctx)
    assert "pkg/mod.py:1:" in out


def test_bash_runs_in_workdir(ctx: ToolContext) -> None:
    out = BashTool().run({"command": "ls"}, ctx)
    assert "hello.txt" in out and "exit_code: 0" in out


def test_bash_times_out(workdir: Path) -> None:
    tight = ToolContext(workdir=workdir, timeout_s=0.2)
    with pytest.raises(ToolError, match="timed out"):
        BashTool().run({"command": "sleep 5"}, tight)


def test_output_is_truncated(workdir: Path) -> None:
    small = ToolContext(workdir=workdir, max_output_chars=50)
    assert "truncated" in small.truncate("y" * 500)
