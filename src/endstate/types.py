"""Core value types shared across the harness.

Deliberately provider-agnostic: every provider adapter translates its own wire
format into these types, so the loop never sees a vendor-specific object.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from endstate._compat import StrEnum

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """A model's request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The outcome of running a tool."""

    call_id: str
    content: str
    is_error: bool = False


class Message(BaseModel):
    """One turn in the conversation."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    # Set by the context manager when a message is synthesised during compaction.
    synthetic: bool = False


class Usage(BaseModel):
    """Token accounting for a single provider call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cached_input_tokens


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    BUDGET_EXCEEDED = "budget_exceeded"
    MAX_STEPS = "max_steps"
    ERROR = "error"


class Response(BaseModel):
    """A normalised provider response."""

    message: Message
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = StopReason.END_TURN
    model: str = ""
