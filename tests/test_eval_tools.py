"""The tool set an eval agent gets."""

from __future__ import annotations

from pathlib import Path

from endstate.agent.tools.base import ToolContext
from endstate.evals.sandbox import ExecResult, LocalSandbox, Sandbox
from endstate.evals.tools import SandboxBashTool, sandbox_tools


class RecordingSandbox(Sandbox):
    """A sandbox that answers with a canned result and remembers the ask."""

    def __init__(self, fixture: Path, root: Path, result: ExecResult) -> None:
        super().__init__(fixture, root)
        self.result = result
        self.commands: list[tuple[str, float | None]] = []

    def run(self, command: str, *, timeout_s: float | None = None) -> ExecResult:
        self.commands.append((command, timeout_s))
        return self.result


def fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    repo.mkdir()
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    return repo


def test_bash_is_replaced_and_the_rest_is_not(tmp_path: Path) -> None:
    with LocalSandbox(fixture(tmp_path), tmp_path / "box") as sandbox:
        tools = {t.name: t for t in sandbox_tools(sandbox)}
    assert isinstance(tools["bash"], SandboxBashTool)
    assert {"read", "write", "edit", "glob", "grep", "bash"} <= set(tools)


def test_the_shell_crosses_into_the_sandbox(tmp_path: Path) -> None:
    with LocalSandbox(fixture(tmp_path), tmp_path / "box") as sandbox:
        tool = SandboxBashTool(sandbox)
        output = tool.run({"command": "cat a.txt"}, ToolContext(workdir=sandbox.workdir))
    assert "exit_code: 0" in output
    assert "hello" in output


def test_both_streams_are_reported(tmp_path: Path) -> None:
    result = ExecResult(command="x", exit_code=2, stdout="out", stderr="err")
    box = RecordingSandbox(fixture(tmp_path), tmp_path / "box", result)
    output = SandboxBashTool(box).run({"command": "x"}, ToolContext(workdir=tmp_path))
    assert "exit_code: 2" in output
    assert "stdout:\nout" in output
    assert "stderr:\nerr" in output


def test_a_timeout_is_reported_rather_than_raised(tmp_path: Path) -> None:
    """The model can shorten a command; it cannot recover from an exception."""
    timed_out = ExecResult(command="x", exit_code=124, timed_out=True)
    box = RecordingSandbox(fixture(tmp_path), tmp_path / "box", timed_out)
    output = SandboxBashTool(box).run(
        {"command": "sleep 999"}, ToolContext(workdir=tmp_path, timeout_s=5.0)
    )
    assert "timed out after 5.0s" in output
    assert box.commands == [("sleep 999", 5.0)]


def test_the_tool_declares_itself_non_idempotent(tmp_path: Path) -> None:
    box = RecordingSandbox(fixture(tmp_path), tmp_path / "box", ExecResult("x", 0))
    assert SandboxBashTool(box).idempotent is False


def test_a_missing_fixture_tree_reads_as_empty(tmp_path: Path) -> None:
    box = RecordingSandbox(tmp_path / "nowhere", tmp_path / "box", ExecResult("x", 0))
    assert box.end_state_files() == {}
