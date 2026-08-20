"""Tests for AudioBookPipeline, chunking, and CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from audiobard.cli import app
from audiobard.config import AudioBardConfig
from audiobard.models import (
    AgeHint,
    AttributionResult,
    Character,
    CharactersResult,
    DialogLine,
    Emotion,
    GenderHint,
    Paragraph,
    Tone,
    Voice,
)
from audiobard.pipeline import (
    AudioBookPipeline,
    chunk_paragraphs,
    create_llm_client,
    create_tts_provider,
)

runner = CliRunner()


def test_chunk_paragraphs() -> None:
    """Test paragraph chunking by word count."""
    paragraphs = [
        Paragraph(text="One two three", chapter=0, index=0),
        Paragraph(text="Four five six", chapter=0, index=1),
        Paragraph(text="Seven eight nine ten", chapter=0, index=2),
    ]

    # Chunk size 6:
    # Chunk 1: [P0, P1] (6 words)
    # Chunk 2: [P2] (4 words)
    chunks = chunk_paragraphs(paragraphs, chunk_size=6)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 1


@pytest.mark.asyncio
async def test_factories() -> None:
    """Test factory client instantiation."""
    config = AudioBardConfig(
        llm_provider="ollama",
        tts_provider="piper",
    )
    llm = create_llm_client(config)
    assert llm.__class__.__name__ == "OllamaClient"

    tts = create_tts_provider(config)
    assert tts.__class__.__name__ == "PiperProvider"


@pytest.mark.asyncio
@patch("audiobard.pipeline.create_llm_client")
@patch("audiobard.pipeline.create_tts_provider")
@patch("audiobard.pipeline.AudioProcessor")
@patch("audiobard.pipeline.AudioSegment")
async def test_pipeline_run(
    mock_audio_seg: MagicMock,
    mock_processor_cls: MagicMock,
    mock_tts_cls: MagicMock,
    mock_llm_cls: MagicMock,
) -> None:
    """Test complete pipeline run with mocked LLM, TTS, and AudioProcessor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test.db"

        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.extract_characters.return_value = CharactersResult(
            characters=[
                Character(
                    canonical_id="Narrator",
                    name="Narrator",
                    gender_hint=GenderHint.NEUTRAL,
                    age_hint=AgeHint.ADULT,
                    tone=Tone.NEUTRAL,
                ),
                Character(
                    canonical_id="Character_A",
                    name="Alice",
                    gender_hint=GenderHint.FEMALE,
                    age_hint=AgeHint.YOUNG,
                    tone=Tone.CALM,
                ),
            ]
        )
        mock_llm.attribute_dialog.return_value = AttributionResult(
            lines=[
                DialogLine(
                    text="Hello!",
                    speaker="Character_A",
                    emotion=Emotion.HAPPY,
                )
            ]
        )
        mock_llm_cls.return_value = mock_llm

        # Mock TTS
        mock_tts = AsyncMock()
        mock_tts.list_voices.return_value = [
            Voice(
                id="voice-a",
                locale="en_US",
                gender=GenderHint.FEMALE,
                age=AgeHint.YOUNG,
                energy=0.5,
            )
        ]
        mock_tts.synthesize.return_value = b"synthesized-audio"
        mock_tts_cls.return_value = mock_tts

        # Mock AudioSegment.from_file so pydub doesn't try to decode fake bytes
        mock_segment = MagicMock()
        mock_segment.__len__ = MagicMock(return_value=500)
        mock_audio_seg.from_file.return_value = mock_segment

        # Mock AudioProcessor
        mock_proc = AsyncMock()
        mock_proc.concatenate.return_value = b"final-audio"
        mock_processor_cls.return_value = mock_proc

        # Create dummy voice pool file
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir(parents=True, exist_ok=True)
        (voices_dir / "en_US.json").write_text(
            '[{"id": "voice-a", "locale": "en_US", "gender": "female"'
            ', "age": "young", "energy": 0.5}]',
            encoding="utf-8",
        )

        config = AudioBardConfig(
            db_path=db_path,
            cache_dir=tmp_path / "cache",
            voices_dir=voices_dir,
        )

        # Create dummy text book
        book_file = tmp_path / "book.txt"
        book_file.write_text(
            "CHAPTER I\n\nThis is narrator text.\n\n\"Hello!\" she said.",
            encoding="utf-8",
        )

        pipeline = AudioBookPipeline(config)

        # Override default llm and tts clients
        pipeline.llm_client = mock_llm
        pipeline.tts_provider = mock_tts

        output_mp3 = tmp_path / "output.mp3"
        await pipeline.run(book_file, output_mp3, resume=False, dry_run=False)

        # Verify output MP3 was generated
        mock_proc.export_mp3.assert_called_once_with(b"final-audio", output_mp3)


def test_cli_validate_config() -> None:
    """Test CLI validate-config command."""
    result = runner.invoke(app, ["validate-config"])
    assert result.exit_code == 0
    assert "Configuration is valid and safe!" in result.stdout


@patch("audiobard.cli.create_tts_provider")
def test_cli_voices(mock_tts_factory: MagicMock) -> None:
    """Test CLI voices command listing."""
    mock_tts = AsyncMock()
    mock_tts.list_voices.return_value = [
        Voice(
            id="voice-dummy",
            locale="en_US",
            gender=GenderHint.MALE,
            age=AgeHint.ADULT,
            energy=0.6,
        )
    ]
    mock_tts_factory.return_value = mock_tts

    result = runner.invoke(app, ["voices", "--provider", "edge"])
    assert result.exit_code == 0
    assert "voice-dummy" in result.stdout
