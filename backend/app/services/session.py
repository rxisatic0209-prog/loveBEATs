from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db import get_connection
from app.models import ChatMessage, LLMConfigResolved, MessageRole, SessionCreateRequest, SessionHistoryResponse, SessionState
from app.services.llm import resolve_llm_config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_persona_profile(session: SessionCreateRequest | SessionState) -> str | None:
    if session.persona_profile is None:
        return None
    return session.persona_profile.model_dump_json()


def _row_to_session_state(row) -> SessionState:
    persona_profile = None
    if row["persona_profile_json"]:
        persona_profile = json.loads(row["persona_profile_json"])
    return SessionState(
        session_id=row["session_id"],
        profile_id=row["profile_id"],
        title=row["title"],
        persona_text=row["persona_text"],
        persona_profile=persona_profile,
        llm_model_id=row["llm_model_id"],
        llm_base_url=row["llm_base_url"],
        has_llm_api_key=bool(row["has_llm_api_key"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_or_update_session(request: SessionCreateRequest) -> SessionState:
    existing = get_session_optional(request.session_id)
    existing_llm = get_session_llm_config(request.session_id, required=False)
    resolved_llm = resolve_llm_config(
        existing_llm,
        api_key=request.llm_config.api_key if request.llm_config else None,
        base_url=request.llm_config.base_url if request.llm_config else None,
        model_id=request.llm_config.model_id if request.llm_config else None,
        timeout=request.llm_config.timeout if request.llm_config else None,
    )
    now = utc_now()
    if existing is None:
        state = SessionState(
            session_id=request.session_id,
            profile_id=request.profile_id,
            title=request.title,
            persona_text=request.persona_text,
            persona_profile=request.persona_profile,
            llm_model_id=resolved_llm.model_id if resolved_llm else None,
            llm_base_url=resolved_llm.base_url if resolved_llm else None,
            has_llm_api_key=resolved_llm is not None,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, profile_id, title, persona_text, persona_profile_json,
                    llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.session_id,
                    state.profile_id,
                    state.title,
                    state.persona_text,
                    _serialize_persona_profile(state),
                    state.llm_model_id,
                    state.llm_base_url,
                    int(state.has_llm_api_key),
                    state.created_at.isoformat(),
                    state.updated_at.isoformat(),
                ),
            )
            if resolved_llm is not None:
                _upsert_session_llm_config(conn, request.session_id, resolved_llm)
        return state

    updated = existing.model_copy(
        update={
            "profile_id": request.profile_id,
            "title": request.title or existing.title,
            "persona_text": request.persona_text,
            "persona_profile": request.persona_profile or existing.persona_profile,
            "llm_model_id": resolved_llm.model_id if resolved_llm else existing.llm_model_id,
            "llm_base_url": resolved_llm.base_url if resolved_llm else existing.llm_base_url,
            "has_llm_api_key": resolved_llm is not None or existing.has_llm_api_key,
            "updated_at": now,
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET profile_id = ?, title = ?, persona_text = ?, persona_profile_json = ?,
                llm_model_id = ?, llm_base_url = ?, has_llm_api_key = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (
                updated.profile_id,
                updated.title,
                updated.persona_text,
                _serialize_persona_profile(updated),
                updated.llm_model_id,
                updated.llm_base_url,
                int(updated.has_llm_api_key),
                updated.updated_at.isoformat(),
                updated.session_id,
            ),
        )
        if resolved_llm is not None:
            _upsert_session_llm_config(conn, request.session_id, resolved_llm)
    return updated


def get_session(session_id: str) -> SessionState:
    session = get_session_optional(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def get_session_optional(session_id: str) -> SessionState | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT session_id, profile_id, title, persona_text, persona_profile_json,
                   llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_session_state(row)


def touch_session(session_id: str) -> None:
    session = get_session(session_id)
    updated_at = utc_now().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (updated_at, session.session_id),
        )


def get_history(session_id: str) -> SessionHistoryResponse:
    session = get_session(session_id)
    return SessionHistoryResponse(
        session=session,
        messages=list_messages(session_id),
    )


def list_messages(session_id: str) -> list[ChatMessage]:
    get_session(session_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [
        ChatMessage(
            role=MessageRole(row["role"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def get_recent_messages(session_id: str, limit: int) -> list[ChatMessage]:
    get_session(session_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM (
                SELECT id, role, content, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
    return [
        ChatMessage(
            role=MessageRole(row["role"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def append_message(session_id: str, role: MessageRole, content: str) -> ChatMessage:
    created_at = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role.value, content, created_at.isoformat()),
        )
    return ChatMessage(role=role, content=content, created_at=created_at)


def get_session_llm_config(session_id: str, required: bool = True) -> LLMConfigResolved | None:
    if required:
        get_session(session_id)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT api_key, base_url, model_id, timeout
            FROM session_llm_configs
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return LLMConfigResolved(
        api_key=row["api_key"],
        base_url=row["base_url"],
        model_id=row["model_id"],
        timeout=row["timeout"],
    )


def _upsert_session_llm_config(conn, session_id: str, llm_config: LLMConfigResolved) -> None:
    conn.execute(
        """
        INSERT INTO session_llm_configs (session_id, api_key, base_url, model_id, timeout)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            api_key = excluded.api_key,
            base_url = excluded.base_url,
            model_id = excluded.model_id,
            timeout = excluded.timeout
        """,
        (
            session_id,
            llm_config.api_key,
            llm_config.base_url,
            llm_config.model_id,
            llm_config.timeout,
        ),
    )
