from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db import get_connection
from app.models import AgentProfile, AgentProfileCreateRequest, AgentProfileUpdateRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_default_agent_profile() -> AgentProfile:
    now = utc_now()
    return AgentProfile(
        agent_id="default_companion",
        name="Default Companion Agent",
        description="默认恋爱陪伴 agent，允许每轮最多一次工具调用。",
        system_preamble=None,
        tool_call_limit=1,
        heart_rate_enabled=True,
        heart_rate_max_call_per_turn=1,
        allow_stale_heart_rate=False,
        created_at=now,
        updated_at=now,
    )


def list_agent_profiles() -> list[AgentProfile]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT agent_id, name, description, system_preamble, tool_call_limit,
                   heart_rate_enabled, heart_rate_max_call_per_turn, allow_stale_heart_rate,
                   created_at, updated_at
            FROM agent_profiles
            ORDER BY updated_at DESC, agent_id DESC
            """
        ).fetchall()
    return [_row_to_agent_profile(row) for row in rows]


def create_agent_profile(request: AgentProfileCreateRequest) -> AgentProfile:
    now = utc_now()
    profile = AgentProfile(
        agent_id=f"agent_{uuid.uuid4().hex[:12]}",
        name=request.name,
        description=request.description,
        system_preamble=request.system_preamble,
        tool_call_limit=request.tool_call_limit,
        heart_rate_enabled=request.heart_rate_enabled,
        heart_rate_max_call_per_turn=request.heart_rate_max_call_per_turn,
        allow_stale_heart_rate=request.allow_stale_heart_rate,
        created_at=now,
        updated_at=now,
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_profiles (
                agent_id, name, description, system_preamble, tool_call_limit,
                heart_rate_enabled, heart_rate_max_call_per_turn, allow_stale_heart_rate,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.agent_id,
                profile.name,
                profile.description,
                profile.system_preamble,
                profile.tool_call_limit,
                int(profile.heart_rate_enabled),
                profile.heart_rate_max_call_per_turn,
                int(profile.allow_stale_heart_rate),
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
            ),
        )
    return profile


def get_agent_profile(agent_id: str) -> AgentProfile:
    profile = get_agent_profile_optional(agent_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="agent profile not found")
    return profile


def get_agent_profile_optional(agent_id: str) -> AgentProfile | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT agent_id, name, description, system_preamble, tool_call_limit,
                   heart_rate_enabled, heart_rate_max_call_per_turn, allow_stale_heart_rate,
                   created_at, updated_at
            FROM agent_profiles
            WHERE agent_id = ?
            """,
            (agent_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_agent_profile(row)


def resolve_agent_profile(agent_id: str | None) -> AgentProfile:
    if not agent_id:
        return build_default_agent_profile()
    return get_agent_profile(agent_id)


def update_agent_profile(agent_id: str, request: AgentProfileUpdateRequest) -> AgentProfile:
    existing = get_agent_profile(agent_id)
    updated = existing.model_copy(
        update={
            "name": request.name or existing.name,
            "description": request.description if request.description is not None else existing.description,
            "system_preamble": request.system_preamble if request.system_preamble is not None else existing.system_preamble,
            "tool_call_limit": request.tool_call_limit if request.tool_call_limit is not None else existing.tool_call_limit,
            "heart_rate_enabled": request.heart_rate_enabled if request.heart_rate_enabled is not None else existing.heart_rate_enabled,
            "heart_rate_max_call_per_turn": (
                request.heart_rate_max_call_per_turn
                if request.heart_rate_max_call_per_turn is not None
                else existing.heart_rate_max_call_per_turn
            ),
            "allow_stale_heart_rate": (
                request.allow_stale_heart_rate
                if request.allow_stale_heart_rate is not None
                else existing.allow_stale_heart_rate
            ),
            "updated_at": utc_now(),
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agent_profiles
            SET name = ?, description = ?, system_preamble = ?, tool_call_limit = ?,
                heart_rate_enabled = ?, heart_rate_max_call_per_turn = ?, allow_stale_heart_rate = ?,
                updated_at = ?
            WHERE agent_id = ?
            """,
            (
                updated.name,
                updated.description,
                updated.system_preamble,
                updated.tool_call_limit,
                int(updated.heart_rate_enabled),
                updated.heart_rate_max_call_per_turn,
                int(updated.allow_stale_heart_rate),
                updated.updated_at.isoformat(),
                updated.agent_id,
            ),
        )
    return updated


def delete_agent_profile(agent_id: str) -> None:
    get_agent_profile(agent_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM agent_profiles WHERE agent_id = ?", (agent_id,))


def _row_to_agent_profile(row) -> AgentProfile:
    return AgentProfile(
        agent_id=row["agent_id"],
        name=row["name"],
        description=row["description"],
        system_preamble=row["system_preamble"],
        tool_call_limit=row["tool_call_limit"],
        heart_rate_enabled=bool(row["heart_rate_enabled"]),
        heart_rate_max_call_per_turn=row["heart_rate_max_call_per_turn"],
        allow_stale_heart_rate=bool(row["allow_stale_heart_rate"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
