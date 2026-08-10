"""Tool interface and the sandbox boundary.

Every tool receives a ToolContext whose workdir is the only part of the
filesystem it may touch. Path confinement lives here rather than in each tool so
there is exactly one place to audit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """Raised for expected tool failures; surfaced to the model, not the user."""


@dataclass(frozen=True)
class ToolContext:
    workdir: Path
    timeout_s: float = 30.0
    max_output_chars: int = 20_000

    def resolve(self, relative: str) -> Path:
        """Resolve a path inside the workdir, refusing anything that escapes it."""
        root = self.workdir.resolve()
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ToolError(f"path {relative!r} escapes the working directory")
        return candidate

    def truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        omitted = len(text) - self.max_output_chars
        return text[: self.max_output_chars] + f"\n... [{omitted} chars truncated]"


class Tool(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool arguments."""

    @abstractmethod
    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        """Execute and return output for the model. Raise ToolError on failure."""

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
