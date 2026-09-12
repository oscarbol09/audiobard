"""Unit tests for AudioBardConfig and settings sources."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal
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


@pytest.mark.parametrize(
    ("provider", "commercial_use", "should_raise"),
    [
        ("ollama", True, False),
        ("gemini", True, True),
        ("openrouter", True, True),
        ("gemini", False, False),
        ("openrouter", False, False),
    ],
    ids=[
        "ollama_commercial_allowed",
        "gemini_commercial_blocked",
        "openrouter_commercial_blocked",
        "gemini_non_commercial_allowed",
        "openrouter_non_commercial_allowed",
    ],
)
def test_assert_commercial_safe(
    provider: Literal["ollama", "gemini", "openrouter"],
    commercial_use: bool,
    should_raise: bool,
) -> None:
    """Test that commercial safety checks prevent cloud providers on free tier."""
    config = AudioBardConfig(llm_provider=provider, commercial_use=commercial_use)
    if should_raise:
        with pytest.raises(RuntimeError, match="does not allow commercial use"):
            config.assert_commercial_safe()
    else:
        config.assert_commercial_safe()


def test_yaml_config_source_loading(tmp_path: Path) -> None:
    """Test YamlConfigSettingsSource parsing key-value settings from file."""
    fake_config_file = tmp_path / "config.yaml"
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


def test_yaml_config_source_uses_pyyaml_when_available(tmp_path: Path) -> None:
    """YamlConfigSettingsSource parses with PyYAML when the module is importable."""
    import types

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.__dict__["safe_load"] = (
        lambda text: {"llm_provider": "gemini", "llm_model": "gemini-2.0-flash"}
    )

    fake_config_file = tmp_path / "config.yaml"
    fake_config_file.write_text(
        "llm_provider: gemini\nllm_model: gemini-2.0-flash\n",
        encoding="utf-8",
    )

    source = YamlConfigSettingsSource(AudioBardConfig)
    with patch.dict(sys.modules, {"yaml": fake_yaml}), patch(
        "pathlib.Path.expanduser", return_value=fake_config_file
    ):
        data = source()
        assert data["llm_provider"] == "gemini"
        assert data["llm_model"] == "gemini-2.0-flash"


def test_yaml_config_source_ignores_non_dict_yaml(tmp_path: Path) -> None:
    """YamlConfigSettingsSource falls back to {} when PyYAML returns a non-dict."""
    import types

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.__dict__["safe_load"] = lambda text: ["not", "a", "dict"]

    fake_config_file = tmp_path / "config.yaml"
    fake_config_file.write_text("llm_provider: gemini\n", encoding="utf-8")

    source = YamlConfigSettingsSource(AudioBardConfig)
    with patch.dict(sys.modules, {"yaml": fake_yaml}), patch(
        "pathlib.Path.expanduser", return_value=fake_config_file
    ):
        assert source() == {}


def test_yaml_config_source_fallback_without_pyyaml(tmp_path: Path) -> None:
    """Test YamlConfigSettingsSource fallback parsing when PyYAML is not available."""
    fake_config_file = tmp_path / "config.yaml"
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


def test_yaml_config_source_json_file(tmp_path: Path) -> None:
    """Test YamlConfigSettingsSource loading from config.json."""
    fake_json_file = tmp_path / "config.json"
    fake_json_file.write_text('{"llm_provider": "gemini"}', encoding="utf-8")

    source = YamlConfigSettingsSource(AudioBardConfig)

    def mock_expanduser(self: Path) -> Path:
        if "config.yaml" in str(self):
            return tmp_path / "nonexistent.yaml"
        return fake_json_file

    with patch("pathlib.Path.expanduser", mock_expanduser):
        data = source()
        assert data["llm_provider"] == "gemini"


def test_yaml_config_source_no_file_found() -> None:
    """Test YamlConfigSettingsSource when no config file exists."""
    source = YamlConfigSettingsSource(AudioBardConfig)
    with patch("pathlib.Path.expanduser", return_value=Path("/nonexistent/file.yaml")):
        assert source() == {}


def test_yaml_config_source_corrupted_file(tmp_path: Path) -> None:
    """Test YamlConfigSettingsSource error handling on corrupted content."""
    fake_json_file = tmp_path / "config.json"
    fake_json_file.write_text("{invalid json", encoding="utf-8")

    source = YamlConfigSettingsSource(AudioBardConfig)

    def mock_expanduser(self: Path) -> Path:
        if "config.yaml" in str(self):
            return tmp_path / "nonexistent.yaml"
        return fake_json_file

    with patch("pathlib.Path.expanduser", mock_expanduser):
        assert source() == {}

