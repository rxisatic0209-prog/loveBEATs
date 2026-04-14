from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.agent.llm import default_llm_config
from app.db import get_connection
from app.memory.agent_profiles import get_agent_profile
from app.memory.heart_rate_store import delete_role_heart_rate_events
from app.memory.persona_templates import get_persona_template
from app.memory.role_prompt_store import delete_role_prompt_snapshot
from app.models import (
    ChatMessage,
    LLMConfigResolved,
    MessageRole,
    PersonaProfile,
    RoleCardInput,
    RoleCreateRequest,
    RoleHistoryResponse,
    RoleState,
)
from app.system.persona import build_persona_from_role_card


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_role_id() -> str:
    return f"role_{uuid.uuid4().hex[:12]}"


def _serialize_persona_profile(role: RoleCreateRequest | RoleState) -> str | None:
    if role.persona_profile is None:
        return None
    return role.persona_profile.model_dump_json()


def _serialize_role_card(role: RoleCreateRequest | RoleState) -> str | None:
    if role.role_card is None:
        return None
    return role.role_card.model_dump_json()


def _row_to_role_state(row) -> RoleState:
    role_card = json.loads(row["role_card_json"]) if row["role_card_json"] else None
    persona_profile = json.loads(row["persona_profile_json"]) if row["persona_profile_json"] else None
    return RoleState(
        role_id=row["role_id"],
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


def create_or_update_role(request: RoleCreateRequest) -> RoleState:
    role_id = request.role_id or _generate_role_id()
    existing = get_role_optional(role_id)
    persona_id, persona_text, role_card, persona_profile = _resolve_persona_inputs(request, existing)
    agent_id = _resolve_agent_id(request, existing)
    resolved_llm = default_llm_config()
    now = utc_now()

    if existing is None:
        state = RoleState(
            role_id=role_id,
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
                    role_id, title, persona_id, persona_text, role_card_json, persona_profile_json, agent_id,
                    llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.role_id,
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
        return state

    updated = existing.model_copy(
        update={
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
            conn.execute("DELETE FROM role_messages WHERE role_id = ?", (updated.role_id,))
        conn.execute(
            """
            UPDATE roles
            SET title = ?, persona_id = ?, persona_text = ?, role_card_json = ?, persona_profile_json = ?, agent_id = ?,
                llm_model_id = ?, llm_base_url = ?, has_llm_api_key = ?, updated_at = ?
            WHERE role_id = ?
            """,
            (
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
                updated.role_id,
            ),
        )
    return updated


def get_role(role_id: str) -> RoleState:
    role = get_role_optional(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="role not found")
    return role


def get_role_optional(role_id: str) -> RoleState | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT role_id, title, persona_id, persona_text, role_card_json, persona_profile_json,
                   agent_id, llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM roles
            WHERE role_id = ?
            """,
            (role_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_role_state(row)


def list_roles() -> list[RoleState]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role_id, title, persona_id, persona_text, role_card_json, persona_profile_json,
                   agent_id, llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM roles
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    return [_row_to_role_state(row) for row in rows]


def delete_role(role_id: str) -> None:
    get_role(role_id)
    delete_role_heart_rate_events(role_id)
    delete_role_prompt_snapshot(role_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))


def touch_role(role_id: str) -> None:
    get_role(role_id)
    updated_at = utc_now().isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE roles SET updated_at = ? WHERE role_id = ?", (updated_at, role_id))


def get_role_history(role_id: str) -> RoleHistoryResponse:
    return RoleHistoryResponse(role=get_role(role_id), messages=list_role_messages(role_id))


def list_role_messages(role_id: str) -> list[ChatMessage]:
    get_role(role_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM role_messages
            WHERE role_id = ?
            ORDER BY id ASC
            """,
            (role_id,),
        ).fetchall()
    return [
        ChatMessage(
            role=MessageRole(row["role"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def get_recent_role_messages(role_id: str, limit: int) -> list[ChatMessage]:
    get_role(role_id)
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
            (role_id, limit),
        ).fetchall()
    return [
        ChatMessage(
            role=MessageRole(row["role"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def append_role_message(role_id: str, role: MessageRole, content: str) -> ChatMessage:
    created_at = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO role_messages (role_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (role_id, role.value, content, created_at.isoformat()),
        )
    return ChatMessage(role=role, content=content, created_at=created_at)


def get_role_llm_config(role_id: str, required: bool = True) -> LLMConfigResolved | None:
    if required:
        get_role(role_id)
    return default_llm_config()



def _resolve_persona_inputs(
    request: RoleCreateRequest,
    existing: RoleState | None,
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


def _resolve_agent_id(request: RoleCreateRequest, existing: RoleState | None) -> str | None:
    if request.agent_id:
        return get_agent_profile(request.agent_id).agent_id
    if existing is not None:
        return existing.agent_id
    return None


def _persona_memory_boundary_changed(existing: RoleState, updated: RoleState) -> bool:
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
