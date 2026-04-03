import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import reset_db
from app.main import app


class PulseAgentAPITest(unittest.TestCase):
    def setUp(self) -> None:
        reset_db()
        self.client = TestClient(app)

    def test_agent_scaffold_endpoint(self) -> None:
        response = self.client.get("/v1/agent/scaffold")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tool_registry", data)
        self.assertEqual(data["tool_registry"][0]["name"], "get_heart_rate")

    def test_turn_preview_does_not_persist_messages(self) -> None:
        preview_response = self.client.post(
            "/v1/turns/preview",
            json={
                "session_id": "s_preview",
                "profile_id": "p_preview",
                "persona_text": "像恋人一样聊天，温柔一点。",
                "user_message": "你在想我吗？",
                "idle_seconds": 18,
            },
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()
        self.assertEqual(preview["current_user_message"], "你在想我吗？")
        self.assertEqual(preview["recent_messages"][-1]["role"], "user")

        session_response = self.client.get("/v1/sessions/s_preview")
        self.assertEqual(session_response.status_code, 404)

    def test_turn_debug_returns_prompt_and_warnings(self) -> None:
        debug_response = self.client.post(
            "/v1/turns/debug",
            json={
                "session_id": "s_debug",
                "profile_id": "p_debug",
                "persona_text": "像恋人一样聊天，温柔一点。",
                "user_message": "我有点想你。",
                "idle_seconds": 12,
            },
        )
        self.assertEqual(debug_response.status_code, 200)
        data = debug_response.json()
        self.assertEqual(data["runtime"]["current_user_message"], "我有点想你。")
        self.assertEqual(data["prompt_messages"][0]["role"], "system")
        self.assertEqual(data["llm"]["source"], "mock-local")
        self.assertTrue(data["warnings"])

    def test_smoke_script_exists(self) -> None:
        script_path = Path("/Users/rxie/Desktop/loveBEATs/backend/scripts/smoke_test.py")
        self.assertTrue(script_path.exists())

    def test_heart_rate_simulator_script_exists(self) -> None:
        script_path = Path("/Users/rxie/Desktop/loveBEATs/backend/scripts/heart_rate_simulator.py")
        self.assertTrue(script_path.exists())

    def test_ios_healthkit_skeleton_exists(self) -> None:
        base = Path("/Users/rxie/Desktop/loveBEATs/ios/PulseAgentIOS")
        self.assertTrue((base / "PulseAgentApp.swift").exists())
        self.assertTrue((base / "Services/HealthKitHeartRateService.swift").exists())
        self.assertTrue((base / "ViewModels/HeartRateSyncViewModel.swift").exists())
        self.assertTrue((base / "Support/PulseAgent.entitlements").exists())

    def test_persona_compile_with_profile(self) -> None:
        response = self.client.post(
            "/v1/persona/compile",
            json={
                "persona_text": "像恋人一样自然聊天，温柔一点，不要说教。",
                "persona_profile": {
                    "display_name": "阿昼",
                    "relation_mode": "你是用户的年上恋人，稳定、克制、有照顾感。",
                    "user_nickname": "宝宝",
                    "tone_hint": "轻柔、亲密，不要过火。",
                    "affection_style": "直接表达喜欢，但不要油腻。",
                    "expression_level": "偏高",
                    "taboo_list": ["不说教", "不冷暴力"],
                    "lexicon_list": ["笨蛋", "乖一点"],
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("阿昼", data["compiled_prompt"])
        self.assertIn("宝宝", data["compiled_prompt"])
        self.assertEqual(data["taboos"], ["不说教", "不冷暴力", "不训斥", "不做医学判断"])
        self.assertEqual(data["lexicon"], ["笨蛋", "乖一点"])
        self.assertEqual(data["expression_level"], "偏高")

    def test_session_lifecycle_and_chat(self) -> None:
        create_response = self.client.post(
            "/v1/sessions",
            json={
                "session_id": "s_001",
                "profile_id": "p_001",
                "title": "默认恋人",
                "persona_text": "像恋人一样聊天，温柔一点，可以接住情绪。",
            },
        )
        self.assertEqual(create_response.status_code, 200)

        hr_response = self.client.post(
            "/v1/heart-rate/latest",
            json={"profile_id": "p_001", "bpm": 96},
        )
        self.assertEqual(hr_response.status_code, 200)
        self.assertEqual(hr_response.json()["status"], "fresh")

        chat_response = self.client.post(
            "/v1/chat/send",
            json={
                "session_id": "s_001",
                "profile_id": "p_001",
                "user_message": "我刚刚有点紧张，心跳好快。",
                "idle_seconds": 42,
            },
        )
        self.assertEqual(chat_response.status_code, 200)
        data = chat_response.json()
        self.assertTrue(data["tool_used"])
        self.assertEqual(data["heart_rate"]["status"], "fresh")
        self.assertIn("占位回复", data["reply"])

        history_response = self.client.get("/v1/sessions/s_001/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(len(history["messages"]), 2)
        self.assertEqual(history["messages"][0]["role"], "user")
        self.assertEqual(history["messages"][1]["role"], "assistant")

    def test_session_accepts_user_llm_config(self) -> None:
        response = self.client.post(
            "/v1/sessions",
            json={
                "session_id": "s_003",
                "profile_id": "p_003",
                "title": "用户自填模型",
                "persona_text": "像恋人一样聊天。",
                "llm_config": {
                    "api_key": "sk-test",
                    "base_url": "https://aihubmix.com/v1",
                    "model_id": "coding-glm-5-free",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["llm_model_id"], "coding-glm-5-free")
        self.assertEqual(data["llm_base_url"], "https://aihubmix.com/v1")
        self.assertTrue(data["has_llm_api_key"])

    def test_sqlite_persists_across_clients(self) -> None:
        self.client.post(
            "/v1/sessions",
            json={
                "session_id": "s_004",
                "profile_id": "p_004",
                "persona_text": "像恋人一样聊天，安静一点。",
            },
        )
        self.client.post(
            "/v1/chat/send",
            json={
                "session_id": "s_004",
                "profile_id": "p_004",
                "user_message": "你还在吗？",
            },
        )

        second_client = TestClient(app)
        history_response = second_client.get("/v1/sessions/s_004/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(history["session"]["session_id"], "s_004")
        self.assertEqual(len(history["messages"]), 2)

    def test_new_session_requires_persona(self) -> None:
        response = self.client.post(
            "/v1/chat/send",
            json={
                "session_id": "s_002",
                "profile_id": "p_002",
                "user_message": "你好。",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "persona_text is required for a new session")


if __name__ == "__main__":
    unittest.main()
