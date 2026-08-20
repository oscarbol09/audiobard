"""Unit tests for AudioBardConfig and settings sources."""

from __future__ import annotations

import sys
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
    unsafe_config_gemini = AudioBardConfig(llm_provider="gemini", commercial_use=True)
    with pytest.raises(RuntimeError, match="does not allow commercial use"):
        unsafe_config_gemini.assert_commercial_safe()

    # OpenRouter + commercial_use=True violates safety
    unsafe_config_openrouter = AudioBardConfig(llm_provider="openrouter", commercial_use=True)
    with pytest.raises(RuntimeError, match="does not allow commercial use"):
        unsafe_config_openrouter.assert_commercial_safe()


def test_yaml_config_source_loading() -> None:
    """Test YamlConfigSettingsSource parsing key-value settings from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config_file = Path(tmpdir) / "config.yaml"
        fake_config_file.write_text(
            "llm_provider: gemini\nllm_model: gemini-2.0-flash\n",
            encoding="utf-8",
        )

        source = YamlConfigSettingsSource(AudioBardConfig)
        assert source.get_field_value(None, "dummy_field") == (None, "dummy_field", False)

        with patch("pathlib.Path.expanduser", return_value=fake_config_file):
            data = source()
            assert data["llm_provider"] == "gemini"
            assert data["llm_model"] == "gemini-2.0-flash"


def test_yaml_config_source_fallback_without_pyyaml() -> None:
    """Test YamlConfigSettingsSource fallback parsing when PyYAML is not available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_config_file = Path(tmpdir) / "config.yaml"
        fake_config_file.write_text(
            "# Comment line\n\nllm_provider: 'ollama'\nllm_model: \"llama3.1:8b\"\n",
            encoding="utf-8",
        )

        source = YamlConfigSettingsSource(AudioBardConfig)
        with patch.dict(sys.modules, {"yaml": None}), patch(
            "pathlib.Path.expanduser", return_value=fake_config_file
        ):
            data = source()
            assert data["llm_provider"] == "ollama"
            assert data["llm_model"] == "llama3.1:8b"


def test_yaml_config_source_json_file() -> None:
    """Test YamlConfigSettingsSource loading from config.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_json_file = Path(tmpdir) / "config.json"
        fake_json_file.write_text('{"llm_provider": "gemini"}', encoding="utf-8")

        source = YamlConfigSettingsSource(AudioBardConfig)

        def mock_expanduser(self: Path) -> Path:
            if "config.yaml" in str(self):
                return Path(tmpdir) / "nonexistent.yaml"
            return fake_json_file

        with patch("pathlib.Path.expanduser", mock_expanduser):
            data = source()
            assert data["llm_provider"] == "gemini"


def test_yaml_config_source_no_file_found() -> None:
    """Test YamlConfigSettingsSource when no config file exists."""
    source = YamlConfigSettingsSource(AudioBardConfig)
    with patch("pathlib.Path.expanduser", return_value=Path("/nonexistent/file.yaml")):
        assert source() == {}


def test_yaml_config_source_corrupted_file() -> None:
    """Test YamlConfigSettingsSource error handling on corrupted content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_json_file = Path(tmpdir) / "config.json"
        fake_json_file.write_text("{invalid json", encoding="utf-8")

        source = YamlConfigSettingsSource(AudioBardConfig)

        def mock_expanduser(self: Path) -> Path:
            if "config.yaml" in str(self):
                return Path(tmpdir) / "nonexistent.yaml"
            return fake_json_file

        with patch("pathlib.Path.expanduser", mock_expanduser):
            assert source() == {}
