"""Adapter for the Anthropic Messages API."""

from __future__ import annotations

from typing import Any

from endstate.types import Message, Response, StopReason, ToolCall, Usage

_STOP_REASONS = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
}


def to_wire(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
    system: str | None = None
    wire: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            system = m.content
            continue
        if m.role == "tool":
            wire.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.call_id,
                            "content": r.content,
                            "is_error": r.is_error,
                        }
                        for r in m.tool_results
                    ],
                }
            )
            continue
        blocks: list[dict[str, Any]] = []
        if m.content:
            blocks.append({"type": "text", "text": m.content})
        blocks.extend(
            {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
            for c in m.tool_calls
        )
        wire.append({"role": m.role, "content": blocks or [{"type": "text", "text": ""}]})
    return system, wire


class AnthropicProvider:
    """Requires the `anthropic` extra: pip install 'endstate[anthropic]'."""

    def __init__(self, model: str, api_key: str | None = None, max_tokens: int = 4096) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "install the anthropic extra: pip install 'endstate[anthropic]'"
            ) from exc

        self.model = model
        self.max_tokens = max_tokens
        self._client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response:
        system, wire = to_wire(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": wire,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]

        result = self._client.messages.create(**kwargs)
        text = "".join(b.text for b in result.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input or {}))
            for b in result.content
            if b.type == "tool_use"
        ]
        return Response(
            message=Message(role="assistant", content=text, tool_calls=calls),
            usage=Usage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            ),
            stop_reason=_STOP_REASONS.get(result.stop_reason or "end_turn", StopReason.END_TURN),
            model=result.model,
        )
