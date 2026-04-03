from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def _db_path() -> Path:
    return Path(settings.sqlite_path).expanduser()


def init_db() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                title TEXT,
                persona_text TEXT NOT NULL,
                persona_profile_json TEXT,
                llm_model_id TEXT,
                llm_base_url TEXT,
                has_llm_api_key INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_llm_configs (
                session_id TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model_id TEXT NOT NULL,
                timeout INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_id
            ON chat_messages(session_id, id);

            CREATE TABLE IF NOT EXISTS heart_rate_cache (
                profile_id TEXT PRIMARY KEY,
                bpm INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )


@contextmanager
def get_connection():
    init_db()
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM session_llm_configs")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM heart_rate_cache")
