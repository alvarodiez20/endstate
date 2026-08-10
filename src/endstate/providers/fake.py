"""A scripted provider.

Exists so the harness is testable without a network, an API key, or a bill. Every
behaviour in the loop — tool calls, multi-step runs, budget exhaustion, denial —
is covered by tests that use this.
"""

from __future__ import annotations

from typing import Any

from endstate.types import Message, Response, StopReason, Usage


class FakeProvider:
    """Replays a fixed list of responses, then ends the turn."""

    def __init__(self, responses: list[Response], model: str = "fake-1") -> None:
        self.model = model
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    @classmethod
    def saying(cls, text: str, model: str = "fake-1") -> FakeProvider:
        return cls(
            [
                Response(
                    message=Message(role="assistant", content=text),
                    usage=Usage(input_tokens=10, output_tokens=5),
                    stop_reason=StopReason.END_TURN,
                    model=model,
                )
            ],
            model=model,
        )

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response:
        self.calls.append(list(messages))
        if self._responses:
            response = self._responses.pop(0)
            if not response.model:
                response.model = self.model
            return response
        return Response(
            message=Message(role="assistant", content="done"),
            usage=Usage(input_tokens=1, output_tokens=1),
            stop_reason=StopReason.END_TURN,
            model=self.model,
        )
