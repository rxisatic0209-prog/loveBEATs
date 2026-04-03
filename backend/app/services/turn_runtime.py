from __future__ import annotations

from fastapi import HTTPException

from app.config import settings
from app.models import (
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    LLMConfigResolved,
    LLMConfigSummary,
    MessageRole,
    PromptMessage,
    RuntimePolicy,
    SessionCreateRequest,
    SessionState,
    TurnDebugSnapshot,
    TurnRuntime,
)
from app.prompts import build_runtime_context_prompt, build_system_prompt
from app.services.agent_scaffold import build_agent_scaffold
from app.services.heart_rate import get_latest_heart_rate
from app.services.llm import build_assistant_tool_call_message, build_tool_result_message, call_llm, resolve_llm_config
from app.services.persona import compile_persona
from app.services.session import (
    append_message,
    create_or_update_session,
    get_recent_messages,
    get_session,
    get_session_llm_config,
    get_session_optional,
    touch_session,
)
from app.services.tool_registry import get_runtime_tools


def create_turn_runtime(
    request: ChatSendRequest,
    *,
    persist_session: bool = True,
) -> TurnRuntime:
    session, llm_config = _resolve_session_snapshot(request, persist_session=persist_session)
    persona = compile_persona(session.persona_text, session.persona_profile)
    scaffold = build_agent_scaffold()
    policy = RuntimePolicy()
    model_id = llm_config.model_id if llm_config else "mock-local"
    previous_messages = get_recent_messages(session.session_id, settings.session_message_window - 1) if get_session_optional(session.session_id) else []
    current_message = ChatMessage(role=MessageRole.user, content=request.user_message)
    recent_messages = [*previous_messages, current_message][-settings.session_message_window :]
    enabled_tool_names = {item.name for item in get_runtime_tools(policy)}
    runtime_tools = [tool for tool in scaffold.tool_registry if tool.name in enabled_tool_names]

    return TurnRuntime(
        session_id=session.session_id,
        profile_id=session.profile_id,
        model_id=model_id,
        persona=persona,
        system_prompt=build_system_prompt(persona.compiled_prompt),
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


async def run_turn_runtime(runtime: TurnRuntime) -> ChatSendResponse:
    llm_config = get_session_llm_config(runtime.session_id)
    append_message(runtime.session_id, role=MessageRole.user, content=runtime.current_user_message)

    messages = [{"role": "system", "content": runtime.system_prompt}]
    messages.append(
        {
            "role": "system",
            "content": build_runtime_context_prompt(
                idle_seconds=runtime.idle_seconds,
                tool_names=[tool.name for tool in runtime.tools],
            ),
        }
    )
    for item in runtime.recent_messages:
        messages.append({"role": item.role.value, "content": item.content})

    model_used, first_pass = await call_llm(
        llm_config,
        messages,
        tools=runtime.tools,
        allow_tools=bool(runtime.tools) and runtime.policy.tool_call_limit > 0,
    )
    tool_used = False
    heart_rate = None

    if (
        first_pass.tool_name == "get_heart_rate"
        and runtime.policy.heart_rate.enabled
        and runtime.policy.heart_rate.max_call_per_turn > 0
    ):
        tool_used = True
        heart_rate = get_latest_heart_rate(runtime.profile_id)
        payload = heart_rate.model_dump(mode="json")
        payload["_tool_call_id"] = first_pass.tool_call_id or "mock_tool_call_id"
        messages.append(
            build_assistant_tool_call_message(
                tool_name="get_heart_rate",
                tool_call_id=first_pass.tool_call_id,
            )
        )
        messages.append(build_tool_result_message("get_heart_rate", payload))
        messages.append(
            {
                "role": "system",
                "content": (
                    "如果心率状态不是 fresh 或 recent，请忽略它，优先按当前对话回复。"
                    "不要把心率说成诊断。"
                ),
            }
        )
        _, second_pass = await call_llm(
            llm_config,
            messages,
            tools=runtime.tools,
            allow_tools=False,
        )
        reply = second_pass.content or "我在这里。"
    else:
        reply = first_pass.content or "我在这里。"

    if heart_rate and heart_rate.status.value not in {"fresh", "recent"}:
        heart_rate = None

    append_message(runtime.session_id, role=MessageRole.assistant, content=reply)
    touch_session(runtime.session_id)

    return ChatSendResponse(
        session_id=runtime.session_id,
        model_used=model_used,
        tool_used=tool_used,
        heart_rate=heart_rate,
        reply=reply,
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
    if existing is not None:
        existing_llm = get_session_llm_config(session_id)
    else:
        existing_llm = None
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


def _resolve_session_snapshot(
    request: ChatSendRequest,
    *,
    persist_session: bool,
) -> tuple[SessionState, LLMConfigResolved | None]:
    existing = get_session_optional(request.session_id)
    if existing is None and not request.persona_text:
        raise HTTPException(status_code=400, detail="persona_text is required for a new session")

    if persist_session:
        if existing is None:
            create_or_update_session(
                SessionCreateRequest(
                    session_id=request.session_id,
                    profile_id=request.profile_id,
                    persona_text=request.persona_text or "",
                    persona_profile=request.persona_profile,
                    llm_config=request.llm_config,
                )
            )
        else:
            create_or_update_session(
                SessionCreateRequest(
                    session_id=request.session_id,
                    profile_id=request.profile_id,
                    title=existing.title,
                    persona_text=request.persona_text or existing.persona_text,
                    persona_profile=request.persona_profile or existing.persona_profile,
                    llm_config=request.llm_config,
                )
            )
        session = get_session(request.session_id)
        return session, get_session_llm_config(request.session_id)

    if existing is None:
        llm_config = resolve_llm_config(
            None,
            api_key=request.llm_config.api_key if request.llm_config else None,
            base_url=request.llm_config.base_url if request.llm_config else None,
            model_id=request.llm_config.model_id if request.llm_config else None,
            timeout=request.llm_config.timeout if request.llm_config else None,
        )
        session = SessionState(
            session_id=request.session_id,
            profile_id=request.profile_id,
            persona_text=request.persona_text or "",
            persona_profile=request.persona_profile,
            llm_model_id=llm_config.model_id if llm_config else None,
            llm_base_url=llm_config.base_url if llm_config else None,
            has_llm_api_key=llm_config is not None,
        )
        return session, llm_config

    existing_llm = get_session_llm_config(request.session_id)
    llm_config = resolve_llm_config(
        existing_llm,
        api_key=request.llm_config.api_key if request.llm_config else None,
        base_url=request.llm_config.base_url if request.llm_config else None,
        model_id=request.llm_config.model_id if request.llm_config else None,
        timeout=request.llm_config.timeout if request.llm_config else None,
    )
    session = existing.model_copy(
        update={
            "profile_id": request.profile_id,
            "persona_text": request.persona_text or existing.persona_text,
            "persona_profile": request.persona_profile or existing.persona_profile,
            "llm_model_id": llm_config.model_id if llm_config else existing.llm_model_id,
            "llm_base_url": llm_config.base_url if llm_config else existing.llm_base_url,
            "has_llm_api_key": llm_config is not None or existing.has_llm_api_key,
        }
    )
    return session, llm_config
