"""Comprehensive tests for the CLI entry points and subcommands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from audiobard import __version__
from audiobard.cli import DEFAULT_VOICE_TEST_TEXT, app
from audiobard.models import (
    AgeHint,
    Emotion,
    GenderHint,
    Voice,
    VoiceAssignment,
    VoicePreset,
)
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


def _mock_tts_provider(
    mock_create: MagicMock, voices: list[Voice], audio: bytes = b"mp3-bytes"
) -> AsyncMock:
    """Install a mocked TTS provider on the CLI factory and return it."""
    mock_tts = AsyncMock()
    mock_tts.list_voices.return_value = voices
    mock_tts.synthesize.return_value = audio
    mock_create.return_value = mock_tts
    return mock_tts


def test_voices_test_writes_default_sample(tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp3"
    known = [
        Voice(
            id="en_US-amy-medium",
            locale="en_US",
            gender=GenderHint.FEMALE,
            age=AgeHint.ADULT,
        )
    ]
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = _mock_tts_provider(mock_create, known)
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "en_US-amy-medium",
                "--locale",
                "en_US",
                "--output",
                str(sample),
                "--no-play",
            ],
        )

    assert result.exit_code == 0
    assert sample.read_bytes() == b"mp3-bytes"
    assert "Sample written to" in result.stdout
    kwargs = mock_tts.synthesize.await_args.kwargs
    assert kwargs["text"] == DEFAULT_VOICE_TEST_TEXT
    assert kwargs["emotion"] is Emotion.NEUTRAL
    assert kwargs["voice"].id == "en_US-amy-medium"


def test_voices_test_plays_sample_and_inherits_group_provider(tmp_path: Path) -> None:
    sample = tmp_path / "edge.mp3"
    with (
        patch("audiobard.cli.create_tts_provider") as mock_create,
        patch("audiobard.cli._play_audio", return_value=True) as mock_play,
    ):
        _mock_tts_provider(mock_create, [])
        result = runner.invoke(
            app,
            [
                "voices",
                "--provider",
                "edge",
                "test",
                "--voice",
                "en-US-EmmaNeural",
                "--locale",
                "en_US",
                "--output",
                str(sample),
            ],
        )

    assert result.exit_code == 0
    mock_play.assert_called_once_with(sample)
    config = mock_create.call_args[0][0]
    assert config.tts_provider == "edge"


def test_voices_test_reports_missing_player(tmp_path: Path) -> None:
    with (
        patch("audiobard.cli.create_tts_provider") as mock_create,
        patch("audiobard.cli._play_audio", return_value=False),
    ):
        _mock_tts_provider(mock_create, [])
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "v1",
                "--locale",
                "en_US",
                "--output",
                str(tmp_path / "sample.mp3"),
            ],
        )

    assert result.exit_code == 0
    assert "No system audio player available" in result.stdout


def test_voices_test_accepts_emotion_synonym(tmp_path: Path) -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = _mock_tts_provider(mock_create, [])
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "v1",
                "--locale",
                "en_US",
                "--text",
                "Welcome back to the library",
                "--emotion",
                "cheerful",
                "--output",
                str(tmp_path / "sample.mp3"),
                "--no-play",
            ],
        )

    assert result.exit_code == 0
    kwargs = mock_tts.synthesize.await_args.kwargs
    assert kwargs["emotion"] is Emotion.HAPPY
    assert kwargs["text"] == "Welcome back to the library"
    assert "happy emotion" in result.stdout


def test_voices_test_unknown_voice_uses_placeholder(tmp_path: Path) -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = _mock_tts_provider(mock_create, [])
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "ghost-voice",
                "--locale",
                "es_ES",
                "--output",
                str(tmp_path / "sample.mp3"),
                "--no-play",
            ],
        )

    assert result.exit_code == 0
    target = mock_tts.synthesize.await_args.kwargs["voice"]
    assert target.id == "ghost-voice"
    assert target.locale == "es_ES"


def test_voices_test_known_voice_keeps_catalog_metadata(tmp_path: Path) -> None:
    known = [
        Voice(
            id="en_US-amy-medium",
            locale="en_US",
            gender=GenderHint.FEMALE,
            age=AgeHint.CHILD,
            energy=0.9,
        )
    ]
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = _mock_tts_provider(mock_create, known)
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "en_US-amy-medium",
                "--locale",
                "en_US",
                "--output",
                str(tmp_path / "sample.mp3"),
                "--no-play",
            ],
        )

    assert result.exit_code == 0
    target = mock_tts.synthesize.await_args.kwargs["voice"]
    assert target.age is AgeHint.CHILD
    assert target.energy == 0.9


def test_voices_test_synthesis_failure(tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp3"
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = []
        mock_tts.synthesize.side_effect = RuntimeError("engine down")
        mock_create.return_value = mock_tts
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "v1",
                "--locale",
                "en_US",
                "--output",
                str(sample),
                "--no-play",
            ],
        )

    assert result.exit_code == 1
    assert "Voice audition failed" in result.stdout
    assert not sample.exists()


def test_voices_test_empty_audio_is_an_error(tmp_path: Path) -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        _mock_tts_provider(mock_create, [], audio=b"")
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "v1",
                "--locale",
                "en_US",
                "--output",
                str(tmp_path / "sample.mp3"),
                "--no-play",
            ],
        )

    assert result.exit_code == 1
    assert "returned no audio" in result.stdout


def test_voices_test_invalid_provider() -> None:
    result = runner.invoke(app, ["voices", "test", "--voice", "v1", "--provider", "bogus"])
    assert result.exit_code == 1
    assert "Error loading configuration" in result.stdout


def _write_voice_pool(directory: Path, locale: str, count: int) -> None:
    entries = json.dumps([{"id": f"{locale}-{index}"} for index in range(count)])
    (directory / f"{locale}.json").write_text(entries, encoding="utf-8")


def test_locales_command_lists_piper_pools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    _write_voice_pool(voices_dir, "en_US", 2)
    _write_voice_pool(voices_dir, "es_ES", 1)
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(voices_dir))

    result = runner.invoke(app, ["locales", "--provider", "piper"])

    assert result.exit_code == 0
    assert "Available locales for provider piper:" in result.stdout
    assert "en_US" in result.stdout
    assert "es_ES" in result.stdout


def test_locales_command_edge_uses_bundled_snapshot() -> None:
    result = runner.invoke(app, ["locales", "--provider", "edge"])
    assert result.exit_code == 0
    assert "Available locales for provider edge:" in result.stdout
    assert "en_US" in result.stdout


def test_locales_command_without_any_pools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(empty))

    result = runner.invoke(app, ["locales", "--provider", "piper"])

    assert result.exit_code == 0
    assert "No locales with locally available voices found" in result.stdout
    assert "Add a voice pool file under" in result.stdout


def test_locales_command_invalid_provider() -> None:
    result = runner.invoke(app, ["locales", "--provider", "bogus"])
    assert result.exit_code == 1
    assert "Error loading configuration" in result.stdout


def test_generate_rejects_locale_without_voices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown --locale must fail fast with the available alternatives."""
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    _write_voice_pool(voices_dir, "en_US", 1)
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(voices_dir))

    book_file = tmp_path / "book.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(app, ["generate", str(book_file), "--locale", "zz_ZZ"])

    assert result.exit_code == 1
    assert "has no voices available for the piper provider" in result.stdout
    assert "Available locales: en_US" in result.stdout
    mock_run.assert_not_called()


