from app.agent.llm import build_assistant_tool_call_message, build_tool_result_message, call_llm
from app.logging_setup import get_logger
from app.memory.session_store import append_message, get_session_llm_config, touch_session
from app.models import ChatSendResponse, MessageRole, TurnRuntime
from app.system.guardrails import build_runtime_context_prompt
from app.tools.heart_rate import execute_get_heart_rate

logger = get_logger("pulseagent.runtime")


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
        logger.info("runtime tool call role_id=%s tool=get_heart_rate", runtime.role_id)
        heart_rate = execute_get_heart_rate(runtime.role_id)
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
    logger.info(
        "runtime reply role_id=%s model=%s tool_used=%s reply_length=%s",
        runtime.role_id,
        model_used,
        tool_used,
        len(reply),
    )

    return ChatSendResponse(
        role_id=runtime.role_id,
        app_user_id=runtime.app_user_id,
        session_id=runtime.session_id,
        model_used=model_used,
        tool_used=tool_used,
        heart_rate=heart_rate,
        reply=reply,
    )
