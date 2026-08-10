"""Provider interface.

The loop depends on this Protocol and nothing else. Adding a provider means
writing one adapter; it never means touching the loop. This is also what makes
the same eval suite runnable against a hosted API and a self-hosted vLLM
endpoint without changing a single task.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from endstate.types import Message, Response


@runtime_checkable
class Provider(Protocol):
    model: str

    def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Response: ...
