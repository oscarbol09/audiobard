"""AudioBard configuration.

Settings are loaded from environment variables (prefixed ``AUDIOBARD_``) and,
optionally, from ``~/.config/audiobard/config.yaml``.  Pydantic-Settings handles
the merge; env vars always win.

Example .env::

    AUDIOBARD_LLM_PROVIDER=ollama
    AUDIOBARD_LLM_MODEL=qwen2.5:7b
    AUDIOBARD_TTS_PROVIDER=piper
    AUDIOBARD_COMMERCIAL_USE=false
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioBardConfig(BaseSettings):
    """Central configuration for the AudioBard pipeline.

    All fields can be overridden by environment variables with the
    ``AUDIOBARD_`` prefix (e.g. ``AUDIOBARD_LLM_MODEL=llama3.1:8b``).
    """

    model_config = SettingsConfigDict(
        env_prefix="AUDIOBARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ LLM
    llm_provider: Literal["ollama", "gemini", "openrouter"] = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_base_url: str = "http://localhost:11434"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_semaphore: int = Field(default=4, ge=1, le=64, description="Max concurrent LLM calls")

    # ------------------------------------------------------------------ TTS
    tts_provider: Literal["piper", "edge"] = "piper"
    tts_locale: str = "en_US"
    tts_semaphore: int = Field(default=4, ge=1, le=64, description="Max concurrent TTS calls")

    # ------------------------------------------------------------------ Paths
    db_path: Path = Path("~/.local/share/audiobard/audiobard.db").expanduser()
    cache_dir: Path = Path("~/.cache/audiobard").expanduser()
    voices_dir: Path = Path("data/voices")

    # ------------------------------------------------------------------ Output
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    chunk_words: int = Field(
        default=1500,
        ge=100,
        le=8000,
        description="Words per LLM attribution chunk",
    )

    # ------------------------------------------------------------------ Ethics
    commercial_use: bool = Field(
        default=False,
        description=(
            "Set True only if you self-host open models (Ollama/Piper) and "
            "have confirmed commercial use is permitted under all applicable "
            "licences. Cloud providers (Gemini, OpenRouter) disallow commercial "
            "use on free tiers."
        ),
    )

    def assert_commercial_safe(self) -> None:
        """Raise RuntimeError if commercial_use=True with a cloud provider."""
        cloud_providers = {"gemini", "openrouter"}
        if self.commercial_use and self.llm_provider in cloud_providers:
            raise RuntimeError(
                f"AUDIOBARD_COMMERCIAL_USE=true is set, but the selected LLM "
                f"provider ({self.llm_provider!r}) does not allow commercial use "
                "on its free tier.  Switch to llm_provider=ollama or disable "
                "commercial_use."
            )
