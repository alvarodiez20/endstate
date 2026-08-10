"""Context budgeting and compaction.

The budget is a first-class object rather than an implicit consequence of the
model's context window. Every compaction is recorded as an event with the token
counts before and after, which is what makes "what did compaction cost you?"
answerable with a number instead of a shrug.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from endstate.types import Message


@runtime_checkable
class TokenCounter(Protocol):
    def count(self, messages: list[Message]) -> int: ...


class HeuristicTokenCounter:
    """Chars/4 approximation.

    Deliberately not a tokeniser: the harness must work against any provider,
    including ones whose tokeniser is not public. Swap in a real counter per
    provider when exactness matters.
    """

    def __init__(self, chars_per_token: float = 4.0) -> None:
        self.chars_per_token = chars_per_token

    def count(self, messages: list[Message]) -> int:
        chars = 0
        for m in messages:
            chars += len(m.content)
            for tc in m.tool_calls:
                chars += len(tc.name) + len(str(tc.arguments))
            for tr in m.tool_results:
                chars += len(tr.content)
        return int(chars / self.chars_per_token)


class TokenBudget(BaseModel):
    max_context_tokens: int = 128_000
    reserve_output_tokens: int = 8_000

    @property
    def usable_tokens(self) -> int:
        return max(0, self.max_context_tokens - self.reserve_output_tokens)


class CompactionEvent(BaseModel):
    strategy: str
    tokens_before: int
    tokens_after: int
    messages_before: int
    messages_after: int
    dropped_messages: int

    @property
    def tokens_reclaimed(self) -> int:
        return self.tokens_before - self.tokens_after


@runtime_checkable
class CompactionStrategy(Protocol):
    name: str

    def compact(
        self, messages: list[Message], budget: TokenBudget, counter: TokenCounter
    ) -> list[Message]: ...


class DropOldest:
    """Keep the system prompt, the first user message, and the newest tail that fits.

    The first user message is pinned because it usually contains the task; losing
    it is the most common way a long-horizon agent forgets what it was doing.
    """

    name = "drop_oldest"

    def compact(
        self, messages: list[Message], budget: TokenBudget, counter: TokenCounter
    ) -> list[Message]:
        if not messages:
            return messages

        pinned: list[Message] = []
        rest = list(messages)

        if rest and rest[0].role == "system":
            pinned.append(rest.pop(0))
        first_user = next((i for i, m in enumerate(rest) if m.role == "user"), None)
        if first_user is not None:
            pinned.append(rest.pop(first_user))

        tail: list[Message] = []
        for message in reversed(rest):
            candidate = [*pinned, message, *tail]
            if counter.count(candidate) > budget.usable_tokens:
                break
            tail.insert(0, message)
        return [*pinned, *tail]


class SummariseMiddle:
    """Replace the dropped middle with one synthetic summary message.

    Takes a summariser callable rather than a provider so the strategy stays
    testable without a network call.
    """

    name = "summarise_middle"

    def __init__(self, summariser: Callable[[list[Message]], str]) -> None:
        self.summariser = summariser

    def compact(
        self, messages: list[Message], budget: TokenBudget, counter: TokenCounter
    ) -> list[Message]:
        kept = DropOldest().compact(messages, budget, counter)
        kept_ids = {id(m) for m in kept}
        dropped = [m for m in messages if id(m) not in kept_ids]
        if not dropped:
            return kept

        summary = Message(
            role="user",
            content=f"[summary of {len(dropped)} earlier messages]\n{self.summariser(dropped)}",
            synthetic=True,
        )
        head = [m for m in kept if m.role == "system"]
        tail = [m for m in kept if m.role != "system"]
        return [*head, summary, *tail]


class ContextManager(BaseModel):
    """Fits a conversation into the budget, recording every compaction."""

    budget: TokenBudget = Field(default_factory=TokenBudget)
    events: list[CompactionEvent] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        budget: TokenBudget | None = None,
        strategy: CompactionStrategy | None = None,
        counter: TokenCounter | None = None,
    ) -> None:
        super().__init__(budget=budget or TokenBudget())
        self._strategy: CompactionStrategy = strategy or DropOldest()
        self._counter: TokenCounter = counter or HeuristicTokenCounter()

    @property
    def strategy_name(self) -> str:
        return self._strategy.name

    def count(self, messages: list[Message]) -> int:
        return self._counter.count(messages)

    def fit(self, messages: list[Message]) -> list[Message]:
        before = self._counter.count(messages)
        if before <= self.budget.usable_tokens:
            return messages

        compacted = self._strategy.compact(messages, self.budget, self._counter)
        after = self._counter.count(compacted)
        self.events.append(
            CompactionEvent(
                strategy=self._strategy.name,
                tokens_before=before,
                tokens_after=after,
                messages_before=len(messages),
                messages_after=len(compacted),
                dropped_messages=len(messages) - len(compacted),
            )
        )
        return compacted
