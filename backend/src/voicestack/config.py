from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production", "test"] = "development"
    role: Literal["all", "app", "telephony"] = "all"
    data_dir: Path = PROJECT_ROOT / "data"
    database_url: str | None = None
    public_base_url: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    static_dir: Path | None = None
    seed_example: bool = True

    # Auth for the builder UI/API itself.
    auth_mode: Literal["none", "token", "proxy"] = "none"
    admin_token: str | None = None
    proxy_user_header: str = "x-goog-authenticated-user-email"

    # Secrets at rest.
    app_encryption_key: str | None = None

    # xAI.
    xai_api_key: str | None = None
    xai_api_base: str = "https://api.x.ai"
    xai_realtime_url: str = "wss://api.x.ai/v1/realtime"
    voice_model: str = "grok-voice-latest"
    text_model: str = "grok-4.3"
    # Prompt optimiser. grok-4.6 cannot turn reasoning off; "low" is its fastest setting.
    optimizer_model: str = "grok-4.6"
    optimizer_reasoning_effort: Literal["low", "medium", "high"] = "low"
    ephemeral_token_ttl_s: int = 300
    # Function tool wire shape for session.update; the docs show both. Phase 0 settles it.
    realtime_function_tool_shape: Literal["flat", "nested"] = "flat"
    # How handoffs treat the voice: switch it with session.update, or keep the first voice.
    handoff_voice_mode: Literal["in_session", "keep"] = "in_session"
    playback_wait_timeout_s: float = 12.0
    # Store every realtime event (minus audio/transcript deltas) per conversation.
    record_events: bool = True

    # Knowledge.
    embeddings_provider: Literal["fastembed", "openai_compatible"] = "fastembed"
    embeddings_model: str = "BAAI/bge-small-en-v1.5"
    embeddings_api_base: str | None = None
    embeddings_api_key: str | None = None

    # Tools.
    plugins_dir: Path | None = None
    ssrf_allowlist: list[str] = Field(default_factory=list)
    tool_timeout_s: float = 15.0
    # Managed MCP tools often wrap model calls themselves (e.g. DeepWiki), so they get longer.
    mcp_tool_timeout_s: float = 60.0

    # Observability.
    log_level: str = "INFO"

    @field_validator(
        "data_dir",
        "static_dir",
        "plugins_dir",
        "database_url",
        "public_base_url",
        "admin_token",
        "app_encryption_key",
        "xai_api_key",
        "embeddings_api_base",
        "embeddings_api_key",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value, info):  # noqa: ANN001
        # `NAME=` in an env file means "not set": an empty path would otherwise resolve to the cwd.
        if isinstance(value, str) and not value.strip():
            return PROJECT_ROOT / "data" if info.field_name == "data_dir" else None
        return value

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://") :]
            if url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://") :]
            return url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.data_dir / 'voicestack.db'}"

    @property
    def is_postgres(self) -> bool:
        return self.resolved_database_url.startswith("postgresql")

    @property
    def psycopg_url(self) -> str:
        """Plain postgres URL for LangGraph's psycopg-based checkpointer and store."""
        return self.resolved_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    @property
    def checkpoint_sqlite_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "langgraph.db"

    @property
    def serves_app(self) -> bool:
        return self.role in ("all", "app")

    @property
    def serves_telephony(self) -> bool:
        return self.role in ("all", "telephony")


@lru_cache
def get_settings() -> Settings:
    return Settings()
