import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.db import reset_db
from app.agent.llm import LLMCallError
from app.main import app


class LoveBeatsAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_llm_settings = (
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model_id,
            settings.llm_timeout,
        )
        self._original_sqlite_path = settings.sqlite_path
        self._temp_dir = TemporaryDirectory()
        settings.sqlite_path = str(Path(self._temp_dir.name) / "LoveBeats.test.db")
        settings.llm_api_key = None
        settings.llm_base_url = None
        settings.llm_model_id = None
        settings.llm_timeout = 60
        reset_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        (
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model_id,
            settings.llm_timeout,
        ) = self._original_llm_settings
        settings.sqlite_path = self._original_sqlite_path
        self._temp_dir.cleanup()

    def test_agent_scaffold_endpoint(self) -> None:
        response = self.client.get("/v1/agent/scaffold")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tool_registry", data)
        self.assertEqual(data["tool_registry"][0]["name"], "get_heart_rate")

    def test_heart_rate_tool_provider_defaults_to_local_cache(self) -> None:
        response = self.client.get("/v1/tools/heart-rate/provider")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider"], "local_cache")
        self.assertEqual(data["transport"], "internal")
        self.assertEqual(data["host_platform"], "backend")
        self.assertTrue(data["ready"])

    def test_chat_page_exists(self) -> None:
        response = self.client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("LoveBeats Chat", response.text)

    def test_turn_preview_does_not_persist_messages(self) -> None:
        preview_response = self.client.post(
            "/v1/turns/preview",
            json={
                "role_id": "role_preview",
                "persona_text": "像恋人一样聊天，温柔一点。",
                "user_message": "你在想我吗？",
                "idle_seconds": 18,
            },
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()
        self.assertEqual(preview["current_user_message"], "你在想我吗？")
        self.assertEqual(preview["recent_messages"][-1]["role"], "user")

        role_response = self.client.get("/v1/roles/role_preview")
        self.assertEqual(role_response.status_code, 404)

    def test_turn_debug_returns_prompt_and_warnings(self) -> None:
        debug_response = self.client.post(
            "/v1/turns/debug",
            json={
                "role_id": "role_debug",
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
        self.assertIn("严禁 OOC（Out Of Character）。必须始终贴合角色身份、语气、背景、经历进行表达。", data["runtime"]["system_prompt"])
        self.assertIn("信息获取应遵循现实逻辑：只能知道通过合理途径获得的信息。", data["runtime"]["system_prompt"])

    def test_smoke_script_exists(self) -> None:
        script_path = Path("/Users/rxie/Desktop/loveBEATs/backend/scripts/smoke_test.py")
        self.assertTrue(script_path.exists())

    def test_heart_rate_simulator_script_exists(self) -> None:
        script_path = Path("/Users/rxie/Desktop/loveBEATs/backend/scripts/heart_rate_simulator.py")
        self.assertTrue(script_path.exists())

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
        self.assertIn("[角色身份]", data["compiled_prompt"])
        self.assertIn("[扮演摘要]", data["compiled_prompt"])
        self.assertEqual(data["taboos"], ["不说教", "不冷暴力", "不做医学判断", "不跳出角色", "不擅自改写设定"])
        self.assertEqual(data["lexicon"], ["笨蛋", "乖一点"])
        self.assertEqual(data["expression_level"], "偏高")

    def test_persona_template_crud(self) -> None:
        create_response = self.client.post(
            "/v1/personas",
            json={
                "name": "年上恋人",
                "description": "稳定照顾型",
                "persona_text": "像年上恋人一样聊天，温柔克制。",
                "persona_profile": {
                    "display_name": "阿昼",
                    "user_nickname": "宝宝",
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        self.assertTrue(created["persona_id"].startswith("persona_"))

        list_response = self.client.get("/v1/personas")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        update_response = self.client.put(
            f"/v1/personas/{created['persona_id']}",
            json={"name": "年上恋人Plus", "persona_text": "更自然一点。"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["name"], "年上恋人Plus")

        delete_response = self.client.delete(f"/v1/personas/{created['persona_id']}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["ok"], True)

    def test_agent_profile_crud_and_runtime_binding(self) -> None:
        persona_response = self.client.post(
            "/v1/personas",
            json={
                "name": "测试 persona",
                "persona_text": "像恋人一样聊天，安静一点。",
            },
        )
        persona_id = persona_response.json()["persona_id"]

        agent_response = self.client.post(
            "/v1/agents",
            json={
                "name": "无心率 agent",
                "description": "禁用心率工具",
                "system_preamble": "优先用更日常、更轻的关系表达。",
                "tool_call_limit": 0,
                "heart_rate_enabled": False,
                "heart_rate_max_call_per_turn": 0,
                "allow_stale_heart_rate": False,
            },
        )
        self.assertEqual(agent_response.status_code, 200)
        agent = agent_response.json()
        self.assertTrue(agent["agent_id"].startswith("agent_"))

        preview_response = self.client.post(
            "/v1/turns/preview",
            json={
                "role_id": "role_agent_preview",
                "persona_id": persona_id,
                "agent_id": agent["agent_id"],
                "user_message": "你会不会想我？",
            },
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()
        self.assertEqual(preview["agent"]["agent_id"], agent["agent_id"])
        self.assertEqual(preview["policy"]["tool_call_limit"], 0)
        self.assertFalse(preview["policy"]["heart_rate"]["enabled"])
        self.assertEqual(preview["tools"], [])
        self.assertIn("更日常、更轻的关系表达", preview["system_prompt"])

    def test_role_can_bind_persona_and_agent(self) -> None:
        persona_response = self.client.post(
            "/v1/personas",
            json={
                "name": "夜间陪伴",
                "persona_text": "像恋人一样聊天，夜里更安静一点。",
            },
        )
        agent_response = self.client.post(
            "/v1/agents",
            json={
                "name": "轻回应 agent",
                "tool_call_limit": 0,
                "heart_rate_enabled": False,
                "heart_rate_max_call_per_turn": 0,
            },
        )

        create_response = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_bound",
                "persona_id": persona_response.json()["persona_id"],
                "agent_id": agent_response.json()["agent_id"],
            },
        )
        self.assertEqual(create_response.status_code, 200)
        role = create_response.json()
        self.assertEqual(role["persona_id"], persona_response.json()["persona_id"])
        self.assertEqual(role["agent_id"], agent_response.json()["agent_id"])
        self.assertEqual(role["persona_text"], "像恋人一样聊天，夜里更安静一点。")

    def test_role_lifecycle_uses_role_id_as_memory_boundary(self) -> None:
        create_response = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_001",
                "title": "深夜恋人",
                "persona_text": "像恋人一样聊天，深夜更轻一点。",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        role = create_response.json()
        self.assertEqual(role["role_id"], "role_001")
        self.assertEqual(role["persona_text"], "像恋人一样聊天，深夜更轻一点。")

        chat_response = self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_001",
                "user_message": "你醒着吗？",
            },
        )
        self.assertEqual(chat_response.status_code, 200)
        data = chat_response.json()
        self.assertEqual(data["role_id"], "role_001")

        history_response = self.client.get("/v1/roles/role_001/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(history["role"]["role_id"], "role_001")
        self.assertEqual(len(history["messages"]), 2)

    def test_roles_list_returns_latest_first(self) -> None:
        first = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_list_001",
                "persona_text": "像恋人一样聊天，温柔一点。",
            },
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_list_002",
                "persona_text": "像恋人一样聊天，安静一点。",
            },
        )
        self.assertEqual(second.status_code, 200)

        response = self.client.get("/v1/roles")
        self.assertEqual(response.status_code, 200)
        roles = response.json()
        self.assertEqual(len(roles), 2)
        self.assertEqual(roles[0]["role_id"], "role_list_002")
        self.assertEqual(roles[1]["role_id"], "role_list_001")

    def test_role_card_creation_persists_structured_fields(self) -> None:
        create_response = self.client.post(
            "/v1/roles",
            json={
                "role_card": {
                    "name": "阿昼",
                    "user_nickname": "宝宝",
                    "background": "你是用户的年上恋人，关系稳定克制，已经相处很久。",
                    "trait_profile": "温柔、稳定、慢热，会先理解情绪。",
                    "attachment_style": "安全型，亲近但不控制。",
                    "major_life_events": "长期承担照顾者角色，对逞强和疲惫更敏感。",
                    "response_style": "轻柔、自然、不要说教；先接住情绪，再自然延展；中等偏主动，会追问一点点。",
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        role = create_response.json()
        self.assertTrue(role["role_id"].startswith("role_"))
        self.assertEqual(role["role_card"]["name"], "阿昼")
        self.assertEqual(role["role_card"]["trait_profile"], "温柔、稳定、慢热，会先理解情绪。")
        self.assertEqual(role["role_card"]["major_life_events"], "长期承担照顾者角色，对逞强和疲惫更敏感。")
        self.assertEqual(
            role["role_card"]["response_style"],
            "轻柔、自然、不要说教；先接住情绪，再自然延展；中等偏主动，会追问一点点。",
        )
        self.assertIn("背景设定", role["persona_text"])
        self.assertIn("角色个人重大事件", role["persona_text"])
        self.assertIn("回答风格", role["persona_text"])

        get_response = self.client.get(f"/v1/roles/{role['role_id']}")
        self.assertEqual(get_response.status_code, 200)
        loaded = get_response.json()
        self.assertEqual(loaded["role_card"]["background"], "你是用户的年上恋人，关系稳定克制，已经相处很久。")

    def test_role_card_creation_with_only_name_is_allowed(self) -> None:
        create_response = self.client.post(
            "/v1/roles",
            json={
                "role_card": {
                    "name": "阿昼",
                },
            },
        )
        self.assertEqual(create_response.status_code, 200)
        role = create_response.json()
        self.assertEqual(role["role_card"]["name"], "阿昼")
        self.assertIsNone(role["role_card"]["background"])
        self.assertIsNone(role["role_card"]["trait_profile"])
        self.assertIn("角色名：阿昼", role["persona_text"])

    def test_chat_send_returns_readable_llm_error(self) -> None:
        role_response = self.client.post(
            "/v1/roles",
            json={"role_card": {"name": "阿昼"}},
        )
        self.assertEqual(role_response.status_code, 200)
        role_id = role_response.json()["role_id"]

        with patch(
            "app.main.handle_chat",
            new=AsyncMock(side_effect=LLMCallError("模型调用失败：当前 LLM_MODEL_ID 不可用，或当前 key 没有权限使用它。请检查 backend/.env。", status_code=400)),
        ):
            response = self.client.post(
                "/v1/chat/send",
                json={"role_id": role_id, "user_message": "我真的很讨厌你"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "模型调用失败：当前 LLM_MODEL_ID 不可用，或当前 key 没有权限使用它。请检查 backend/.env。",
        )

    def test_role_heart_rate_history_starts_after_role_creation(self) -> None:
        self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_hr_001",
                "persona_text": "像恋人一样聊天，温柔一点。",
            },
        )
        append_response = self.client.post(
            "/v1/roles/role_hr_001/heart-rate",
            json={"bpm": 88},
        )
        self.assertEqual(append_response.status_code, 200)
        reading = append_response.json()
        self.assertEqual(reading["role_id"], "role_hr_001")
        self.assertEqual(reading["status"], "fresh")

        latest_response = self.client.get("/v1/roles/role_hr_001/heart-rate/latest")
        self.assertEqual(latest_response.status_code, 200)
        self.assertEqual(latest_response.json()["bpm"], 88)

        history_response = self.client.get("/v1/roles/role_hr_001/heart-rate/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role_id"], "role_hr_001")
        self.assertEqual(history[0]["bpm"], 88)

    def test_role_heart_rate_tool_reads_global_latest(self) -> None:
        self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_owner_001",
                "persona_text": "像恋人一样聊天，温柔一点。",
            },
        )
        self.client.post("/v1/heart-rate/latest", json={"bpm": 91})
        chat_response = self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_owner_001",
                "user_message": "我现在是不是有点紧张？",
            },
        )
        self.assertEqual(chat_response.status_code, 200)
        data = chat_response.json()
        self.assertTrue(data["tool_used"])
        self.assertEqual(data["heart_rate"]["bpm"], 91)

    def test_role_lifecycle_and_chat(self) -> None:
        create_response = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_heart_001",
                "title": "默认恋人",
                "persona_text": "像恋人一样聊天，温柔一点，可以接住情绪。",
            },
        )
        self.assertEqual(create_response.status_code, 200)

        hr_response = self.client.post(
            "/v1/heart-rate/latest",
            json={"bpm": 96},
        )
        self.assertEqual(hr_response.status_code, 200)
        self.assertEqual(hr_response.json()["status"], "fresh")

        chat_response = self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_heart_001",
                "user_message": "我刚刚有点紧张，心跳好快。",
                "idle_seconds": 42,
            },
        )
        self.assertEqual(chat_response.status_code, 200)
        data = chat_response.json()
        self.assertTrue(data["tool_used"])
        self.assertEqual(data["heart_rate"]["status"], "fresh")
        self.assertIn("占位回复", data["reply"])

        history_response = self.client.get("/v1/roles/role_heart_001/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(len(history["messages"]), 2)
        self.assertEqual(history["messages"][0]["role"], "user")
        self.assertEqual(history["messages"][1]["role"], "assistant")

    def test_role_does_not_persist_user_llm_config(self) -> None:
        response = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_llm_003",
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
        self.assertIsNone(data["llm_model_id"])
        self.assertIsNone(data["llm_base_url"])
        self.assertFalse(data["has_llm_api_key"])

    def test_sqlite_persists_across_clients(self) -> None:
        self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_persist_004",
                "persona_text": "像恋人一样聊天，安静一点。",
            },
        )
        self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_persist_004",
                "user_message": "你还在吗？",
            },
        )

        second_client = TestClient(app)
        history_response = second_client.get("/v1/roles/role_persist_004/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(history["role"]["role_id"], "role_persist_004")
        self.assertEqual(len(history["messages"]), 2)

    def test_updating_persona_clears_role_memory(self) -> None:
        self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_reset",
                "persona_text": "像恋人一样聊天，温柔一点。",
            },
        )
        self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_reset",
                "user_message": "第一段记忆",
            },
        )

        update_response = self.client.post(
            "/v1/roles",
            json={
                "role_id": "role_reset",
                "persona_text": "你现在是另一张新角色卡，语气更冷静。",
            },
        )
        self.assertEqual(update_response.status_code, 200)

        history_response = self.client.get("/v1/roles/role_reset/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(history["messages"], [])

    def test_new_role_requires_persona(self) -> None:
        response = self.client.post(
            "/v1/chat/send",
            json={
                "role_id": "role_002",
                "user_message": "你好。",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "persona_text or persona_id or role_card is required for a new role")


if __name__ == "__main__":
    unittest.main()
