"""Comprehensive tests for the CLI entry points and subcommands."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from audiobard import __version__
from audiobard.cli import app
from audiobard.models import AgeHint, GenderHint, Voice
from audiobard.persistence import PersistenceManager

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"audiobard {__version__}" in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


def test_unknown_command_fails() -> None:
    result = runner.invoke(app, ["definitely-not-a-command"])
    assert result.exit_code != 0


def test_validate_config_success() -> None:
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 0
    assert "Configuration is valid and safe!" in result.stdout


def test_validate_config_commercial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBARD_COMMERCIAL_USE", "true")
    monkeypatch.setenv("AUDIOBARD_LLM_PROVIDER", "gemini")
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 1
    assert "Commercial use assertion failed" in result.stdout


def test_validate_config_load_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBARD_CHUNK_WORDS", "not_a_valid_number")
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 1
    assert "Configuration validation failed" in result.stdout


def test_voices_listing() -> None:
    mock_voices = [
        Voice(id="en_US-amy-medium", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)
    ]
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = mock_voices
        mock_create.return_value = mock_tts

        result = runner.invoke(app, ["voices", "--provider", "piper", "--locale", "en_US"])
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.stdout


def test_voices_unknown_provider() -> None:
    result = runner.invoke(app, ["voices", "--provider", "unknown-provider"])
    assert result.exit_code == 1
    assert "Error loading configuration" in result.stdout


def test_voices_retrieval_failure() -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.side_effect = RuntimeError("Voice engine connection failed")
        mock_create.return_value = mock_tts

        result = runner.invoke(app, ["voices", "--provider", "piper"])
        assert result.exit_code == 1
        assert "Failed to retrieve voices" in result.stdout


def test_voices_empty_list() -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = []
        mock_create.return_value = mock_tts

        result = runner.invoke(app, ["voices", "--provider", "piper", "--locale", "fr_FR"])
        assert result.exit_code == 0
        assert "No voices found for locale: fr_FR" in result.stdout


def test_stats_command_no_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(tmp_path / "nonexistent.db"))
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "No database found yet" in result.stdout


def test_stats_command_with_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "test.db"
    pm = PersistenceManager(db_file)
    pm.save_llm_cache("dummy_hash", "{}", "ollama")
    pm.get_llm_cache("dummy_hash")  # increment hit

    cache_dir = tmp_path / "cache"
    tts_dir = cache_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    (tts_dir / "clip.mp3").write_bytes(b"dummy-audio-bytes")

    pipe_dir = cache_dir / "pipeline"
    pipe_dir.mkdir(parents=True, exist_ok=True)
    (pipe_dir / "clip_0_0.mp3").write_bytes(b"dummy-audio-bytes")

    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(db_file))
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(cache_dir))

    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "AudioBard Statistics" in result.stdout
    assert "LLM cache hits" in result.stdout


def test_stats_command_invalid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBARD_CHUNK_WORDS", "not_a_valid_number")
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 1
    assert "Error loading configuration" in result.stdout


def test_generate_missing_file() -> None:
    result = runner.invoke(app, ["generate", "nonexistent_book.epub"])
    assert result.exit_code in (1, 2)


def test_generate_dry_run_and_options(tmp_path: Path) -> None:
    book_file = tmp_path / "sample.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(
            app,
            [
                "generate",
                str(book_file),
                "--llm",
                "ollama",
                "--model",
                "qwen2.5:7b",
                "--tts",
                "piper",
                "--locale",
                "en_US",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert mock_run.called


def test_generate_invalid_config(tmp_path: Path) -> None:
    book_file = tmp_path / "sample.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")
    result = runner.invoke(app, ["generate", str(book_file), "--llm", "invalid_provider"])
    assert result.exit_code == 1
    assert "Error loading configuration" in result.stdout


def test_generate_commercial_violation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBARD_COMMERCIAL_USE", "true")
    book_file = tmp_path / "sample.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")
    result = runner.invoke(app, ["generate", str(book_file), "--llm", "gemini"])
    assert result.exit_code == 1
    assert "Ethics Guardrail Violation" in result.stdout


def test_generate_pipeline_failure(tmp_path: Path) -> None:
    book_file = tmp_path / "sample.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")
    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("Pipeline fatal error")
        result = runner.invoke(app, ["generate", str(book_file)])
        assert result.exit_code == 1
        assert "Pipeline execution failed" in result.stdout


def test_benchmark_subcommand() -> None:
    from unittest.mock import MagicMock
    mock_mod = MagicMock()
    mock_mod.main.return_value = 0
    mock_spec = MagicMock()

    with (
        patch("importlib.util.spec_from_file_location", return_value=mock_spec),
        patch("importlib.util.module_from_spec", return_value=mock_mod),
    ):
        result = runner.invoke(
            app,
            ["benchmark", "--llm", "ollama", "--model", "qwen2.5:7b", "--json"],
        )
        assert result.exit_code == 0


def test_benchmark_script_missing() -> None:
    with patch("pathlib.Path.exists", return_value=False):
        result = runner.invoke(app, ["benchmark"])
        assert result.exit_code == 1
        assert "Benchmark script not found" in result.stdout


def test_benchmark_spec_loader_failure() -> None:
    with patch("importlib.util.spec_from_file_location", return_value=None):
        result = runner.invoke(app, ["benchmark"])
        assert result.exit_code == 1
        assert "Failed to load benchmark module" in result.stdout


def test_benchmark_nonzero_return() -> None:
    from unittest.mock import MagicMock
    mock_mod = MagicMock()
    mock_mod.main.return_value = 3
    mock_spec = MagicMock()

    with (
        patch("importlib.util.spec_from_file_location", return_value=mock_spec),
        patch("importlib.util.module_from_spec", return_value=mock_mod),
    ):
        result = runner.invoke(app, ["benchmark"])
        assert result.exit_code == 3



def test_cli_main_invoked() -> None:
    from audiobard import cli

    cli_path = Path(cli.__file__)
    cli_code = cli_path.read_text(encoding="utf-8")
    compiled = compile(cli_code, str(cli_path), "exec")
    with patch.object(sys, "argv", ["audiobard", "--version"]):
        globs = {"__name__": "__main__", "__file__": str(cli_path)}
        with pytest.raises(SystemExit) as exc:
            exec(compiled, globs)
        assert exc.value.code == 0





