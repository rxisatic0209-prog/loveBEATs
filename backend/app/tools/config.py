from __future__ import annotations

from app.config import settings


class ToolSettings:
    @property
    def tool_call_timeout_seconds(self) -> int:
        return settings.tool_call_timeout_seconds

    @property
    def heart_rate_tool_provider(self) -> str:
        return settings.heart_rate_tool_provider

    @property
    def pulsoid_api_base(self) -> str:
        return settings.pulsoid_api_base

    @property
    def pulsoid_access_token(self) -> str | None:
        return settings.pulsoid_access_token

    @property
    def pulsoid_timeout_seconds(self) -> float:
        return settings.pulsoid_timeout_seconds


tool_settings = ToolSettings()
