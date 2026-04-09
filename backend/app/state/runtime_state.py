from __future__ import annotations

from fastapi import HTTPException

from app.agent.llm import resolve_llm_config
from app.config import settings
from app.memory.agent_profiles import resolve_agent_profile
from app.memory.persona_templates import get_persona_template
from app.memory.role_prompt_store import upsert_role_prompt_snapshot
from app.memory.session_store import (
    create_or_update_session,
    get_recent_messages,
    get_session,
    get_session_llm_config,
    get_session_optional,
)
from app.models import (
    ChatMessage,
    ChatSendRequest,
    LLMConfigResolved,
    LLMConfigSummary,
    MessageRole,
    PromptMessage,
    SessionCreateRequest,
    SessionState,
    TurnDebugSnapshot,
    TurnRuntime,
)
from app.system.guardrails import build_runtime_context_prompt, build_system_prompt
from app.system.persona import compile_persona
from app.system.scaffold import build_agent_scaffold
from app.tools.registry import get_runtime_tools


def create_turn_runtime(
    request: ChatSendRequest,
    *,
    persist_session: bool = True,
) -> TurnRuntime:
    session, llm_config = _resolve_role_snapshot(request, persist_session=persist_session)
    persona = compile_persona(session.persona_text, session.persona_profile)
    if persist_session:
        upsert_role_prompt_snapshot(session.session_id, persona)
    agent = resolve_agent_profile(session.agent_id)
    scaffold = build_agent_scaffold()
    policy = agent.to_runtime_policy()
    model_id = llm_config.model_id if llm_config else "mock-local"
    previous_messages = (
        get_recent_messages(session.session_id, settings.session_message_window - 1)
        if get_session_optional(session.session_id)
        else []
    )
    current_message = ChatMessage(role=MessageRole.user, content=request.user_message)
    recent_messages = [*previous_messages, current_message][-settings.session_message_window :]
    enabled_tool_names = {item.name for item in get_runtime_tools(policy)}
    runtime_tools = [tool for tool in scaffold.tool_registry if tool.name in enabled_tool_names]

    return TurnRuntime(
        role_id=session.role_id or session.session_id,
        app_user_id=session.app_user_id or session.profile_id,
        session_id=session.session_id,
        profile_id=session.profile_id,
        model_id=model_id,
        agent=agent,
        persona=persona,
        system_prompt=build_system_prompt(persona.compiled_prompt, system_preamble=agent.system_preamble),
        tools=runtime_tools,
        recent_messages=recent_messages,
        current_user_message=request.user_message,
        idle_seconds=request.idle_seconds,
        policy=policy,
    )


def create_turn_debug_snapshot(
    request: ChatSendRequest,
    *,
    persist_session: bool = False,
) -> TurnDebugSnapshot:
    runtime = create_turn_runtime(request, persist_session=persist_session)
    llm_config = _resolve_runtime_llm_config(runtime.session_id, persist_session=persist_session, request=request)
    llm_source = _resolve_llm_source(request, persist_session=persist_session)
    warnings: list[str] = []
    if llm_config is None:
        warnings.append("LLM 配置不完整，本轮将退回本地 mock 响应。")
    if not runtime.tools:
        warnings.append("本轮没有可用工具。")
    if runtime.policy.heart_rate.enabled and "get_heart_rate" not in {tool.name for tool in runtime.tools}:
        warnings.append("心率策略已开启，但心率工具未进入本轮 runtime。")

    return TurnDebugSnapshot(
        scaffold=build_agent_scaffold(),
        runtime=runtime,
        llm=_build_llm_summary(llm_config, source=llm_source),
        prompt_messages=_build_prompt_messages(runtime),
        warnings=warnings,
        persists_session=persist_session,
    )


def _build_prompt_messages(runtime: TurnRuntime) -> list[PromptMessage]:
    messages = [
        PromptMessage(role="system", content=runtime.system_prompt),
        PromptMessage(
            role="system",
            content=build_runtime_context_prompt(
                idle_seconds=runtime.idle_seconds,
                tool_names=[tool.name for tool in runtime.tools],
            ),
        ),
    ]
    messages.extend(PromptMessage(role=item.role.value, content=item.content) for item in runtime.recent_messages)
    return messages


def _build_llm_summary(llm_config: LLMConfigResolved | None, *, source: str) -> LLMConfigSummary:
    if llm_config is None:
        return LLMConfigSummary(source="mock-local")
    return LLMConfigSummary(
        model_id=llm_config.model_id,
        base_url=llm_config.base_url,
        has_api_key=bool(llm_config.api_key),
        timeout=llm_config.timeout,
        source=source,
    )


def _resolve_runtime_llm_config(
    session_id: str,
    *,
    persist_session: bool,
    request: ChatSendRequest,
) -> LLMConfigResolved | None:
    if persist_session:
        return get_session_llm_config(session_id)
    existing = get_session_optional(session_id)
    existing_llm = get_session_llm_config(session_id) if existing is not None else None
    return resolve_llm_config(
        existing_llm,
        api_key=request.llm_config.api_key if request.llm_config else None,
        base_url=request.llm_config.base_url if request.llm_config else None,
        model_id=request.llm_config.model_id if request.llm_config else None,
        timeout=request.llm_config.timeout if request.llm_config else None,
    )


