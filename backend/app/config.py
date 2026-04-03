from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PulseAgent MVP"
    sqlite_path: str = "pulseagent.db"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model_id: str | None = None
    llm_timeout: int = 60
    tool_call_timeout_seconds: int = 12
    session_message_window: int = 12

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
