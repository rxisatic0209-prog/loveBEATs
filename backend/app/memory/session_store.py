from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from app.agent.llm import resolve_llm_config
from app.config import settings
from app.db import get_connection
from app.memory.agent_profiles import get_agent_profile
from app.memory.persona_templates import get_persona_template
from app.models import ChatMessage, LLMConfigResolved, MessageRole, PersonaProfile, RoleCardInput, SessionCreateRequest, SessionHistoryResponse, SessionState
from app.system.persona import build_persona_from_role_card


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_persona_profile(session: SessionCreateRequest | SessionState) -> str | None:
    if session.persona_profile is None:
        return None
    return session.persona_profile.model_dump_json()


def _serialize_role_card(session: SessionCreateRequest | SessionState) -> str | None:
    if session.role_card is None:
        return None
    return session.role_card.model_dump_json()


def _row_to_session_state(row) -> SessionState:
    role_card = json.loads(row["role_card_json"]) if row["role_card_json"] else None
    persona_profile = None
    if row["persona_profile_json"]:
        persona_profile = json.loads(row["persona_profile_json"])
    return SessionState(
        role_id=row["role_id"],
        session_id=row["role_id"],
        app_user_id=row["profile_id"],
        profile_id=row["profile_id"],
        title=row["title"],
        persona_id=row["persona_id"],
        persona_text=row["persona_text"],
        role_card=role_card,
        persona_profile=persona_profile,
        agent_id=row["agent_id"],
        llm_model_id=row["llm_model_id"],
        llm_base_url=row["llm_base_url"],
        has_llm_api_key=bool(row["has_llm_api_key"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_or_update_session(request: SessionCreateRequest) -> SessionState:
    existing = get_session_optional(request.session_id)
    existing_llm = get_session_llm_config(request.session_id, required=False)
    app_user_id = _resolve_app_user_id(request, existing)
    persona_id, persona_text, role_card, persona_profile = _resolve_persona_inputs(request, existing)
    agent_id = _resolve_agent_id(request, existing)
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
            app_user_id=app_user_id,
            profile_id=app_user_id,
            title=request.title,
            persona_id=persona_id,
            persona_text=persona_text,
            role_card=role_card,
            persona_profile=persona_profile,
            agent_id=agent_id,
            llm_model_id=resolved_llm.model_id if resolved_llm else None,
            llm_base_url=resolved_llm.base_url if resolved_llm else None,
            has_llm_api_key=resolved_llm is not None,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO roles (
                    role_id, profile_id, title, persona_id, persona_text, role_card_json, persona_profile_json, agent_id,
                    llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.session_id,
                    state.profile_id,
                    state.title,
                    state.persona_id,
                    state.persona_text,
                    _serialize_role_card(state),
                    _serialize_persona_profile(state),
                    state.agent_id,
                    state.llm_model_id,
                    state.llm_base_url,
                    int(state.has_llm_api_key),
                    state.created_at.isoformat(),
                    state.updated_at.isoformat(),
                ),
            )
            _upsert_app_user(conn, app_user_id, state.created_at)
            if resolved_llm is not None:
                _upsert_session_llm_config(conn, request.session_id, resolved_llm)
        return state

    updated = existing.model_copy(
        update={
            "app_user_id": app_user_id,
            "profile_id": app_user_id,
            "title": request.title or existing.title,
            "persona_id": persona_id,
            "persona_text": persona_text,
            "role_card": role_card,
            "persona_profile": persona_profile,
            "agent_id": agent_id,
            "llm_model_id": resolved_llm.model_id if resolved_llm else existing.llm_model_id,
            "llm_base_url": resolved_llm.base_url if resolved_llm else existing.llm_base_url,
            "has_llm_api_key": resolved_llm is not None or existing.has_llm_api_key,
            "updated_at": now,
        }
    )
    with get_connection() as conn:
        if _persona_memory_boundary_changed(existing, updated):
            conn.execute("DELETE FROM role_messages WHERE role_id = ?", (updated.session_id,))
        _upsert_app_user(conn, app_user_id, updated.updated_at)
        conn.execute(
            """
            UPDATE roles
            SET profile_id = ?, title = ?, persona_id = ?, persona_text = ?, role_card_json = ?, persona_profile_json = ?, agent_id = ?,
                llm_model_id = ?, llm_base_url = ?, has_llm_api_key = ?, updated_at = ?
            WHERE role_id = ?
            """,
            (
                updated.profile_id,
                updated.title,
                updated.persona_id,
                updated.persona_text,
                _serialize_role_card(updated),
                _serialize_persona_profile(updated),
                updated.agent_id,
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


def delete_session(session_id: str) -> None:
    get_session(session_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM roles WHERE role_id = ?", (session_id,))


def get_session_optional(session_id: str) -> SessionState | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT role_id, profile_id, title, persona_id, persona_text, role_card_json, persona_profile_json,
                   agent_id, llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM roles
            WHERE role_id = ?
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
            "UPDATE roles SET updated_at = ? WHERE role_id = ?",
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
            FROM role_messages
            WHERE role_id = ?
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
                FROM role_messages
                WHERE role_id = ?
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
            INSERT INTO role_messages (role_id, role, content, created_at)
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
            FROM role_llm_configs
            WHERE role_id = ?
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
        INSERT INTO role_llm_configs (role_id, api_key, base_url, model_id, timeout)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(role_id) DO UPDATE SET
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


def _upsert_app_user(conn, app_user_id: str, now: datetime) -> None:
    conn.execute(
        """
        INSERT INTO app_users (app_user_id, created_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(app_user_id) DO UPDATE SET
            updated_at = excluded.updated_at
        """,
        (app_user_id, now.isoformat(), now.isoformat()),
    )


def _resolve_persona_inputs(
    request: SessionCreateRequest,
    existing: SessionState | None,
) -> tuple[str | None, str, RoleCardInput | None, PersonaProfile | None]:
    if request.role_card is not None:
        persona_text, persona_profile = build_persona_from_role_card(request.role_card)
        return None, persona_text, request.role_card, persona_profile

    if request.persona_id:
        template = get_persona_template(request.persona_id)
        persona_text = request.persona_text or template.persona_text
        persona_profile = request.persona_profile or template.persona_profile
        return template.persona_id, persona_text, None, persona_profile

    if request.persona_text is not None or request.persona_profile is not None:
        if request.persona_text is None and existing is None:
            raise HTTPException(status_code=400, detail="persona_text or role_card is required for a new role")
        return (
            None,
            request.persona_text or existing.persona_text,
            existing.role_card if existing else None,
            request.persona_profile or (existing.persona_profile if existing else None),
        )

    if existing is not None:
        return existing.persona_id, existing.persona_text, existing.role_card, existing.persona_profile

    raise HTTPException(status_code=400, detail="persona_text or persona_id or role_card is required for a new role")


def _resolve_agent_id(request: SessionCreateRequest, existing: SessionState | None) -> str | None:
    if request.agent_id:
        return get_agent_profile(request.agent_id).agent_id
    if existing is not None:
        return existing.agent_id
    return None


def _resolve_app_user_id(request: SessionCreateRequest, existing: SessionState | None) -> str:
    return (
        request.app_user_id
        or request.profile_id
        or (existing.app_user_id if existing is not None else None)
        or (existing.profile_id if existing is not None else None)
        or settings.default_app_user_id
    )


def _persona_memory_boundary_changed(existing: SessionState, updated: SessionState) -> bool:
    existing_role_card = existing.role_card.model_dump_json() if existing.role_card else None
    updated_role_card = updated.role_card.model_dump_json() if updated.role_card else None
    existing_profile = existing.persona_profile.model_dump_json() if existing.persona_profile else None
    updated_profile = updated.persona_profile.model_dump_json() if updated.persona_profile else None
    return (
        existing.persona_id != updated.persona_id
        or existing.persona_text != updated.persona_text
        or existing_role_card != updated_role_card
        or existing_profile != updated_profile
    )


def get_app_user_id_for_session(session_id: str) -> str:
    session = get_session(session_id)
    return session.app_user_id or session.profile_id
