from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Paddock Brief API"
    app_env: str = "development"
    app_use_sample_data: bool = True
    app_cors_origins: str = "http://localhost:3000"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    openf1_token: str | None = None
    youtube_api_key: str | None = None
    transcript_api_key: str | None = None
    openai_api_key: str | None = None
    team_radio_audio_proxy_url: str | None = None
    openai_summary_model: str = "gpt-6-luna"
    live_timing_enabled: bool = False
    live_timing_url: str = "wss://livetiming.formula1.com/signalrcore"
    f1_live_token: str | None = None
    collector_user_agent: str = "PaddockBrief/1.0 (+personal F1 reader)"
    api_prefix: str = Field(default="/api/v1")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def supabase_key(self) -> str | None:
        return self.supabase_secret_key or self.supabase_publishable_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
