"""Konusma gecmisi.

- Aktif oturum baglami (Gemini Content listesi) bellekte tutulur.
- Kalici kayit (audit + ileride uzun sureli hafiza cikarimi icin)
  SQLite'a duz metin olarak yazilir.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
from google.genai import types

from ..config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


class ConversationStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[types.Content]] = {}
        self._db_path = settings.anka_db_path

    async def init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    def get_history(self, session_id: str) -> list[types.Content]:
        return self._sessions.setdefault(session_id, [])

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def log(self, session_id: str, role: str, content: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            await db.commit()


store = ConversationStore()
