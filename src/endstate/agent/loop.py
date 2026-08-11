"""The harness.

Written from primitives rather than on a framework, on purpose. The interesting
parts of an agent — where the context budget is enforced, what happens when a
tool is denied, what is persisted before a step can fail — are exactly the parts
a framework hides. They are all visible in this file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from endstate.agent.context import CompactionEvent, ContextManager
from endstate.agent.permissions import Decision, PermissionPolicy, default_policy
from endstate.agent.session import Session
from endstate.agent.tools.base import Tool, ToolContext, ToolError
from endstate.telemetry.cost import CostAccountant
from endstate.telemetry.trace import Trace
from endstate.tree import DEFAULT_EXCLUDES, tree_hash
from endstate.types import Message, StopReason, ToolCall, ToolResult, Usage


class DeniedCall(BaseModel):
    tool: str
    arguments: dict[str, object]
    reason: str


class RunResult(BaseModel):
    session_id: str | None = None
    workdir: Path | None = None
    messages: list[Message] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = StopReason.END_TURN
    steps: int = 0
    compaction_events: list[CompactionEvent] = Field(default_factory=list)
    denied_calls: list[DeniedCall] = Field(default_factory=list)
    final_text: str = ""

    model_config = {"arbitrary_types_allowed": True}

    def tree_hash(self, *, excludes: frozenset[str] = DEFAULT_EXCLUDES) -> str:
        """Hash the sandbox this run worked in.

        The assertion primitive for end-state grading: "the destructive command
        did not run" is this value being unchanged, and "the resumed run got to
        the same place" is two of these being equal.

        Raises:
            ValueError: If the run recorded no working directory.
        """
        if self.workdir is None:
            raise ValueError("this run recorded no workdir")
        return tree_hash(self.workdir, excludes=excludes)


class AgentLoop:
    def __init__(
        self,
        provider: object,
        tools: list[Tool],
        tool_context: ToolContext,
        policy: PermissionPolicy | None = None,
        context: ContextManager | None = None,
        session: Session | None = None,
        accountant: CostAccountant | None = None,
        max_steps: int = 25,
        system_prompt: str | None = None,
    ) -> None:
        self.provider = provider
        self.tools = {t.name: t for t in tools}
        self.tool_context = tool_context
        self.policy = policy or default_policy()
        self.context = context or ContextManager()
        self.session = session
        self.accountant = accountant or CostAccountant()
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.trace = Trace()

    # --- persistence ------------------------------------------------------

    def _record(self, message: Message, messages: list[Message]) -> None:
        messages.append(message)
        if self.session is not None:
            self.session.append(message)

    def _checkpoint_last(self, messages: list[Message]) -> None:
        """Re-persist the last message after mutating it in place."""
        if self.session is not None:
            self.session.messages[-1] = messages[-1]
            self.session.checkpoint_last()

    # --- entry points -----------------------------------------------------

    def run(self, prompt: str) -> RunResult:
        """Run the agent against a new instruction."""
        messages: list[Message] = list(self.session.messages) if self.session else []
        denied: list[DeniedCall] = []

        # Settle before the new prompt is appended, not after: an interrupted
        # batch has to be finished while it is still the tail of the history.
        self._settle(messages, denied)

        if not messages and self.system_prompt:
            self._record(Message(role="system", content=self.system_prompt), messages)
        self._record(Message(role="user", content=prompt), messages)
        return self._drive(messages, denied)

    def resume(self) -> RunResult:
        """Continue an interrupted run without a new instruction.

        Finishes any tool calls that were requested but never executed, then
        carries on. This is the difference between *continuing* a conversation
        and *finishing* what the agent was doing when the process died.

        Raises:
            ValueError: If the loop has no session to resume from.
        """
        if self.session is None:
            raise ValueError("resume requires a session")
        messages: list[Message] = list(self.session.messages)
        denied: list[DeniedCall] = []
        self._settle(messages, denied)
        return self._drive(messages, denied)

    # --- recovery ---------------------------------------------------------

    def _pending(self, messages: list[Message]) -> tuple[list[ToolCall], bool]:
        """Tool calls that were requested but have no recorded result.

        Returns the outstanding calls and whether a partial result message is
        already the tail of the history.
        """
        if not messages:
            return [], False

        last = messages[-1]
        if last.role == "assistant" and last.tool_calls:
            return list(last.tool_calls), False

        if last.role == "tool" and len(messages) >= 2:
            requested = messages[-2]
            if requested.role == "assistant" and requested.tool_calls:
                done = {r.call_id for r in last.tool_results}
                return [c for c in requested.tool_calls if c.id not in done], True

        return [], False

    def _settle(self, messages: list[Message], denied: list[DeniedCall]) -> None:
        """Execute any calls left outstanding by an interrupted run.

        Without this, a resumed session carries tool calls with no matching
        results — malformed under both the Anthropic and OpenAI contracts — and
        the work those calls represent is silently dropped.
        """
        pending, partial = self._pending(messages)
        if pending:
            self._run_calls(pending, messages, denied, into_existing=partial)

    # --- tool execution ---------------------------------------------------

    def _execute(self, call: ToolCall, denied: list[DeniedCall]) -> ToolResult:
        decision, reason = self.policy.check(call.name, call.arguments)
        if decision is not Decision.ALLOW:
            denied.append(DeniedCall(tool=call.name, arguments=call.arguments, reason=reason))
            with self.trace.span("tool.denied", tool=call.name, reason=reason):
                pass
            return ToolResult(
                call_id=call.id,
                content=f"permission denied ({decision.value}): {reason}",
                is_error=True,
            )

        tool = self.tools.get(call.name)
        if tool is None:
            return ToolResult(call_id=call.id, content=f"unknown tool: {call.name}", is_error=True)

        with self.trace.span("tool.run", tool=call.name):
            try:
                output = tool.run(call.arguments, self.tool_context)
                return ToolResult(call_id=call.id, content=output)
            except ToolError as exc:
                return ToolResult(call_id=call.id, content=str(exc), is_error=True)

    def _run_calls(
        self,
        calls: list[ToolCall],
        messages: list[Message],
        denied: list[DeniedCall],
        *,
        into_existing: bool = False,
    ) -> None:
        """Run a batch, persisting after every individual result.

        D8 — checkpoint *after* the tool result, never before — at per-call
        granularity. Writing the whole batch at the end would mean a crash after
        the second of three tools left no record that the first two had run,
        while their side effects were already on disk.
        """
        started = into_existing
        for call in calls:
            result = self._execute(call, denied)
            if started:
                messages[-1].tool_results.append(result)
                self._checkpoint_last(messages)
            else:
                self._record(Message(role="tool", tool_results=[result]), messages)
                started = True

    # --- the loop ---------------------------------------------------------

    def _drive(self, messages: list[Message], denied: list[DeniedCall]) -> RunResult:
        specs = [t.spec() for t in self.tools.values()]
        total = Usage()
        stop = StopReason.MAX_STEPS
        steps = 0

        for step in range(self.max_steps):
            steps = step + 1
            fitted = self.context.fit(messages)

            with self.trace.span("provider.complete", step=steps):
                response = self.provider.complete(fitted, specs)  # type: ignore[attr-defined]

            total = total + response.usage
            self.accountant.record(response.model or "unknown", response.usage)
            self._record(response.message, messages)

            if not response.message.tool_calls:
                stop = response.stop_reason
                break

            self._run_calls(list(response.message.tool_calls), messages, denied)

        final = next(
            (m.content for m in reversed(messages) if m.role == "assistant" and m.content), ""
        )
        return RunResult(
            session_id=self.session.id if self.session else None,
            workdir=self.tool_context.workdir,
            messages=messages,
            usage=total,
            stop_reason=stop,
            steps=steps,
            compaction_events=list(self.context.events),
            denied_calls=denied,
            final_text=final,
        )
