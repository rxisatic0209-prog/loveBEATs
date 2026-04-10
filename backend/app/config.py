from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PulseAgent MVP"
    sqlite_path: str = "pulseagent.db"
    default_app_user_id: str = "local_app_user"
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"
    log_max_bytes: int = 1_048_576
    log_backup_count: int = 3
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model_id: str | None = None
    llm_timeout: int = 60
    tool_call_timeout_seconds: int = 12
    role_message_window: int = Field(
        default=12,
        validation_alias=AliasChoices("ROLE_MESSAGE_WINDOW", "SESSION_MESSAGE_WINDOW"),
    )
    heart_rate_tool_provider: str = "local_cache"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