def test_generate_skips_validation_when_locales_are_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty locale mapping means unknown, so the pipeline must still run."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(empty))

    book_file = tmp_path / "book.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(app, ["generate", str(book_file), "--locale", "zz_ZZ"])

    assert result.exit_code == 0
    assert mock_run.called


def test_voices_empty_list_suggests_available_locales() -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = []
        mock_tts.available_locales.return_value = {"en_US": 2, "es_ES": 1}
        mock_create.return_value = mock_tts

        result = runner.invoke(
            app, ["voices", "--provider", "piper", "--locale", "fr_FR"]
        )

    assert result.exit_code == 0
    assert "No voices found for locale: fr_FR" in result.stdout
    assert "Available locales: en_US, es_ES" in result.stdout


def test_voices_empty_list_without_locale_data_prints_no_hint() -> None:
    with patch("audiobard.cli.create_tts_provider") as mock_create:
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = []
        mock_tts.available_locales.return_value = {}
        mock_create.return_value = mock_tts

        result = runner.invoke(
            app, ["voices", "--provider", "piper", "--locale", "fr_FR"]
        )

    assert result.exit_code == 0
    assert "Available locales" not in result.stdout


def _seed_book_with_mapping(
    db_file: Path, book: Path, assignments: list[VoiceAssignment]
) -> int:
    from audiobard.parser.base import ParserStats

    persistence = PersistenceManager(db_file)
    book_id = persistence.get_or_create_book(
        book,
        "Book",
        ParserStats(
            total_paragraphs=1,
            total_words=2,
            dialog_ratio=0.0,
            chapter_word_counts={0: 2},
        ),
    )
    if assignments:
        persistence.save_voice_mapping(book_id, assignments)
    return book_id


