from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HeartRateStatus(str, Enum):
    fresh = "fresh"
    recent = "recent"
    stale = "stale"
    unavailable = "unavailable"


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class PersonaProfile(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    relation_mode: str | None = Field(default=None, max_length=128)
    user_nickname: str | None = Field(default=None, max_length=32)
    tone_hint: str | None = Field(default=None, max_length=128)
    initiative_hint: str | None = Field(default=None, max_length=64)
    affection_style: str | None = Field(default=None, max_length=64)
    expression_level: str | None = Field(default=None, max_length=64)
    comfort_hint: str | None = Field(default=None, max_length=128)
    taboo_list: list[str] = Field(default_factory=list, max_length=8)
    lexicon_list: list[str] = Field(default_factory=list, max_length=8)

    @field_validator(
        "display_name",
        "relation_mode",
        "user_nickname",
        "tone_hint",
        "initiative_hint",
        "affection_style",
        "expression_level",
        "comfort_hint",
    )
    @classmethod
    def strip_profile_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("taboo_list", "lexicon_list")
    @classmethod
    def normalize_list_items(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized


class PersonaCompileRequest(BaseModel):
    persona_text: str = Field(min_length=1, max_length=400)
    persona_profile: PersonaProfile | None = None


class PersonaCompiled(BaseModel):
    source_text: str
    relationship_frame: str
    assistant_name: str | None = None
    user_nickname: str | None = None
    tone: str
    initiative_level: str
    affection_style: str
    expression_level: str
    comfort_style: str
    taboos: list[str]
    lexicon: list[str]
    compiled_prompt: str


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)
    availability: str = "runtime"


class HeartRatePolicy(BaseModel):
    enabled: bool = True
    max_call_per_turn: int = 1
    allow_stale_reading: bool = False


class RuntimePolicy(BaseModel):
    tool_call_limit: int = 1
    heart_rate: HeartRatePolicy = Field(default_factory=HeartRatePolicy)


class AgentScaffold(BaseModel):
    base_system_prompt: str
    safety_rules: list[str]
    pipeline_steps: list[str]
    tool_registry: list[ToolDefinition]


class TurnRuntime(BaseModel):
    session_id: str
    profile_id: str
    model_id: str
    persona: PersonaCompiled
    system_prompt: str
    tools: list[ToolDefinition]
    recent_messages: list["ChatMessage"]
    current_user_message: str
    idle_seconds: int
    policy: RuntimePolicy


class LLMConfigSummary(BaseModel):
    model_id: str | None = None
    base_url: str | None = None
    has_api_key: bool = False
    timeout: int | None = None
    source: str


class PromptMessage(BaseModel):
    role: str
    content: str


class TurnDebugSnapshot(BaseModel):
    scaffold: AgentScaffold
    runtime: TurnRuntime
    llm: LLMConfigSummary
    prompt_messages: list[PromptMessage]
    warnings: list[str] = Field(default_factory=list)
    persists_session: bool


class LLMConfigInput(BaseModel):
    api_key: str | None = Field(default=None, max_length=512)
    base_url: str | None = Field(default=None, max_length=512)
    model_id: str | None = Field(default=None, max_length=256)
    timeout: int | None = Field(default=None, ge=1, le=300)

    @field_validator("api_key", "base_url", "model_id")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LLMConfigResolved(BaseModel):
    api_key: str
    base_url: str
    model_id: str
    timeout: int


class HeartRateUpsertRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    bpm: int = Field(ge=30, le=220)
    timestamp: datetime | None = None


class HeartRateReading(BaseModel):
    profile_id: str
    bpm: int | None = None
    timestamp: datetime | None = None
    age_sec: int | None = None
    status: HeartRateStatus


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime = Field(default_factory=utc_now)


class SessionCreateRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=80)
    persona_text: str = Field(min_length=1, max_length=400)
    persona_profile: PersonaProfile | None = None
    llm_config: LLMConfigInput | None = None


class SessionState(BaseModel):
    session_id: str
    profile_id: str
    title: str | None = None
    persona_text: str
    persona_profile: PersonaProfile | None = None
    llm_model_id: str | None = None
    llm_base_url: str | None = None
    has_llm_api_key: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionHistoryResponse(BaseModel):
    session: SessionState
    messages: list[ChatMessage]


class ChatSendRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    persona_text: str | None = Field(default=None, max_length=400)
    persona_profile: PersonaProfile | None = None
    llm_config: LLMConfigInput | None = None
    user_message: str = Field(min_length=1, max_length=4000)
    idle_seconds: int = Field(default=0, ge=0, le=86400)

    @field_validator("user_message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("user_message cannot be empty")
        return stripped

    @field_validator("persona_text")
    @classmethod
    def strip_persona_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ChatSendResponse(BaseModel):
    session_id: str
    model_used: str
    tool_used: bool
    heart_rate: HeartRateReading | None = None
    reply: str


class LLMReply(BaseModel):
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    raw: dict | None = None
