"""The harness.

Written from primitives rather than on a framework, on purpose. The interesting
parts of an agent — where the context budget is enforced, what happens when a
tool is denied, what is persisted before a step can fail — are exactly the parts
a framework hides. They are all visible in this file.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from endstate.agent.context import CompactionEvent, ContextManager
from endstate.agent.permissions import Decision, PermissionPolicy, default_policy
from endstate.agent.session import Session
from endstate.agent.tools.base import Tool, ToolContext, ToolError
from endstate.telemetry.cost import CostAccountant
from endstate.telemetry.trace import Trace
from endstate.types import Message, StopReason, ToolResult, Usage


class DeniedCall(BaseModel):
    tool: str
    arguments: dict[str, object]
    reason: str


class RunResult(BaseModel):
    session_id: str | None = None
    messages: list[Message] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = StopReason.END_TURN
    steps: int = 0
    compaction_events: list[CompactionEvent] = Field(default_factory=list)
    denied_calls: list[DeniedCall] = Field(default_factory=list)
    final_text: str = ""

    model_config = {"arbitrary_types_allowed": True}


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

    def _record(self, message: Message, messages: list[Message]) -> None:
        messages.append(message)
        if self.session is not None:
            self.session.append(message)

    def run(self, prompt: str) -> RunResult:
        messages: list[Message] = list(self.session.messages) if self.session else []
        if not messages and self.system_prompt:
            self._record(Message(role="system", content=self.system_prompt), messages)
        self._record(Message(role="user", content=prompt), messages)

        specs = [t.spec() for t in self.tools.values()]
        total = Usage()
        denied: list[DeniedCall] = []
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

            results: list[ToolResult] = []
            for call in response.message.tool_calls:
                decision, reason = self.policy.check(call.name, call.arguments)
                if decision is not Decision.ALLOW:
                    denied.append(
                        DeniedCall(tool=call.name, arguments=call.arguments, reason=reason)
                    )
                    with self.trace.span("tool.denied", tool=call.name, reason=reason):
                        pass
                    results.append(
                        ToolResult(
                            call_id=call.id,
                            content=f"permission denied ({decision.value}): {reason}",
                            is_error=True,
                        )
                    )
                    continue

                tool = self.tools.get(call.name)
                if tool is None:
                    results.append(
                        ToolResult(
                            call_id=call.id, content=f"unknown tool: {call.name}", is_error=True
                        )
                    )
                    continue

                with self.trace.span("tool.run", tool=call.name):
                    try:
                        output = tool.run(call.arguments, self.tool_context)
                        results.append(ToolResult(call_id=call.id, content=output))
                    except ToolError as exc:
                        results.append(ToolResult(call_id=call.id, content=str(exc), is_error=True))

            self._record(Message(role="tool", tool_results=results), messages)

        final = next(
            (m.content for m in reversed(messages) if m.role == "assistant" and m.content), ""
        )
        return RunResult(
            session_id=self.session.id if self.session else None,
            messages=messages,
            usage=total,
            stop_reason=stop,
            steps=steps,
            compaction_events=list(self.context.events),
            denied_calls=denied,
            final_text=final,
        )
