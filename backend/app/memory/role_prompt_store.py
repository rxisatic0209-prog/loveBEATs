from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import get_connection
from app.models import PersonaCompiled


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_role_prompt_snapshot(role_id: str, persona: PersonaCompiled) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO role_prompt_snapshots (role_id, compiled_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(role_id) DO UPDATE SET
                compiled_json = excluded.compiled_json,
                updated_at = excluded.updated_at
            """,
            (role_id, json.dumps(persona.model_dump(mode="json"), ensure_ascii=False), utc_now_iso()),
        )


def get_role_prompt_snapshot(role_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT compiled_json FROM role_prompt_snapshots WHERE role_id = ?",
            (role_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["compiled_json"])


def delete_role_prompt_snapshot(role_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM role_prompt_snapshots WHERE role_id = ?", (role_id,))
