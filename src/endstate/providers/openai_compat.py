"""Adapter for any OpenAI-compatible chat completions endpoint.

One adapter covers OpenAI, vLLM, Ollama, TGI and most hosted gateways, which is
what lets the identical eval suite run against a frontier API and a self-hosted
model without touching a task definition.
"""

from __future__ import annotations

import json
from typing import Any

from endstate.types import Message, Response, StopReason, ToolCall, Usage

_STOP_REASONS = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
}


def to_wire(messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            wire.extend(
                {"role": "tool", "tool_call_id": r.call_id, "content": r.content}
                for r in m.tool_results
            )
            continue
        entry: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in m.tool_calls
            ]
        wire.append(entry)
    return wire


class OpenAICompatProvider:
    """Requires the `openai` extra: pip install 'endstate[openai]'."""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError("install the openai extra: pip install 'endstate[openai]'") from exc

        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response:
        kwargs: dict[str, Any] = {"model": self.model, "messages": to_wire(messages)}
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        completion = self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        calls = [
            ToolCall(
                id=c.id,
                name=c.function.name,
                arguments=json.loads(c.function.arguments or "{}"),
            )
            for c in (choice.message.tool_calls or [])
        ]
        usage = completion.usage
        return Response(
            message=Message(
                role="assistant", content=choice.message.content or "", tool_calls=calls
            ),
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            stop_reason=_STOP_REASONS.get(choice.finish_reason or "stop", StopReason.END_TURN),
            model=completion.model or self.model,
        )
