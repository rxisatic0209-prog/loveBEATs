from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from openai import APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError, OpenAI, PermissionDeniedError, RateLimitError
from starlette.concurrency import run_in_threadpool

from app.agent.config import agent_settings
from app.logging_setup import get_logger
from app.models import LLMConfigResolved, LLMReply, ToolDefinition

logger = get_logger("pulseagent.llm")


class LLMCallError(Exception):
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class LLM:
    """
    项目的 LLM 基建层。
    负责：
    - 构造 OpenAI 兼容客户端
    - 统一模型调用接口
    - 将业务层与具体 SDK 解耦
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        client: OpenAI | None = None,
    ):
        self.model = model or agent_settings.llm_model_id
        self.api_key = api_key or agent_settings.llm_api_key
        self.base_url = base_url or agent_settings.llm_base_url
        self.timeout = timeout or agent_settings.llm_timeout

        if client is not None:
            self.client = client
            return

        if not all([self.model, self.api_key, self.base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在环境变量中定义。")

        self.client = get_openai_client(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def think(self, messages: list[dict[str, Any]], temperature: float = 0.1) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.1,
        tools: list[dict[str, Any]] | None = None,
        allow_tools: bool = True,
    ):
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if allow_tools and tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return self.client.chat.completions.create(**payload)


def default_llm_config() -> LLMConfigResolved | None:
    if not all([agent_settings.llm_api_key, agent_settings.llm_base_url, agent_settings.llm_model_id]):
        return None

    return LLMConfigResolved(
        api_key=agent_settings.llm_api_key,
        base_url=agent_settings.llm_base_url,
        model_id=agent_settings.llm_model_id,
        timeout=agent_settings.llm_timeout,
    )


@lru_cache(maxsize=8)
def get_openai_client(api_key: str, base_url: str, timeout: int) -> OpenAI:
    logger.info("create llm client base_url=%s timeout=%s", base_url, timeout)
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )


def resolve_llm_config(
    incoming: LLMConfigResolved | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_id: str | None = None,
    timeout: int | None = None,
) -> LLMConfigResolved | None:
    defaults = default_llm_config()

    merged_api_key = api_key or (incoming.api_key if incoming else None) or (defaults.api_key if defaults else None)
    merged_base_url = base_url or (incoming.base_url if incoming else None) or (defaults.base_url if defaults else None)
    merged_model_id = model_id or (incoming.model_id if incoming else None) or (defaults.model_id if defaults else None)
    merged_timeout = timeout or (incoming.timeout if incoming else None) or (defaults.timeout if defaults else agent_settings.llm_timeout)

    if not all([merged_api_key, merged_base_url, merged_model_id]):
        return None

    return LLMConfigResolved(
        api_key=merged_api_key,
        base_url=merged_base_url,
        model_id=merged_model_id,
        timeout=merged_timeout,
    )


async def call_llm(
    llm_config: LLMConfigResolved | None,
    messages: list[dict],
    tools: list[ToolDefinition] | None = None,
    allow_tools: bool = True,
) -> tuple[str, LLMReply]:
    if llm_config is None:
        logger.warning("llm config missing, fallback to mock-local")
        return "mock-local", _mock_reply(messages, allow_tools)

    client = LLM(
        model=llm_config.model_id,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
    )
    serialized_tools = _serialize_tools(tools or [])
    logger.info(
        "llm call start model=%s allow_tools=%s tool_count=%s message_count=%s",
        llm_config.model_id,
        allow_tools,
        len(serialized_tools),
        len(messages),
    )
    try:
        response = await run_in_threadpool(
            client.complete,
            messages,
            temperature=0.1,
            tools=serialized_tools,
            allow_tools=allow_tools,
        )
    except BadRequestError as error:
        logger.warning("llm bad request model=%s detail=%s", llm_config.model_id, _format_bad_request_error(error))
        raise LLMCallError(_format_bad_request_error(error), status_code=400) from error
    except AuthenticationError as error:
        logger.warning("llm authentication failed model=%s", llm_config.model_id)
        raise LLMCallError("模型调用失败：LLM_API_KEY 无效或已失效。请检查 backend/.env。", status_code=401) from error
    except PermissionDeniedError as error:
        logger.warning("llm permission denied model=%s", llm_config.model_id)
        raise LLMCallError("模型调用失败：当前 key 没有权限访问这个模型或服务。", status_code=403) from error
    except RateLimitError as error:
        logger.warning("llm rate limited model=%s", llm_config.model_id)
        raise LLMCallError("模型调用失败：请求过于频繁或额度不足。请稍后重试。", status_code=429) from error
    except APITimeoutError as error:
        logger.warning("llm timeout model=%s timeout=%s", llm_config.model_id, llm_config.timeout)
        raise LLMCallError("模型调用超时。请稍后再试，或检查 LLM_TIMEOUT 设置。", status_code=504) from error
    except APIConnectionError as error:
        logger.warning("llm connection failed model=%s base_url=%s", llm_config.model_id, llm_config.base_url)
        raise LLMCallError("模型连接失败。请检查 LLM_BASE_URL 和当前网络。", status_code=502) from error
    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        tool_call = tool_calls[0]
        tool_name = getattr(getattr(tool_call, "function", None), "name", None)
        logger.info("llm call requested tool model=%s tool=%s", llm_config.model_id, tool_name)
        return llm_config.model_id, LLMReply(
            tool_name=tool_name,
            tool_call_id=getattr(tool_call, "id", None),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )
    logger.info("llm call completed model=%s content_length=%s", llm_config.model_id, len(getattr(message, "content", "") or ""))
    return llm_config.model_id, LLMReply(
        content=getattr(message, "content", "") or "",
        raw=response.model_dump() if hasattr(response, "model_dump") else None,
    )


def _mock_reply(messages: list[dict], allow_tools: bool) -> LLMReply:
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if allow_tools and any(keyword in last_user_message for keyword in ("难受", "心跳", "紧张", "情绪", "沉默")):
        return LLMReply(tool_name="get_heart_rate", raw={"mock": True})
    return LLMReply(
        content=f"这是本地占位回复：我收到你说的“{last_user_message[:80]}”。现在还没接入真实模型，但链路已经可以联调。",
        raw={"mock": True},
    )


def _serialize_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def build_tool_result_message(tool_name: str, payload: dict) -> dict:
    return {
        "role": "tool",
        "tool_call_id": payload.pop("_tool_call_id", "mock_tool_call_id"),
        "content": json.dumps(payload, ensure_ascii=False),
    }


def build_assistant_tool_call_message(tool_name: str, tool_call_id: str | None) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": tool_call_id or "mock_tool_call_id",
                "type": "function",
                "function": {"name": tool_name, "arguments": "{}"},
            }
        ],
    }


def _format_bad_request_error(error: BadRequestError) -> str:
    error_message = str(error)
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body_error = body.get("error")
        if isinstance(body_error, dict):
            error_message = body_error.get("message") or error_message
    lowered = error_message.lower()
    if "incorrect model id" in lowered or "do not have permission to use this model" in lowered:
        return "模型调用失败：当前 LLM_MODEL_ID 不可用，或当前 key 没有权限使用它。请检查 backend/.env。"
    return f"模型调用失败：{error_message}"
