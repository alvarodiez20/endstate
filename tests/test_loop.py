from pathlib import Path

from endstate.agent.context import ContextManager, TokenBudget
from endstate.agent.loop import AgentLoop
from endstate.agent.permissions import Decision, PermissionPolicy, Rule
from endstate.agent.session import SessionStore
from endstate.agent.tools import default_tools
from endstate.agent.tools.base import ToolContext
from endstate.providers.fake import FakeProvider
from endstate.types import Message, Response, StopReason, ToolCall, Usage


def tool_response(name: str, args: dict) -> Response:
    return Response(
        message=Message(
            role="assistant", tool_calls=[ToolCall(id="c1", name=name, arguments=args)]
        ),
        usage=Usage(input_tokens=100, output_tokens=20),
        stop_reason=StopReason.TOOL_USE,
        model="fake-1",
    )


def final(text: str = "finished") -> Response:
    return Response(
        message=Message(role="assistant", content=text),
        usage=Usage(input_tokens=50, output_tokens=10),
        stop_reason=StopReason.END_TURN,
        model="fake-1",
    )


def build(provider: FakeProvider, ctx: ToolContext, **kw) -> AgentLoop:  # type: ignore[no-untyped-def]
    return AgentLoop(provider=provider, tools=default_tools(), tool_context=ctx, **kw)


def test_single_turn_run(ctx: ToolContext) -> None:
    result = build(FakeProvider.saying("hi"), ctx).run("say hi")
    assert result.final_text == "hi"
    assert result.steps == 1
    assert result.stop_reason is StopReason.END_TURN


def test_tool_call_is_executed_and_fed_back(ctx: ToolContext, workdir: Path) -> None:
    provider = FakeProvider([tool_response("write", {"path": "out.txt", "content": "ok"}), final()])
    result = build(provider, ctx).run("write a file")
    assert (workdir / "out.txt").read_text() == "ok"
    assert result.steps == 2
    tool_msgs = [m for m in result.messages if m.role == "tool"]
    assert tool_msgs and not tool_msgs[0].tool_results[0].is_error


def test_usage_accumulates_across_steps(ctx: ToolContext) -> None:
    provider = FakeProvider([tool_response("read", {"path": "hello.txt"}), final()])
    result = build(provider, ctx).run("read it")
    assert result.usage.input_tokens == 150
    assert result.usage.output_tokens == 30


def test_denied_tool_call_is_recorded_and_not_executed(ctx: ToolContext, workdir: Path) -> None:
    provider = FakeProvider([tool_response("bash", {"command": "rm -rf ."}), final()])
    result = build(provider, ctx).run("delete everything")
    assert len(result.denied_calls) == 1
    assert result.denied_calls[0].tool == "bash"
    assert (workdir / "hello.txt").exists()  # sandbox untouched
    assert result.messages[-2].tool_results[0].is_error


def test_tool_errors_are_returned_to_the_model_not_raised(ctx: ToolContext) -> None:
    provider = FakeProvider([tool_response("read", {"path": "missing.txt"}), final()])
    result = build(provider, ctx).run("read a missing file")
    assert result.messages[-2].tool_results[0].is_error
    assert result.stop_reason is StopReason.END_TURN


def test_unknown_tool_is_denied_by_the_default_policy(ctx: ToolContext) -> None:
    """Default is deny, so an unknown tool never reaches dispatch."""
    provider = FakeProvider([tool_response("teleport", {}), final()])
    result = build(provider, ctx).run("teleport")
    assert result.denied_calls[0].tool == "teleport"
    assert "permission denied" in result.messages[-2].tool_results[0].content


def test_unknown_tool_is_reported_when_policy_permits(ctx: ToolContext) -> None:
    provider = FakeProvider([tool_response("teleport", {}), final()])
    permissive = PermissionPolicy(rules=[Rule(tool="*", decision=Decision.ALLOW)])
    result = build(provider, ctx, policy=permissive).run("teleport")
    assert "unknown tool" in result.messages[-2].tool_results[0].content


def test_max_steps_is_enforced(ctx: ToolContext) -> None:
    provider = FakeProvider([tool_response("read", {"path": "hello.txt"}) for _ in range(20)])
    result = build(provider, ctx, max_steps=3).run("loop forever")
    assert result.steps == 3
    assert result.stop_reason is StopReason.MAX_STEPS


def test_compaction_events_are_surfaced_on_the_result(ctx: ToolContext) -> None:
    provider = FakeProvider([final("ok")])
    loop = build(
        provider,
        ctx,
        context=ContextManager(budget=TokenBudget(max_context_tokens=60, reserve_output_tokens=10)),
    )
    result = loop.run("x" * 4000)
    assert len(result.compaction_events) >= 1


def test_run_is_resumable_from_the_session_store(ctx: ToolContext, tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "s.sqlite3")
    session = store.create(model="fake-1")
    build(FakeProvider.saying("first"), ctx, session=session).run("step one")

    resumed = store.resume(session.id)
    assert len(resumed.messages) == 2
    result = build(FakeProvider.saying("second"), ctx, session=resumed).run("step two")
    assert len(result.messages) == 4
    assert result.final_text == "second"


def test_trace_records_provider_and_tool_spans(ctx: ToolContext) -> None:
    provider = FakeProvider([tool_response("read", {"path": "hello.txt"}), final()])
    loop = build(provider, ctx)
    loop.run("read it")
    assert len(loop.trace.events("provider.complete")) == 2
    assert len(loop.trace.events("tool.run")) == 1
