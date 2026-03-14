"""
Configuration management using Pydantic Settings.
Loads from environment variables / .env file.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class TTSProvider(str, Enum):
    GOOGLE = "google"
    ELEVENLABS = "elevenlabs"


class Settings(BaseSettings):
    """Application-wide settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── LLM Providers ──
    llm_provider: LLMProvider = LLMProvider.GEMINI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # ── Speech-to-Text ──
    deepgram_api_key: str = ""

    # ── Text-to-Speech ──
    tts_provider: TTSProvider = TTSProvider.GOOGLE
    google_tts_api_key: str = ""
    elevenlabs_api_key: str = ""

    # ── Database ──
    database_url: str = "postgresql+asyncpg://voiceai:voiceai_secret@localhost:5432/voiceai_db"
    postgres_user: str = "voiceai"
    postgres_password: str = "voiceai_secret"
    postgres_db: str = "voiceai_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379

    # ── Application ──
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    mock_mode: bool = True

    # ── Latency ──
    target_latency_ms: int = 450

    # ── Session ──
    session_ttl_seconds: int = 1800  # 30 minutes


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