def _resolve_llm_source(request: ChatSendRequest, *, persist_session: bool) -> str:
    if persist_session:
        return "session"
    if request.llm_config and any(
        [request.llm_config.api_key, request.llm_config.base_url, request.llm_config.model_id]
    ):
        return "request"
    if get_session_optional(request.session_id) is not None:
        return "session"
    return "mock-local"


def _resolve_role_snapshot(
    request: ChatSendRequest,
    *,
    persist_session: bool,
) -> tuple[SessionState, LLMConfigResolved | None]:
    existing = get_session_optional(request.session_id)
    app_user_id = _resolve_app_user_id(request, existing)
    if existing is None and not request.persona_text and not request.persona_id and request.role_card is None:
        raise HTTPException(status_code=400, detail="persona_text or persona_id or role_card is required for a new role")

    if persist_session:
        if existing is None:
            create_or_update_session(
                SessionCreateRequest(
                    session_id=request.session_id,
                    app_user_id=app_user_id,
                    profile_id=app_user_id,
                    persona_id=request.persona_id,
                    persona_text=request.persona_text,
                    role_card=request.role_card,
                    persona_profile=request.persona_profile,
                    agent_id=request.agent_id,
                    llm_config=request.llm_config,
                )
            )
        else:
            create_or_update_session(
                SessionCreateRequest(
                    session_id=request.session_id,
                    app_user_id=app_user_id,
                    profile_id=app_user_id,
                    title=existing.title,
                    persona_id=request.persona_id or existing.persona_id,
                    persona_text=request.persona_text or existing.persona_text,
                    role_card=request.role_card or existing.role_card,
                    persona_profile=request.persona_profile or existing.persona_profile,
                    agent_id=request.agent_id or existing.agent_id,
                    llm_config=request.llm_config,
                )
            )
        session = get_session(request.session_id)
        return session, get_session_llm_config(request.session_id)

    if existing is None:
        template = get_persona_template(request.persona_id) if request.persona_id else None
        if request.agent_id:
            resolve_agent_profile(request.agent_id)
        llm_config = resolve_llm_config(
            None,
            api_key=request.llm_config.api_key if request.llm_config else None,
            base_url=request.llm_config.base_url if request.llm_config else None,
            model_id=request.llm_config.model_id if request.llm_config else None,
            timeout=request.llm_config.timeout if request.llm_config else None,
        )
        session = SessionState(
            role_id=request.role_id or request.session_id,
            session_id=request.session_id,
            app_user_id=app_user_id,
            profile_id=app_user_id,
            persona_id=request.persona_id,
            persona_text=request.persona_text or (template.persona_text if template else ""),
            role_card=request.role_card,
            persona_profile=request.persona_profile or (template.persona_profile if template else None),
            agent_id=request.agent_id,
            llm_model_id=llm_config.model_id if llm_config else None,
            llm_base_url=llm_config.base_url if llm_config else None,
            has_llm_api_key=llm_config is not None,
        )
        return session, llm_config

    existing_llm = get_session_llm_config(request.session_id)
    template = get_persona_template(request.persona_id) if request.persona_id else None
    if request.agent_id:
        resolve_agent_profile(request.agent_id)
    llm_config = resolve_llm_config(
        existing_llm,
        api_key=request.llm_config.api_key if request.llm_config else None,
        base_url=request.llm_config.base_url if request.llm_config else None,
        model_id=request.llm_config.model_id if request.llm_config else None,
        timeout=request.llm_config.timeout if request.llm_config else None,
    )
    session = existing.model_copy(
        update={
            "app_user_id": app_user_id,
            "profile_id": app_user_id,
            "persona_id": (
                request.persona_id
                if request.persona_id is not None
                else (
                    None
                    if request.persona_text is not None or request.persona_profile is not None or request.role_card is not None
                    else existing.persona_id
                )
            ),
            "persona_text": request.persona_text or (template.persona_text if template else existing.persona_text),
            "role_card": request.role_card if request.role_card is not None else existing.role_card,
            "persona_profile": request.persona_profile or (template.persona_profile if template else existing.persona_profile),
            "agent_id": request.agent_id if request.agent_id is not None else existing.agent_id,
            "llm_model_id": llm_config.model_id if llm_config else existing.llm_model_id,
            "llm_base_url": llm_config.base_url if llm_config else existing.llm_base_url,
            "has_llm_api_key": llm_config is not None or existing.has_llm_api_key,
        }
    )
    return session, llm_config


def _resolve_app_user_id(request: ChatSendRequest, existing: SessionState | None) -> str:
    return (
        request.app_user_id
        or request.profile_id
        or (existing.app_user_id if existing is not None else None)
        or (existing.profile_id if existing is not None else None)
        or settings.default_app_user_id
    )
