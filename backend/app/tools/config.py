from __future__ import annotations

from app.config import settings


class ToolSettings:
    @property
    def tool_call_timeout_seconds(self) -> int:
        return settings.tool_call_timeout_seconds

    @property
    def heart_rate_tool_provider(self) -> str:
        return settings.heart_rate_tool_provider


tool_settings = ToolSettings()
