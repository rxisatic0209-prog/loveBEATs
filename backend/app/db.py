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

            CREATE TABLE IF NOT EXISTS heart_rate_cache (
                profile_id TEXT PRIMARY KEY,
                bpm INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local_cache'
            );

            CREATE TABLE IF NOT EXISTS app_users (
                app_user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            DROP TABLE IF EXISTS app_user_healthkit_bridges;

            CREATE TABLE IF NOT EXISTS app_user_heart_rate_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_user_id TEXT NOT NULL,
                bpm INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local_cache',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_app_user_heart_rate_events_app_user_id_id
            ON app_user_heart_rate_events(app_user_id, id);

            CREATE TABLE IF NOT EXISTS roles (
                role_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                title TEXT,
                persona_id TEXT,
                persona_text TEXT NOT NULL,
                role_card_json TEXT,
                persona_profile_json TEXT,
                agent_id TEXT,
                llm_model_id TEXT,
                llm_base_url TEXT,
                has_llm_api_key INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS role_llm_configs (
                role_id TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model_id TEXT NOT NULL,
                timeout INTEGER NOT NULL,
                FOREIGN KEY(role_id) REFERENCES roles(role_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS role_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(role_id) REFERENCES roles(role_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_role_messages_role_id_id
            ON role_messages(role_id, id);

            CREATE TABLE IF NOT EXISTS role_heart_rate_latest (
                role_id TEXT PRIMARY KEY,
                bpm INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local_cache'
            );

            CREATE TABLE IF NOT EXISTS role_prompt_snapshots (
                role_id TEXT PRIMARY KEY,
                compiled_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(role_id) REFERENCES roles(role_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS role_heart_rate_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id TEXT NOT NULL,
                bpm INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local_cache',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_role_heart_rate_events_role_id_id
            ON role_heart_rate_events(role_id, id);

            CREATE TABLE IF NOT EXISTS persona_templates (
                persona_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                persona_text TEXT NOT NULL,
                persona_profile_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                system_preamble TEXT,
                tool_call_limit INTEGER NOT NULL DEFAULT 1,
                heart_rate_enabled INTEGER NOT NULL DEFAULT 1,
                heart_rate_max_call_per_turn INTEGER NOT NULL DEFAULT 1,
                allow_stale_heart_rate INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "roles", "profile_id", "TEXT")
        _ensure_column(conn, "roles", "role_card_json", "TEXT")
        _ensure_column(conn, "heart_rate_cache", "source", "TEXT NOT NULL DEFAULT 'local_cache'")
        _ensure_column(conn, "app_user_heart_rate_events", "source", "TEXT NOT NULL DEFAULT 'local_cache'")
        _ensure_column(conn, "role_heart_rate_latest", "source", "TEXT NOT NULL DEFAULT 'local_cache'")
        _ensure_column(conn, "role_heart_rate_events", "source", "TEXT NOT NULL DEFAULT 'local_cache'")
        conn.execute("UPDATE heart_rate_cache SET source = 'local_cache' WHERE source IS NULL OR source = ''")
        conn.execute("UPDATE app_user_heart_rate_events SET source = 'local_cache' WHERE source IS NULL OR source = ''")
        conn.execute("UPDATE role_heart_rate_latest SET source = 'local_cache' WHERE source IS NULL OR source = ''")
        conn.execute("UPDATE role_heart_rate_events SET source = 'local_cache' WHERE source IS NULL OR source = ''")
        conn.execute("UPDATE roles SET profile_id = role_id WHERE profile_id IS NULL OR profile_id = ''")
        _migrate_legacy_role_storage(conn)


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _migrate_legacy_role_storage(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if "sessions" in tables:
        conn.executescript(
            """
            INSERT OR IGNORE INTO roles (
                role_id, profile_id, title, persona_id, persona_text, persona_profile_json, agent_id,
                llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            )
            SELECT
                session_id, profile_id, title, persona_id, persona_text, persona_profile_json, agent_id,
                llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM sessions;
            """
        )
    if "session_llm_configs" in tables:
        conn.executescript(
            """
            INSERT OR IGNORE INTO role_llm_configs (role_id, api_key, base_url, model_id, timeout)
            SELECT session_id, api_key, base_url, model_id, timeout
            FROM session_llm_configs;
            """
        )
    if "chat_messages" in tables:
        conn.executescript(
            """
            INSERT OR IGNORE INTO role_messages (id, role_id, role, content, created_at)
            SELECT id, session_id, role, content, created_at
            FROM chat_messages;
            """
        )
    conn.executescript(
        """
        INSERT OR IGNORE INTO role_heart_rate_latest (role_id, bpm, timestamp)
        SELECT profile_id, bpm, timestamp
        FROM heart_rate_cache;
        """
    )
    if {"sessions", "session_llm_configs", "chat_messages"} & tables:
        conn.executescript(
            """
            DROP TABLE IF EXISTS chat_messages;
            DROP TABLE IF EXISTS session_llm_configs;
            DROP TABLE IF EXISTS sessions;
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
        conn.execute("DELETE FROM heart_rate_cache")
        conn.execute("DELETE FROM app_user_heart_rate_events")
        conn.execute("DELETE FROM app_users")
        conn.execute("DELETE FROM role_messages")
        conn.execute("DELETE FROM role_llm_configs")
        conn.execute("DELETE FROM roles")
        conn.execute("DELETE FROM role_heart_rate_latest")
        conn.execute("DELETE FROM role_heart_rate_events")
        conn.execute("DELETE FROM role_prompt_snapshots")
        conn.execute("DELETE FROM persona_templates")
        conn.execute("DELETE FROM agent_profiles")
