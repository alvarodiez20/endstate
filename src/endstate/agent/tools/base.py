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


def confine(root: Path, relative: str) -> Path:
    """Resolve `relative` inside `root`, refusing anything that escapes it.

    Lives at module level because the eval sandbox needs the same rule and one
    audited implementation is worth more than two that agree today.

    Raises:
        ValueError: If the resolved path is outside `root`.
    """
    base = root.resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"path {relative!r} escapes {base}")
    return candidate


@dataclass(frozen=True)
class ToolContext:
    workdir: Path
    timeout_s: float = 30.0
    max_output_chars: int = 20_000

    def resolve(self, relative: str) -> Path:
        """Resolve a path inside the workdir, refusing anything that escapes it."""
        try:
            return confine(self.workdir, relative)
        except ValueError as exc:
            raise ToolError(f"path {relative!r} escapes the working directory") from exc

    def truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        omitted = len(text) - self.max_output_chars
        return text[: self.max_output_chars] + f"\n... [{omitted} chars truncated]"


class Tool(ABC):
    name: str
    description: str

    idempotent: bool = True
    """Whether running this call twice is the same as running it once.

    Read by the resume path. A crash inside a tool call — after the side effect,
    before any record of it — leaves the harness unable to tell "done" from
    "about to". For an idempotent tool that is harmless: re-running converges.
    For one that appends, increments or posts, re-running is a second side
    effect, so resume reports the call as interrupted instead of repeating it.

    Default True because the tools shipped here overwrite rather than accumulate.
    Anything with an external or accumulating effect must set it False.
    """

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
