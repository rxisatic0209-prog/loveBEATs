import uuid

from app.db import get_connection
from app.memory.heart_rate_store import delete_role_heart_rate_events
from app.memory.role_prompt_store import delete_role_prompt_snapshot
from app.memory.session_store import (
    _row_to_session_state,
    create_or_update_session,
    delete_session,
    get_history,
    get_session,
    list_messages,
)
from app.models import (
    RoleCreateRequest,
    RoleHistoryResponse,
    RoleState,
    SessionCreateRequest,
    SessionHistoryResponse,
    SessionState,
)


def _generate_role_id() -> str:
    return f"role_{uuid.uuid4().hex[:12]}"


def _to_role_state(session: SessionState) -> RoleState:
    return RoleState(
        role_id=session.role_id or session.session_id,
        app_user_id=session.app_user_id or session.profile_id,
        title=session.title,
        persona_id=session.persona_id,
        persona_text=session.persona_text,
        role_card=session.role_card,
        persona_profile=session.persona_profile,
        agent_id=session.agent_id,
        llm_model_id=session.llm_model_id,
        llm_base_url=session.llm_base_url,
        has_llm_api_key=session.has_llm_api_key,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _to_role_history(history: SessionHistoryResponse) -> RoleHistoryResponse:
    return RoleHistoryResponse(role=_to_role_state(history.session), messages=history.messages)


def create_or_update_role(request: RoleCreateRequest) -> RoleState:
    role_id = request.role_id or request.session_id or _generate_role_id()
    session = create_or_update_session(
        SessionCreateRequest(
            role_id=role_id,
            session_id=role_id,
            app_user_id=request.app_user_id or request.profile_id,
            profile_id=request.app_user_id or request.profile_id,
            title=request.title,
            persona_id=request.persona_id,
            persona_text=request.persona_text,
            role_card=request.role_card,
            persona_profile=request.persona_profile,
            agent_id=request.agent_id,
            llm_config=request.llm_config,
        )
    )
    return _to_role_state(session)


def get_role(role_id: str) -> RoleState:
    return _to_role_state(get_session(role_id))


def list_roles() -> list[RoleState]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role_id, profile_id, title, persona_id, persona_text, role_card_json, persona_profile_json,
                   agent_id, llm_model_id, llm_base_url, has_llm_api_key, created_at, updated_at
            FROM roles
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    return [_to_role_state(_row_to_session_state(row)) for row in rows]


def get_role_history(role_id: str) -> RoleHistoryResponse:
    return _to_role_history(get_history(role_id))


def list_role_messages(role_id: str):
    return list_messages(role_id)


def delete_role(role_id: str) -> None:
    delete_role_heart_rate_events(role_id)
    delete_role_prompt_snapshot(role_id)
    delete_session(role_id)
