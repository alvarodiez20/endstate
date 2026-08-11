"""Durable sessions.

SQLite, not Postgres or Redis: a harness that needs infrastructure to remember
what it was doing is a harness nobody will run locally. A checkpoint is written
after every step, so a killed process resumes from the last completed tool call
rather than from the beginning.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from endstate.types import Message

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL DEFAULT (julianday('now')),
    model       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS messages (
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    step        INTEGER NOT NULL,
    payload     TEXT NOT NULL,
    PRIMARY KEY (session_id, step)
);
"""


class SessionStore:
    def __init__(self, path: str | Path = ".endstate/sessions.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create(self, model: str = "") -> Session:
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute("INSERT INTO sessions (id, model) VALUES (?, ?)", (session_id, model))
        return Session(id=session_id, store=self, model=model)

    def resume(self, session_id: str) -> Session:
        with self._connect() as conn:
            row = conn.execute("SELECT model FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown session: {session_id}")
            rows = conn.execute(
                "SELECT payload FROM messages WHERE session_id = ? ORDER BY step",
                (session_id,),
            ).fetchall()
        session = Session(id=session_id, store=self, model=row[0])
        session.messages = [Message(**json.loads(r[0])) for r in rows]
        return session

    def list_sessions(self) -> list[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute("SELECT id FROM sessions ORDER BY created_at DESC")]

    def _append(self, session_id: str, step: int, message: Message) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO messages (session_id, step, payload) VALUES (?, ?, ?)",
                (session_id, step, message.model_dump_json()),
            )

    def _set_status(self, session_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


class Session:
    """An append-only conversation that survives process death."""

    def __init__(self, id: str, store: SessionStore, model: str = "") -> None:
        self.id = id
        self.store = store
        self.model = model
        self.messages: list[Message] = []

    def append(self, message: Message) -> None:
        """Append and checkpoint in one operation. There is no uncheckpointed state."""
        self.messages.append(message)
        self.store._append(self.id, len(self.messages) - 1, message)

    def checkpoint_last(self) -> None:
        """Re-persist the final message in place.

        Used while a batch of tool calls is being executed: each result is
        written as it lands, so a process killed mid-batch leaves a record of
        exactly the calls that completed. Rewriting the same step keeps one tool
        message per assistant turn, which is the shape every provider expects.
        """
        if not self.messages:
            raise IndexError("no message to checkpoint")
        self.store._append(self.id, len(self.messages) - 1, self.messages[-1])

    def close(self) -> None:
        self.store._set_status(self.id, "closed")

    def __len__(self) -> int:
        return len(self.messages)