def test_preset_export_writes_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(tmp_path / "test.db"))
    book = tmp_path / "book.txt"
    book.write_text("Chapter 1\n\nHello world.", encoding="utf-8")
    _seed_book_with_mapping(
        tmp_path / "test.db",
        book,
        [
            VoiceAssignment(canonical_id="Narrator", voice_id="en_US-amy-medium"),
            VoiceAssignment(canonical_id="Character_A", voice_id="en_US-ryan-high"),
        ],
    )
    output = tmp_path / "preset.json"

    result = runner.invoke(
        app,
        ["preset", "export", str(book), "--output", str(output), "--name", "series"],
    )

    assert result.exit_code == 0
    assert "Exported 2 voice assignment(s)" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["name"] == "series"
    assert payload["version"] == 1
    assert sorted(a["canonical_id"] for a in payload["assignments"]) == [
        "Character_A",
        "Narrator",
    ]


def test_preset_export_unknown_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(tmp_path / "empty.db"))
    book = tmp_path / "book.txt"
    book.write_text("Hello world.", encoding="utf-8")

    result = runner.invoke(app, ["preset", "export", str(book)])

    assert result.exit_code == 1
    assert "No stored record for" in result.stdout


def test_preset_export_without_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(db_file))
    book = tmp_path / "book.txt"
    book.write_text("Hello world.", encoding="utf-8")
    _seed_book_with_mapping(db_file, book, [])

    result = runner.invoke(app, ["preset", "export", str(book)])

    assert result.exit_code == 1
    assert "has no saved voice mapping to export" in result.stdout


def test_generate_applies_voice_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    _write_voice_pool(voices_dir, "en_US", 1)
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(voices_dir))

    preset_file = tmp_path / "preset.json"
    preset_file.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "series",
                "assignments": [
                    {"canonical_id": "Narrator", "voice_id": "en_US-amy-medium"}
                ],
            }
        ),
        encoding="utf-8",
    )
    book = tmp_path / "book.txt"
    book.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(
            app,
            [
                "generate",
                str(book),
                "--locale",
                "en_US",
                "--voice-preset",
                str(preset_file),
            ],
        )

    assert result.exit_code == 0
    assert "Using voice preset" in result.stdout
    passed = mock_run.await_args.kwargs["voice_preset"]
    assert isinstance(passed, VoicePreset)
    assert passed.assignments[0].voice_id == "en_US-amy-medium"


def test_generate_rejects_invalid_voice_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    _write_voice_pool(voices_dir, "en_US", 1)
    monkeypatch.setenv("AUDIOBARD_VOICES_DIR", str(voices_dir))

    broken = tmp_path / "broken.json"
    broken.write_text("{not a preset", encoding="utf-8")
    book = tmp_path / "book.txt"
    book.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    with patch("audiobard.cli.AudioBookPipeline.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(
            app,
            ["generate", str(book), "--voice-preset", str(broken)],
        )

    assert result.exit_code == 1
    assert "Could not read voice preset" in result.stdout
    mock_run.assert_not_called()


def test_voices_test_requires_voice_option() -> None:
    result = runner.invoke(app, ["voices", "test"])
    assert result.exit_code == 2


def test_voices_test_unwritable_output(tmp_path: Path) -> None:
    with (
        patch("audiobard.cli.create_tts_provider") as mock_create,
        patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")),
    ):
        _mock_tts_provider(mock_create, [])
        result = runner.invoke(
            app,
            [
                "voices",
                "test",
                "--voice",
                "v1",
                "--locale",
                "en_US",
                "--output",
                str(tmp_path / "sample.mp3"),
                "--no-play",
            ],
        )

    assert result.exit_code == 1
    assert "Could not write the sample" in result.stdout





