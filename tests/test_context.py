from endstate.agent.context import (
    ContextManager,
    DropOldest,
    HeuristicTokenCounter,
    SummariseMiddle,
    TokenBudget,
)
from endstate.types import Message


def conversation(n: int, size: int = 400) -> list[Message]:
    msgs = [Message(role="system", content="sys"), Message(role="user", content="TASK " * 5)]
    for i in range(n):
        msgs.append(Message(role="assistant", content=f"{i} " + "x" * size))
    return msgs


def test_no_compaction_when_within_budget() -> None:
    cm = ContextManager(budget=TokenBudget(max_context_tokens=1_000_000))
    msgs = conversation(5)
    assert cm.fit(msgs) == msgs
    assert cm.events == []


def test_compaction_fires_and_is_recorded() -> None:
    cm = ContextManager(budget=TokenBudget(max_context_tokens=1_000, reserve_output_tokens=200))
    fitted = cm.fit(conversation(50))
    assert len(cm.events) == 1
    event = cm.events[0]
    assert event.tokens_after < event.tokens_before
    assert event.tokens_reclaimed > 0
    assert event.dropped_messages > 0
    assert cm.count(fitted) <= cm.budget.usable_tokens


def test_system_and_first_user_message_are_pinned() -> None:
    cm = ContextManager(budget=TokenBudget(max_context_tokens=800, reserve_output_tokens=100))
    fitted = cm.fit(conversation(60))
    assert fitted[0].role == "system"
    assert any(m.role == "user" and "TASK" in m.content for m in fitted)


def test_most_recent_messages_survive() -> None:
    cm = ContextManager(budget=TokenBudget(max_context_tokens=1_200, reserve_output_tokens=200))
    fitted = cm.fit(conversation(40))
    assert fitted[-1].content.startswith("39 ")


def test_summarise_middle_inserts_one_synthetic_message() -> None:
    cm = ContextManager(
        budget=TokenBudget(max_context_tokens=1_000, reserve_output_tokens=200),
        strategy=SummariseMiddle(lambda msgs: f"{len(msgs)} messages summarised"),
    )
    fitted = cm.fit(conversation(50))
    synthetic = [m for m in fitted if m.synthetic]
    assert len(synthetic) == 1
    assert "messages summarised" in synthetic[0].content
    assert cm.strategy_name == "summarise_middle"


def test_heuristic_counter_scales_with_content() -> None:
    counter = HeuristicTokenCounter()
    assert counter.count([Message(role="user", content="a" * 400)]) == 100


def test_drop_oldest_is_stable_on_empty_input() -> None:
    assert DropOldest().compact([], TokenBudget(), HeuristicTokenCounter()) == []
