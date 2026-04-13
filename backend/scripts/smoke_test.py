from __future__ import annotations

import argparse
import json
import time
from uuid import uuid4

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the LoveBeats backend over HTTP.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    suffix = uuid4().hex[:8]
    session_id = f"smoke_session_{suffix}"
    profile_id = f"smoke_profile_{suffix}"

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        _request(client, "GET", "/health")
        _request(
            client,
            "POST",
            "/v1/sessions",
            {
                "session_id": session_id,
                "profile_id": profile_id,
                "title": "Smoke Test Window",
                "persona_text": "像恋人一样聊天，温柔一点，可以接住情绪。",
                "persona_profile": {
                    "display_name": "阿昼",
                    "user_nickname": "宝宝",
                    "comfort_hint": "先抱住情绪，再慢慢回应。",
                },
            },
        )
        _request(
            client,
            "POST",
            "/v1/heart-rate/latest",
            {
                "profile_id": profile_id,
                "bpm": 98,
            },
        )
        debug = _request(
            client,
            "POST",
            "/v1/turns/debug",
            {
                "session_id": session_id,
                "profile_id": profile_id,
                "user_message": "我刚刚有点紧张，心跳很快。",
                "idle_seconds": 26,
            },
        )
        _assert(debug["runtime"]["session_id"] == session_id, "turn debug session_id mismatch")
        _assert(debug["prompt_messages"], "turn debug prompt messages empty")

        chat = _request(
            client,
            "POST",
            "/v1/chat/send",
            {
                "session_id": session_id,
                "profile_id": profile_id,
                "user_message": "我刚刚有点紧张，心跳很快。",
                "idle_seconds": 26,
            },
        )
        _assert(chat["reply"], "chat reply is empty")

        time.sleep(0.05)
        history = _request(client, "GET", f"/v1/sessions/{session_id}/history")
        _assert(len(history["messages"]) == 2, "history length should be 2 after one turn")

    print("\nSmoke test passed.")
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
