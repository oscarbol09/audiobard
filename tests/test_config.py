"""Unit tests for AudioBardConfig and settings sources."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from audiobard.config import AudioBardConfig, YamlConfigSettingsSource


def test_default_config() -> None:
    """Test default values of AudioBardConfig."""
    config = AudioBardConfig()
    assert config.llm_provider == "ollama"
    assert config.llm_model == "qwen2.5:7b"
    assert config.tts_provider == "piper"
    assert config.tts_locale == "en_US"
    assert config.chunk_words == 1500
    assert config.commercial_use is False


def test_assert_commercial_safe() -> None:
    """Test that commercial safety checks prevent cloud providers on free tier."""
    # Ollama + commercial_use=True is safe
    safe_config = AudioBardConfig(llm_provider="ollama", commercial_use=True)
    safe_config.assert_commercial_safe()  # should not raise

    # Gemini + commercial_use=True violates safety
    unsafe_config = AudioBardConfig(llm_provider="gemini", commercial_use=True)
    with pytest.raises(RuntimeError, match="does not allow commercial use"):
        unsafe_config.assert_commercial_safe()


def test_yaml_config_source_loading() -> None:
    """Test YamlConfigSettingsSource parsing key-value settings from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config_file = Path(tmpdir) / "config.yaml"
        fake_config_file.write_text(
            "llm_provider: gemini\nllm_model: gemini-2.0-flash\n",
            encoding="utf-8",
        )

        source = YamlConfigSettingsSource(AudioBardConfig)
        with patch("pathlib.Path.expanduser", return_value=fake_config_file):
            data = source()
            assert data["llm_provider"] == "gemini"
            assert data["llm_model"] == "gemini-2.0-flash"
