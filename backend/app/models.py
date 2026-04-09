from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class RoleCardInput(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    user_nickname: str | None = Field(default=None, max_length=32)
    relationship_setting: str | None = Field(default=None, max_length=300)
    story_background: str | None = Field(default=None, max_length=600)
    trait_profile: str | None = Field(default=None, max_length=300)
    attachment_style: str | None = Field(default=None, max_length=200)
    processing_style: str | None = Field(default=None, max_length=300)
    key_experiences: str | None = Field(default=None, max_length=500)
    core_motivations: str | None = Field(default=None, max_length=300)
    response_style: str | None = Field(default=None, max_length=320)
    response_tone: str | None = Field(default=None, max_length=200)
    response_pacing: str | None = Field(default=None, max_length=120)
    response_initiative: str | None = Field(default=None, max_length=120)
    response_boundaries: str | None = Field(default=None, max_length=200)
    personality: str | None = Field(default=None, max_length=300)
    speaking_style: str | None = Field(default=None, max_length=200)
    interaction_rules: str | None = Field(default=None, max_length=400)
    taboos: list[str] = Field(default_factory=list, max_length=12)
    keywords: list[str] = Field(default_factory=list, max_length=12)

    @field_validator(
        "name",
        "user_nickname",
        "relationship_setting",
        "story_background",
        "trait_profile",
        "attachment_style",
        "processing_style",
        "key_experiences",
        "core_motivations",
        "response_style",
        "response_tone",
        "response_pacing",
        "response_initiative",
        "response_boundaries",
        "personality",
        "speaking_style",
        "interaction_rules",
    )
    @classmethod
    def strip_role_card_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("taboos", "keywords")
    @classmethod
    def normalize_role_card_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @model_validator(mode="after")
    def resolve_legacy_fields(self) -> "RoleCardInput":
        if self.trait_profile is None and self.personality is not None:
            self.trait_profile = self.personality
        if self.response_style is None and self.speaking_style is not None:
            self.response_style = self.speaking_style
        if self.response_style is None:
            response_parts = [self.response_tone, self.response_pacing, self.response_initiative]
            merged_style = "；".join(part for part in response_parts if part)
            if merged_style:
                self.response_style = merged_style
        if self.response_tone is None and self.response_style is not None:
            self.response_tone = self.response_style
        if self.response_tone is None and self.speaking_style is not None:
            self.response_tone = self.speaking_style
        return self


class PersonaCompileRequest(BaseModel):
    persona_text: str = Field(min_length=1, max_length=400)
    persona_profile: PersonaProfile | None = None


class PersonaTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    persona_text: str = Field(min_length=1, max_length=400)
    persona_profile: PersonaProfile | None = None

    @field_validator("name", "description", "persona_text")
    @classmethod
    def strip_template_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PersonaTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    persona_text: str | None = Field(default=None, max_length=400)
    persona_profile: PersonaProfile | None = None

    @field_validator("name", "description", "persona_text")
    @classmethod
    def strip_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PersonaTemplate(BaseModel):
    persona_id: str
    name: str
    description: str | None = None
    persona_text: str
    persona_profile: PersonaProfile | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class AgentProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    system_preamble: str | None = Field(default=None, max_length=2000)
    tool_call_limit: int = Field(default=1, ge=0, le=4)
    heart_rate_enabled: bool = True
    heart_rate_max_call_per_turn: int = Field(default=1, ge=0, le=4)
    allow_stale_heart_rate: bool = False

    @field_validator("name", "description", "system_preamble")
    @classmethod
    def strip_agent_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    system_preamble: str | None = Field(default=None, max_length=2000)
    tool_call_limit: int | None = Field(default=None, ge=0, le=4)
    heart_rate_enabled: bool | None = None
    heart_rate_max_call_per_turn: int | None = Field(default=None, ge=0, le=4)
    allow_stale_heart_rate: bool | None = None

    @field_validator("name", "description", "system_preamble")
    @classmethod
    def strip_agent_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentProfile(BaseModel):
    agent_id: str
    name: str
    description: str | None = None
    system_preamble: str | None = None
    tool_call_limit: int = 1
    heart_rate_enabled: bool = True
    heart_rate_max_call_per_turn: int = 1
    allow_stale_heart_rate: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_runtime_policy(self) -> RuntimePolicy:
        return RuntimePolicy(
            tool_call_limit=self.tool_call_limit,
            heart_rate=HeartRatePolicy(
                enabled=self.heart_rate_enabled,
                max_call_per_turn=self.heart_rate_max_call_per_turn,
                allow_stale_reading=self.allow_stale_heart_rate,
            ),
        )


class AgentScaffold(BaseModel):
    base_system_prompt: str
    safety_rules: list[str]
    pipeline_steps: list[str]
    tool_registry: list[ToolDefinition]


class TurnRuntime(BaseModel):
    role_id: str
    app_user_id: str
    session_id: str
    profile_id: str
    model_id: str
    agent: AgentProfile
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
    role_id: str | None = Field(default=None, min_length=1, max_length=128)
    app_user_id: str | None = Field(default=None, min_length=1, max_length=128)
    profile_id: str | None = Field(default=None, min_length=1, max_length=128)
    bpm: int = Field(ge=30, le=220)
    timestamp: datetime | None = None

    @field_validator("role_id", "app_user_id", "profile_id")
    @classmethod
    def strip_identity_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def resolve_identity(self) -> "HeartRateUpsertRequest":
        if self.app_user_id is None and self.profile_id is not None:
            self.app_user_id = self.profile_id
        if self.profile_id is None and self.app_user_id is not None:
            self.profile_id = self.app_user_id
        if self.role_id is None and self.app_user_id is None and self.profile_id is None:
            raise ValueError("role_id or app_user_id or profile_id is required")
        return self


class RoleHeartRateAppendRequest(BaseModel):
    bpm: int = Field(ge=30, le=220)
    timestamp: datetime | None = None


class HeartRateReading(BaseModel):
    role_id: str | None = None
    app_user_id: str | None = None
    profile_id: str
    bpm: int | None = None
    timestamp: datetime | None = None
    age_sec: int | None = None
    status: HeartRateStatus

    @model_validator(mode="after")
    def resolve_reading_identity(self) -> "HeartRateReading":
        if self.app_user_id is None:
            self.app_user_id = self.profile_id
        if self.role_id is None:
            self.role_id = None
        return self


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime = Field(default_factory=utc_now)


class SessionCreateRequest(BaseModel):
    role_id: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    app_user_id: str | None = Field(default=None, min_length=1, max_length=128)
    profile_id: str | None = Field(default=None, min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=80)
    persona_id: str | None = Field(default=None, max_length=128)
    persona_text: str | None = Field(default=None, max_length=400)
    role_card: RoleCardInput | None = None
    persona_profile: PersonaProfile | None = None
    agent_id: str | None = Field(default=None, max_length=128)
    llm_config: LLMConfigInput | None = None

    @field_validator("role_id", "session_id", "app_user_id", "profile_id", "persona_id", "title")
    @classmethod
    def strip_session_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("persona_text")
    @classmethod
    def strip_session_persona_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("agent_id")
    @classmethod
    def strip_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def resolve_session_identity(self) -> "SessionCreateRequest":
        if self.__class__.__name__ == "RoleCreateRequest" and self.role_id is None and self.session_id is None:
            return self
        if self.app_user_id is None and self.profile_id is not None:
            self.app_user_id = self.profile_id
        if self.profile_id is None and self.app_user_id is not None:
            self.profile_id = self.app_user_id
        if self.role_id:
            if self.session_id is None:
                self.session_id = self.role_id
        if self.session_id is None:
            raise ValueError("role_id or session_id is required")
        return self


class SessionState(BaseModel):
    role_id: str | None = None
    session_id: str
    app_user_id: str | None = None
    profile_id: str
    title: str | None = None
    persona_id: str | None = None
    persona_text: str
    role_card: RoleCardInput | None = None
    persona_profile: PersonaProfile | None = None
    agent_id: str | None = None
    llm_model_id: str | None = None
    llm_base_url: str | None = None
    has_llm_api_key: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def resolve_state_identity(self) -> "SessionState":
        if self.app_user_id is None:
            self.app_user_id = self.profile_id
        if self.role_id is None:
            self.role_id = self.session_id
        return self


class SessionHistoryResponse(BaseModel):
    session: SessionState
    messages: list[ChatMessage]


class RoleCreateRequest(SessionCreateRequest):
    pass


class RoleState(BaseModel):
    role_id: str
    app_user_id: str | None = None
    title: str | None = None
    persona_id: str | None = None
    persona_text: str
    role_card: RoleCardInput | None = None
    persona_profile: PersonaProfile | None = None
    agent_id: str | None = None
    llm_model_id: str | None = None
    llm_base_url: str | None = None
    has_llm_api_key: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RoleHistoryResponse(BaseModel):
    role: RoleState
    messages: list[ChatMessage]


class ChatSendRequest(BaseModel):
    role_id: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    app_user_id: str | None = Field(default=None, min_length=1, max_length=128)
    profile_id: str | None = Field(default=None, min_length=1, max_length=128)
    persona_id: str | None = Field(default=None, max_length=128)
    persona_text: str | None = Field(default=None, max_length=400)
    role_card: RoleCardInput | None = None
    persona_profile: PersonaProfile | None = None
    agent_id: str | None = Field(default=None, max_length=128)
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

    @field_validator("role_id", "session_id", "app_user_id", "profile_id", "persona_id", "agent_id")
    @classmethod
    def strip_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def resolve_chat_identity(self) -> "ChatSendRequest":
        if self.app_user_id is None and self.profile_id is not None:
            self.app_user_id = self.profile_id
        if self.profile_id is None and self.app_user_id is not None:
            self.profile_id = self.app_user_id
        if self.role_id:
            if self.session_id is None:
                self.session_id = self.role_id
        if self.session_id is None:
            raise ValueError("role_id or session_id is required")
        return self


class ChatSendResponse(BaseModel):
    role_id: str | None = None
    app_user_id: str | None = None
    session_id: str
    model_used: str
    tool_used: bool
    heart_rate: HeartRateReading | None = None
    reply: str

    @model_validator(mode="after")
    def resolve_response_identity(self) -> "ChatSendResponse":
        if self.role_id is None:
            self.role_id = self.session_id
        return self


class LLMReply(BaseModel):
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    raw: dict | None = None
