"""Killing a run on purpose, so resume can be graded rather than assumed.

The unit tests in `tests/test_recovery.py` already prove the reconciliation
logic against a scripted provider. What they cannot show is whether a *model*
recovers: whether it notices the work is half done, re-reads the state, and
finishes — or whether it carries on from a plan that no longer matches the disk.

That needs a kill in the middle of a real run, which is what this module
provides. `crash_at_call` counts tool calls across the whole run rather than
steps, because the interesting kill points are inside a batch: the third call of
three is where a result is written by rewriting the tool message rather than by
creating it.
"""

from __future__ import annotations

from typing import Any

from endstate.agent.tools.base import Tool, ToolContext


class Crash(RuntimeError):
    """Stands in for the process dying. Deliberately not a ToolError.

    A ToolError is an *expected* failure the model is meant to read and work
    around. This is the process going away, so it must not be catchable by the
    loop's own error handling.
    """


class _CrashingTool(Tool):
    """Wraps one tool, crashing on the run's nth call overall."""

    def __init__(self, inner: Tool, clock: _CallClock, index: int, after: bool) -> None:
        self.inner = inner
        self.name = inner.name
        self.description = inner.description
        self.idempotent = inner.idempotent
        self._clock = clock
        self._index = index
        self._after = after

    @property
    def parameters(self) -> dict[str, Any]:
        return self.inner.parameters

    def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        seen = self._clock.tick()
        if seen == self._index and not self._after:
            raise Crash(f"killed before call {seen}")
        output = self.inner.run(arguments, ctx)
        if seen == self._index and self._after:
            raise Crash(f"killed after call {seen}")
        return output


class _CallClock:
    def __init__(self) -> None:
        self.calls = 0

    def tick(self) -> int:
        seen = self.calls
        self.calls += 1
        return seen


class CrashAt:
    """A tool set that dies on the nth call.

    `after_side_effect` picks which window the kill lands in, and the two are
    genuinely different problems. False is the honest kill: the work never
    happened, and resume simply does it. True is the irreducible one — the side
    effect landed and nothing recorded it — where resume converges only if the
    tool is idempotent, and otherwise reports the call as unsettled.
    """

    def __init__(self, tools: list[Tool], index: int, *, after_side_effect: bool = False) -> None:
        self.clock = _CallClock()
        self.tools: list[Tool] = [
            _CrashingTool(tool, self.clock, index, after_side_effect) for tool in tools
        ]

    @property
    def calls_made(self) -> int:
        return self.clock.calls
