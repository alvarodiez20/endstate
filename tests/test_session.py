from pathlib import Path

import pytest

from endstate.agent.session import SessionStore
from endstate.types import Message


def test_messages_survive_a_new_store(tmp_path: Path) -> None:
    db = tmp_path / "s.sqlite3"
    session = SessionStore(db).create(model="fake-1")
    session.append(Message(role="user", content="do the thing"))
    session.append(Message(role="assistant", content="done"))
    session_id = session.id

    resumed = SessionStore(db).resume(session_id)
    assert [m.content for m in resumed.messages] == ["do the thing", "done"]
    assert resumed.model == "fake-1"


def test_every_append_is_checkpointed(tmp_path: Path) -> None:
    db = tmp_path / "s.sqlite3"
    store = SessionStore(db)
    session = store.create()
    session.append(Message(role="user", content="one"))
    # Simulate a crash: nothing else is called, no explicit flush.
    assert len(SessionStore(db).resume(session.id).messages) == 1


def test_resume_unknown_session_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        SessionStore(tmp_path / "s.sqlite3").resume("does-not-exist")


def test_sessions_are_listed_newest_first(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "s.sqlite3")
    ids = [store.create().id for _ in range(3)]
    assert set(store.list_sessions()) == set(ids)
