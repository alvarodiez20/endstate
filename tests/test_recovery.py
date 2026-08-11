"""Recovery: a killed run, resumed, reaches the same end state.

The assertions here are all on the sandbox rather than on the transcript, for
the same reason the eval graders will be: two runs can reach an identical
filesystem via different conversations, and an identical conversation can leave
different files. Only the end state answers the question.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from endstate.agent.loop import AgentLoop
from endstate.agent.session import Session, SessionStore
from endstate.agent.tools import default_tools
from endstate.agent.tools.base import Tool, ToolContext
from endstate.providers.fake import FakeProvider
from endstate.types import Message, Response, StopReason, ToolCall, Usage

# Six side effects across three steps, with an uneven first batch on purpose:
# a kill can then land on the *third* call of a batch, where the result is
# persisted by rewriting the tool message rather than by creating it. A suite
# built only from two-call batches passes even if that rewrite never happens.
BATCHES = [["a.txt", "b.txt", "c.txt"], ["d.txt", "e.txt"], ["f.txt"]]
TOTAL_CALLS = sum(len(b) for b in BATCHES)


class Crash(RuntimeError):
    """Stands in for the process dying. Deliberately not a ToolError."""


class CrashAt(Tool):
    """Wraps a tool and crashes on the nth invocation.

    `after=False` crashes before the side effect — the honest kill, where the
    work never happened. `after=True` crashes once the side effect has landed
    but before anything is recorded, which is the window no harness can close.
    """

    def __init__(self, inner: Tool, index: int | None, *, after: bool = False) -> None:
        self.inner = inner
        self.name = inner.name
        self.description = inner.description
        self.index = index
        self.after = after
        self.calls = 0

    @property
    def parameters(self) -> dict[str, Any]:
        return self.inner.parameters

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        seen = self.calls
        self.calls += 1
        if self.index is not None and seen == self.index and not self.after:
            raise Crash(f"killed before call {seen}")
        output = self.inner.run(arguments, ctx)
        if self.index is not None and seen == self.index and self.after:
            raise Crash(f"killed after call {seen}")
        return output


def script() -> list[Response]:
    responses: list[Response] = []
    for step, names in enumerate(BATCHES):
        responses.append(
            Response(
                message=Message(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id=f"s{step}-{i}",
                            name="write",
                            arguments={"path": name, "content": name},
                        )
                        for i, name in enumerate(names)
                    ],
                ),
                usage=Usage(input_tokens=10, output_tokens=5),
                stop_reason=StopReason.TOOL_USE,
                model="fake-1",
            )
        )
    responses.append(
        Response(
            message=Message(role="assistant", content="done"),
            usage=Usage(input_tokens=10, output_tokens=5),
            stop_reason=StopReason.END_TURN,
            model="fake-1",
        )
    )
    return responses


def tools_crashing_at(index: int | None, *, after: bool = False) -> tuple[list[Tool], CrashAt]:
    tools = default_tools()
    wrapper = CrashAt(next(t for t in tools if t.name == "write"), index, after=after)
    return [wrapper if t.name == "write" else t for t in tools], wrapper


def loop_for(
    session: Session, workdir: Path, tools: list[Tool], responses: list[Response]
) -> AgentLoop:
    return AgentLoop(
        provider=FakeProvider(responses),
        tools=tools,
        tool_context=ToolContext(workdir=workdir),
        session=session,
    )


def remaining_script(session: Session) -> list[Response]:
    """The responses the model has not produced yet.

    A resumed FakeProvider must not replay from the start: the model has already
    emitted one response per assistant message on record.
    """
    produced = sum(1 for m in session.messages if m.role == "assistant")
    return script()[produced:]


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.sqlite3")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    box = tmp_path / "sandbox"
    box.mkdir()
    return box


def uninterrupted(store: SessionStore, sandbox: Path) -> str:
    tools, _ = tools_crashing_at(None)
    result = loop_for(store.create(), sandbox, tools, script()).run("write the files")
    return result.tree_hash()


def test_uninterrupted_run_writes_everything(store: SessionStore, sandbox: Path) -> None:
    uninterrupted(store, sandbox)
    expected = sorted(name for batch in BATCHES for name in batch)
    assert sorted(p.name for p in sandbox.iterdir()) == expected


@pytest.mark.parametrize("kill_at", range(TOTAL_CALLS))
def test_resume_reaches_the_same_end_state(tmp_path: Path, kill_at: int) -> None:
    reference_store = SessionStore(tmp_path / "ref.sqlite3")
    reference_box = tmp_path / "reference"
    reference_box.mkdir()
    expected = uninterrupted(reference_store, reference_box)

    store = SessionStore(tmp_path / "killed.sqlite3")
    box = tmp_path / "killed"
    box.mkdir()
    session = store.create()

    tools, _ = tools_crashing_at(kill_at)
    with pytest.raises(Crash):
        loop_for(session, box, tools, script()).run("write the files")

    resumed = store.resume(session.id)
    survivors, _ = tools_crashing_at(None)
    result = loop_for(resumed, box, survivors, remaining_script(resumed)).resume()

    assert result.tree_hash() == expected


@pytest.mark.parametrize("kill_at", range(TOTAL_CALLS))
def test_resume_is_idempotent_when_the_side_effect_already_landed(
    tmp_path: Path, kill_at: int
) -> None:
    """The irreducible window: the write happened, nothing recorded it.

    Re-running the call is the only option, so the harness converges exactly when
    the tool is idempotent. A tool that appends rather than overwrites would not
    converge here, which is why that distinction is worth knowing about.
    """
    reference_store = SessionStore(tmp_path / "ref.sqlite3")
    reference_box = tmp_path / "reference"
    reference_box.mkdir()
    expected = uninterrupted(reference_store, reference_box)

    store = SessionStore(tmp_path / "killed.sqlite3")
    box = tmp_path / "killed"
    box.mkdir()
    session = store.create()

    tools, _ = tools_crashing_at(kill_at, after=True)
    with pytest.raises(Crash):
        loop_for(session, box, tools, script()).run("write the files")

    resumed = store.resume(session.id)
    survivors, _ = tools_crashing_at(None)
    result = loop_for(resumed, box, survivors, remaining_script(resumed)).resume()

    assert result.tree_hash() == expected


def test_completed_calls_are_on_disk_before_the_batch_finishes(
    store: SessionStore, sandbox: Path
) -> None:
    """A kill mid-batch records every call that finished, not just the first.

    Crashing on the third call is the case that matters: the first result
    creates the tool message, and only the second proves results are rewritten
    into it as they land rather than written once when the batch ends.
    """
    session = store.create()
    tools, _ = tools_crashing_at(2)  # third call of the first batch
    with pytest.raises(Crash):
        loop_for(session, sandbox, tools, script()).run("write the files")

    reloaded = store.resume(session.id)
    tool_messages = [m for m in reloaded.messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert [r.call_id for r in tool_messages[0].tool_results] == ["s0-0", "s0-1"]
    assert (sandbox / "a.txt").exists()
    assert (sandbox / "b.txt").exists()


def test_resume_leaves_no_orphan_tool_calls(store: SessionStore, sandbox: Path) -> None:
    """Every requested call ends up with a matching result.

    An assistant message carrying tool_calls with no tool_results is malformed
    under both the Anthropic and OpenAI contracts, so a resumed session that
    still contained one could not be sent back to a provider at all.
    """
    session = store.create()
    tools, _ = tools_crashing_at(2)
    with pytest.raises(Crash):
        loop_for(session, sandbox, tools, script()).run("write the files")

    resumed = store.resume(session.id)
    survivors, _ = tools_crashing_at(None)
    result = loop_for(resumed, sandbox, survivors, remaining_script(resumed)).resume()

    requested = {c.id for m in result.messages for c in m.tool_calls}
    answered = {r.call_id for m in result.messages for r in m.tool_results}
    assert requested == answered


def test_resume_finishes_the_batch_before_a_new_prompt_is_added(
    store: SessionStore, sandbox: Path
) -> None:
    """`run()` on an interrupted session settles first, then takes the prompt."""
    session = store.create()
    tools, _ = tools_crashing_at(1)
    with pytest.raises(Crash):
        loop_for(session, sandbox, tools, script()).run("write the files")

    resumed = store.resume(session.id)
    survivors, _ = tools_crashing_at(None)
    result = loop_for(resumed, sandbox, survivors, remaining_script(resumed)).run("carry on")

    roles = [m.role for m in result.messages]
    # The outstanding call is answered before the new instruction arrives.
    assert roles.index("tool") < roles.index("user", 1)
    assert (sandbox / "b.txt").exists()


def test_resume_without_a_session_raises(sandbox: Path) -> None:
    loop = AgentLoop(
        provider=FakeProvider([]),
        tools=default_tools(),
        tool_context=ToolContext(workdir=sandbox),
    )
    with pytest.raises(ValueError, match="requires a session"):
        loop.resume()


def test_nothing_pending_resumes_cleanly(store: SessionStore, sandbox: Path) -> None:
    session = store.create()
    loop_for(session, sandbox, default_tools(), script()).run("write the files")

    reloaded = store.resume(session.id)
    result = loop_for(
        reloaded,
        sandbox,
        default_tools(),
        [
            Response(
                message=Message(role="assistant", content="nothing left"),
                usage=Usage(),
                stop_reason=StopReason.END_TURN,
                model="fake-1",
            )
        ],
    ).resume()
    assert result.final_text == "nothing left"


def test_run_result_without_workdir_cannot_hash() -> None:
    from endstate.agent.loop import RunResult

    with pytest.raises(ValueError, match="no workdir"):
        RunResult().tree_hash()


def test_checkpoints_survive_sigkill(tmp_path: Path) -> None:
    """The durability claim itself, against a real killed process.

    Everything above simulates the kill in-process, which tests reconciliation
    but takes SQLite's word for the write having landed. This one does not.
    """
    db = tmp_path / "sessions.sqlite3"
    program = textwrap.dedent(
        f"""
        import os, signal
        from endstate.agent.session import SessionStore
        from endstate.types import Message

        store = SessionStore({str(db)!r})
        session = store.create(model="fake-1")
        session.append(Message(role="user", content="do the thing"))
        session.append(Message(role="assistant", content="working"))
        os.kill(os.getpid(), signal.SIGKILL)
        """
    )
    completed = subprocess.run([sys.executable, "-c", program], capture_output=True)
    assert completed.returncode == -signal.SIGKILL, completed.stderr.decode()

    sessions = SessionStore(db).list_sessions()
    assert len(sessions) == 1
    restored = SessionStore(db).resume(sessions[0])
    assert [m.content for m in restored.messages] == ["do the thing", "working"]
