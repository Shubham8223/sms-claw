"""Central typed configuration — loaded once, cached forever."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = Field(min_length=32)
    log_level: str = "INFO"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/sms-claw"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM ───────────────────────────────────────────────────────────────────
    default_llm_provider: Literal["anthropic", "openai", "google", "nvidia"] = (
        "anthropic"
    )
    default_llm_model: str = "claude-sonnet-4-20250514"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    google_api_key: str = ""

    # NVIDIA (NeMo / NIM)
    nvidia_api_key: str = ""
    nvidia_base_url: str | None = None

    # ── SMS ───────────────────────────────────────────────────────────────────
    default_sms_provider: Literal["twilio", "africas_talking", "vonage"] = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    at_api_key: str = ""
    at_username: str = "sandbox"
    at_sender_id: str = "DISPATCH"
    vonage_api_key: str = ""
    vonage_api_secret: str = ""
    vonage_from: str = "DISPATCH"

    # ── Security ──────────────────────────────────────────────────────────────
    allowed_phone_numbers: list[str] = Field(default_factory=list)
    otp_expiry_seconds: int = 300
    rate_limit_messages_per_hour: int = 20

    @field_validator("allowed_phone_numbers", mode="before")
    @classmethod
    def _parse_phones(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    # ── Tool: Email ───────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # ── Tool: WhatsApp ────────────────────────────────────────────────────────
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""

    # ── Tool: GitHub ──────────────────────────────────────────────────────────
    github_token: str = ""

    # ── Tool: Search ──────────────────────────────────────────────────────────
    search_provider: Literal["tavily", "serpapi"] = "tavily"
    tavily_api_key: str = ""
    serpapi_api_key: str = ""

    # ── Tool: Telegram ────────────────────────────────────────────────────────
    telegram_bot_token: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
