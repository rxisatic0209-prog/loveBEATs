from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models import LLMConfigResolved, LLMReply, ToolDefinition


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
        self.model = model or os.getenv("LLM_MODEL_ID") or settings.llm_model_id
        self.api_key = api_key or os.getenv("LLM_API_KEY") or settings.llm_api_key
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or settings.llm_base_url
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", str(settings.llm_timeout)))

        if client is not None:
            self.client = client
            return

        if not all([self.model, self.api_key, self.base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在环境变量中定义。")

        self.client = OpenAI(
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


def resolve_llm_config(
    incoming: LLMConfigResolved | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_id: str | None = None,
    timeout: int | None = None,
) -> LLMConfigResolved | None:
    merged_api_key = api_key or (incoming.api_key if incoming else None) or settings.llm_api_key
    merged_base_url = base_url or (incoming.base_url if incoming else None) or settings.llm_base_url
    merged_model_id = model_id or (incoming.model_id if incoming else None) or settings.llm_model_id
    merged_timeout = timeout or (incoming.timeout if incoming else None) or settings.llm_timeout

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
        return "mock-local", _mock_reply(messages, allow_tools)

    client = LLM(
        model=llm_config.model_id,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
    )
    serialized_tools = _serialize_tools(tools or [])
    response = await run_in_threadpool(
        client.complete,
        messages,
        temperature=0.1,
        tools=serialized_tools,
        allow_tools=allow_tools,
    )
    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        tool_call = tool_calls[0]
        tool_name = getattr(getattr(tool_call, "function", None), "name", None)
        return llm_config.model_id, LLMReply(
            tool_name=tool_name,
            tool_call_id=getattr(tool_call, "id", None),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )
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
