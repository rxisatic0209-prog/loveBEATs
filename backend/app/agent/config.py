from __future__ import annotations

from app.config import settings


class AgentSettings:
    @property
    def llm_api_key(self) -> str | None:
        return settings.llm_api_key

    @property
    def llm_base_url(self) -> str | None:
        return settings.llm_base_url

    @property
    def llm_model_id(self) -> str | None:
        return settings.llm_model_id

    @property
    def llm_timeout(self) -> int:
        return settings.llm_timeout

    @property
    def message_window(self) -> int:
        return settings.role_message_window


agent_settings = AgentSettings()
