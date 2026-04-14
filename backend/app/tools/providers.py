from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.logging_setup import get_logger
from app.memory.heart_rate_store import get_latest_heart_rate
from app.memory.heart_rate_store import upsert_heart_rate
from app.models import HeartRateReading
from app.models import HeartRateStatus
from app.tools.config import tool_settings

logger = get_logger("LoveBeats.tools.providers")


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
        reading = get_latest_heart_rate()
        return reading.model_copy(update={"role_id": role_id})

    def info(self) -> HeartRateProviderInfo:
        return HeartRateProviderInfo(
            provider=self.name,
            transport=self.transport,
            host_platform="backend",
            ready=True,
            source_of_truth="heart_rate_cache",
            note="默认 provider。从本地缓存读取最近心率。",
        )


class PulsoidHeartRateProvider(HeartRateToolProvider):
    name = "pulsoid"
    transport = "https"
    latest_path = "/api/v1/data/heart_rate/latest"

    def get_latest(self, role_id: str) -> HeartRateReading:
        reading = self._sync_latest()
        if reading is None:
            reading = get_latest_heart_rate()
        return reading.model_copy(update={"role_id": role_id})

    def info(self) -> HeartRateProviderInfo:
        token_ready = bool((tool_settings.pulsoid_access_token or "").strip())
        note = (
            "Pulsoid latest HTTP provider。每次 tool 调用会拉取最新心率并回写本地缓存；失败时回退到本地缓存。"
            if token_ready
            else "Pulsoid provider 未配置 token（PULSOID_ACCESS_TOKEN），调用时会回退到本地缓存。"
        )
        return HeartRateProviderInfo(
            provider=self.name,
            transport=self.transport,
            host_platform="backend",
            ready=token_ready,
            source_of_truth="pulsoid_latest_http_with_local_cache_fallback",
            note=note,
        )

    def _sync_latest(self) -> HeartRateReading | None:
        token = (tool_settings.pulsoid_access_token or "").strip()
        if not token:
            return None

        base = tool_settings.pulsoid_api_base.rstrip("/")
        url = f"{base}{self.latest_path}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            with httpx.Client(timeout=tool_settings.pulsoid_timeout_seconds) as client:
                response = client.get(url, headers=headers)
        except Exception as error:  # noqa: BLE001
            logger.warning("pulsoid latest request failed: %s", error)
            return None

        if response.status_code == 412:
            return HeartRateReading(
                source="pulsoid_http_latest",
                status=HeartRateStatus.unavailable,
            )
        if response.status_code != 200:
            logger.warning("pulsoid latest status=%s body=%s", response.status_code, response.text[:256])
            return None

        try:
            payload = response.json()
        except Exception as error:  # noqa: BLE001
            logger.warning("pulsoid latest json parse failed: %s", error)
            return None

        parsed = self._parse_payload(payload)
        if parsed is None:
            logger.warning("pulsoid payload missing usable heart rate: %s", str(payload)[:256])
            return None
        bpm, measured_at = parsed
        return upsert_heart_rate(bpm=bpm, timestamp=measured_at, source="pulsoid_http_latest")

    def _parse_payload(self, payload: dict[str, Any]) -> tuple[int, datetime | None] | None:
        data = payload.get("data", payload)
        bpm_value = None
        if isinstance(data, dict):
            bpm_value = data.get("heart_rate")
            if bpm_value is None:
                bpm_value = data.get("bpm")
        if bpm_value is None:
            return None
        try:
            bpm = int(bpm_value)
        except (TypeError, ValueError):
            return None
        if bpm < 30 or bpm > 220:
            return None

        measured_at = self._parse_measured_at(payload.get("measured_at"))
        return bpm, measured_at

    def _parse_measured_at(self, value: Any) -> datetime | None:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        if isinstance(value, str):
            try:
                if value.isdigit():
                    return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                return None
        return None


def get_heart_rate_provider() -> HeartRateToolProvider:
    if tool_settings.heart_rate_tool_provider == "local_cache":
        return LocalCacheHeartRateProvider()
    if tool_settings.heart_rate_tool_provider == "pulsoid":
        return PulsoidHeartRateProvider()
    raise ValueError(f"unsupported heart-rate provider: {tool_settings.heart_rate_tool_provider}")


def get_heart_rate_provider_info() -> HeartRateProviderInfo:
    return get_heart_rate_provider().info()
