from __future__ import annotations

import argparse
import json
from uuid import uuid4

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test persona templates + agent profiles over HTTP.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    suffix = uuid4().hex[:8]
    role_id = f"persona_agent_role_{suffix}"

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        _request(client, "GET", "/health")

        persona = _request(
            client,
            "POST",
            "/v1/personas",
            {
                "name": "年上恋人模板",
                "description": "稳定、温柔、稍微克制。",
                "persona_text": "像恋人一样聊天，年上感，温柔一点，不要说教。",
                "persona_profile": {
                    "display_name": "阿昼",
                    "user_nickname": "宝宝",
                    "comfort_hint": "先抱住情绪，再慢慢回应。",
                    "lexicon_list": ["乖一点"],
                },
            },
        )
        persona_id = persona["persona_id"]

        agent = _request(
            client,
            "POST",
            "/v1/agents",
            {
                "name": "轻陪伴 Agent",
                "description": "弱工具、轻控制。",
                "system_preamble": "优先自然、松弛、贴近真人关系，不要像任务型助手。",
                "tool_call_limit": 1,
                "heart_rate_enabled": True,
                "heart_rate_max_call_per_turn": 1,
                "allow_stale_heart_rate": False,
            },
        )
        agent_id = agent["agent_id"]

        role = _request(
            client,
            "POST",
            "/v1/roles",
            {
                "role_id": role_id,
                "title": "Persona + Agent Smoke",
                "persona_id": persona_id,
                "agent_id": agent_id,
            },
        )
        _assert(role["persona_id"] == persona_id, "role persona binding mismatch")
        _assert(role["agent_id"] == agent_id, "role agent binding mismatch")

        debug = _request(
            client,
            "POST",
            "/v1/turns/debug",
            {
                "role_id": role_id,
                "user_message": "刚刚有点紧张，想让你陪我说说话。",
                "idle_seconds": 33,
            },
        )
        _assert(debug["runtime"]["agent"]["agent_id"] == agent_id, "runtime agent mismatch")
        _assert(debug["runtime"]["persona"]["assistant_name"] == "阿昼", "runtime persona mismatch")
        _assert("优先自然、松弛" in debug["runtime"]["system_prompt"], "agent preamble missing")

        chat = _request(
            client,
            "POST",
            "/v1/chat/send",
            {
                "role_id": role_id,
                "user_message": "刚刚有点紧张，想让你陪我说说话。",
                "idle_seconds": 33,
            },
        )
        _assert(chat["reply"], "chat reply is empty")

    print("\nPersona/agent smoke test passed.")
    return 0


def _request(client: httpx.Client, method: str, path: str, payload: dict | None = None) -> dict:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    data = response.json()
    print(f"{method} {path}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()
    return data


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
