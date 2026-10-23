from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "postgresql://postgres:postgres@localhost:5432/saipport"
    sandbox_database_url: str = "postgresql://postgres:postgres@localhost:5432/saipport_lab"
    app_secret: SecretStr
    sandbox_token: SecretStr
    app_url: str = "http://127.0.0.1:8000"
    sandbox_url: str = "http://127.0.0.1:8001"
    model_provider: Literal["deterministic", "openrouter"] = "deterministic"
    live_mode_enabled: bool = True
    live_unavailable_reason: str = ""
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openrouter/free"
    tool_transport: Literal["direct", "mcp"] = "mcp"
    secure_cookies: bool = False
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )
    session_limit_per_hour: int = 20
    global_sessions_per_hour: int = 100
    global_active_runs: int = 20
    runs_per_tenant: int = 40
    live_calls_per_day: int = 40
    run_timeout_seconds: int = 240
    max_model_calls: int = 8
    max_model_tokens: int = 24000
    max_tool_calls: int = 18
    lease_seconds: int = 30
    session_hours: int = 24


@lru_cache
def settings() -> Settings:
    return Settings()
