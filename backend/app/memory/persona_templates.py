from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db import get_connection
from app.models import PersonaTemplate, PersonaTemplateCreateRequest, PersonaTemplateUpdateRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_persona_templates() -> list[PersonaTemplate]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT persona_id, name, description, persona_text, persona_profile_json, created_at, updated_at
            FROM persona_templates
            ORDER BY updated_at DESC, persona_id DESC
            """
        ).fetchall()
    return [_row_to_persona_template(row) for row in rows]


def create_persona_template(request: PersonaTemplateCreateRequest) -> PersonaTemplate:
    now = utc_now()
    template = PersonaTemplate(
        persona_id=f"persona_{uuid.uuid4().hex[:12]}",
        name=request.name,
        description=request.description,
        persona_text=request.persona_text,
        persona_profile=request.persona_profile,
        created_at=now,
        updated_at=now,
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO persona_templates (
                persona_id, name, description, persona_text, persona_profile_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.persona_id,
                template.name,
                template.description,
                template.persona_text,
                template.persona_profile.model_dump_json() if template.persona_profile else None,
                template.created_at.isoformat(),
                template.updated_at.isoformat(),
            ),
        )
    return template


def get_persona_template(persona_id: str) -> PersonaTemplate:
    template = get_persona_template_optional(persona_id)
    if template is None:
        raise HTTPException(status_code=404, detail="persona template not found")
    return template


def get_persona_template_optional(persona_id: str) -> PersonaTemplate | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT persona_id, name, description, persona_text, persona_profile_json, created_at, updated_at
            FROM persona_templates
            WHERE persona_id = ?
            """,
            (persona_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_persona_template(row)


def update_persona_template(persona_id: str, request: PersonaTemplateUpdateRequest) -> PersonaTemplate:
    existing = get_persona_template(persona_id)
    updated = existing.model_copy(
        update={
            "name": request.name or existing.name,
            "description": request.description if request.description is not None else existing.description,
            "persona_text": request.persona_text or existing.persona_text,
            "persona_profile": request.persona_profile if request.persona_profile is not None else existing.persona_profile,
            "updated_at": utc_now(),
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE persona_templates
            SET name = ?, description = ?, persona_text = ?, persona_profile_json = ?, updated_at = ?
            WHERE persona_id = ?
            """,
            (
                updated.name,
                updated.description,
                updated.persona_text,
                updated.persona_profile.model_dump_json() if updated.persona_profile else None,
                updated.updated_at.isoformat(),
                updated.persona_id,
            ),
        )
    return updated


def delete_persona_template(persona_id: str) -> None:
    get_persona_template(persona_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM persona_templates WHERE persona_id = ?", (persona_id,))


def _row_to_persona_template(row) -> PersonaTemplate:
    persona_profile = json.loads(row["persona_profile_json"]) if row["persona_profile_json"] else None
    return PersonaTemplate(
        persona_id=row["persona_id"],
        name=row["name"],
        description=row["description"],
        persona_text=row["persona_text"],
        persona_profile=persona_profile,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
