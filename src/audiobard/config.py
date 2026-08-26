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
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Loads configuration from ~/.config/audiobard/config.yaml or config.json if present."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        config_path = Path("~/.config/audiobard/config.yaml").expanduser()
        if not config_path.exists():
            config_path = Path("~/.config/audiobard/config.json").expanduser()
        if not config_path.exists():
            return {}
        try:
            text = config_path.read_text(encoding="utf-8")
            if config_path.suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    data = yaml.safe_load(text)
                    return data if isinstance(data, dict) else {}
                except ImportError:
                    # Lightweight fallback parser for flat key: value yaml lines
                    result: dict[str, Any] = {}
                    for line in text.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and ":" in line:
                            k, v = line.split(":", 1)
                            result[k.strip()] = v.strip().strip("\"'")
                    return result
            else:
                import json

                data = json.loads(text)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def _default_voices_dir() -> Path:
    import os

    env_dir = os.environ.get("AUDIOBARD_VOICES_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)
    cwd_dir = Path.cwd() / "data" / "voices"
    if cwd_dir.is_dir():
        return cwd_dir
    pkg_dir = Path(__file__).resolve().parent.parent.parent / "data" / "voices"
    if pkg_dir.is_dir():
        return pkg_dir
    return Path("~/.local/share/audiobard/voices").expanduser()


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    # ------------------------------------------------------------------ LLM
    llm_provider: Literal["ollama", "gemini", "openrouter", "nim"] = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_base_url: str = "http://localhost:11434"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_semaphore: int = Field(default=4, ge=1, le=64, description="Max concurrent LLM calls")
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    nim_api_key: str = ""
    nim_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # ------------------------------------------------------------------ TTS
    tts_provider: Literal["piper", "edge"] = "piper"
    tts_locale: str = "en_US"
    tts_semaphore: int = Field(default=4, ge=1, le=64, description="Max concurrent TTS calls")

    # ------------------------------------------------------------------ Paths
    db_path: Path = Path("~/.local/share/audiobard/audiobard.db").expanduser()
    cache_dir: Path = Path("~/.cache/audiobard").expanduser()
    voices_dir: Path = Field(default_factory=_default_voices_dir)

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
            "licences. Cloud providers (Gemini, OpenRouter, NIM disallow commercial "
            "use on free tiers."
        ),
    )

    def assert_commercial_safe(self) -> None:
        """Raise RuntimeError if commercial_use=True with a cloud provider."""
        cloud_providers = {"gemini", "openrouter", "nim"}
        if self.commercial_use and self.llm_provider in cloud_providers:
            raise RuntimeError(
                f"AUDIOBARD_COMMERCIAL_USE=true is set, but the selected LLM "
                f"provider ({self.llm_provider!r}) does not allow commercial use "
                "on its free tier. Switch to llm_provider=ollama or disable "
                "commercial_use."
            )
