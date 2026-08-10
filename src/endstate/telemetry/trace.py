"""A minimal in-process trace.

Not OpenTelemetry: the point is a self-contained artifact you can serialise next
to eval results. Exporting to OTel is a later concern.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pydantic import BaseModel, Field


class Span(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    started_at: float
    ended_at: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_s(self) -> float | None:
        if self.ended_at is None:
            return None
        return self.ended_at - self.started_at


class Trace(BaseModel):
    spans: list[Span] = Field(default_factory=list)

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        span = Span(name=name, started_at=time.monotonic(), attributes=dict(attributes))
        self.spans.append(span)
        try:
            yield span
        finally:
            span.ended_at = time.monotonic()

    def events(self, name: str) -> list[Span]:
        return [s for s in self.spans if s.name == name]
