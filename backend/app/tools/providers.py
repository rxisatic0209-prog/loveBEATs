from __future__ import annotations

from dataclasses import dataclass

from app.memory.heart_rate_store import get_latest_heart_rate
from app.memory.session_store import get_app_user_id_for_session
from app.models import HeartRateReading
from app.tools.config import tool_settings


@dataclass(frozen=True)
class HeartRateProviderInfo:
    provider: str
    transport: str
    host_platform: str
    ready: bool
    source_of_truth: str
    note: str


class HeartRateToolProvider:
    name = "base"
    transport = "internal"

    def get_latest(self, role_id: str) -> HeartRateReading:
        raise NotImplementedError

    def info(self) -> HeartRateProviderInfo:
        raise NotImplementedError


class LocalCacheHeartRateProvider(HeartRateToolProvider):
    name = "local_cache"
    transport = "internal"

    def get_latest(self, role_id: str) -> HeartRateReading:
        app_user_id = get_app_user_id_for_session(role_id)
        reading = get_latest_heart_rate(app_user_id)
        return reading.model_copy(update={"role_id": role_id, "app_user_id": app_user_id, "profile_id": app_user_id})

    def info(self) -> HeartRateProviderInfo:
        return HeartRateProviderInfo(
            provider=self.name,
            transport=self.transport,
            host_platform="backend",
            ready=True,
            source_of_truth="heart_rate_cache",
            note="默认 provider。iOS HealthKit 同步器先把心率写进后端缓存，agent 再从这里读取。",
        )

def get_heart_rate_provider() -> HeartRateToolProvider:
    if tool_settings.heart_rate_tool_provider != "local_cache":
        raise ValueError(f"unsupported heart-rate provider: {tool_settings.heart_rate_tool_provider}")
    return LocalCacheHeartRateProvider()


def get_heart_rate_provider_info() -> HeartRateProviderInfo:
    return get_heart_rate_provider().info()
