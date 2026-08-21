"""Tests for AudioBookPipeline, chunking, and CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

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

        # The voice pool cannot change within a run, so the provider is
        # asked for it exactly once (issue #10)
        assert mock_tts.list_voices.await_count == 1

        # Test M4B format output branch
        output_m4b = tmp_path / "output.m4b"
        await pipeline.run(book_file, output_m4b, resume=True, dry_run=False)
        mock_proc.export_m4b.assert_called_once()

        # Test dry-run branch
        output_dry = tmp_path / "output_dry.mp3"
        await pipeline.run(book_file, output_dry, resume=True, dry_run=True)


def test_factories_valid_and_invalid() -> None:
    """Test factory functions for LLM and TTS providers."""
    from audiobard.pipeline import create_llm_client, create_tts_provider

    # Valid providers
    cfg_gemini = AudioBardConfig(llm_provider="gemini", llm_model="gemini-2.0-flash")
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake"}):
        assert create_llm_client(cfg_gemini) is not None

    cfg_openrouter = AudioBardConfig(llm_provider="openrouter")
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake"}):
        assert create_llm_client(cfg_openrouter) is not None

    cfg_edge = AudioBardConfig(tts_provider="edge")
    assert create_tts_provider(cfg_edge) is not None

    # Invalid providers
    cfg_invalid = AudioBardConfig()
    cfg_invalid.__dict__["llm_provider"] = "invalid_llm"
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(cfg_invalid)

    cfg_invalid.__dict__["tts_provider"] = "invalid_tts"
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        create_tts_provider(cfg_invalid)


@pytest.mark.asyncio
async def test_pipeline_missing_book_file(tmp_path: Path) -> None:
    config = AudioBardConfig(db_path=tmp_path / "test.db", cache_dir=tmp_path / "cache")
    pipeline = AudioBookPipeline(config)
    with pytest.raises(FileNotFoundError, match="Book file not found"):
        await pipeline.run(tmp_path / "nonexistent.txt", tmp_path / "out.mp3")


@pytest.mark.asyncio
async def test_pipeline_no_voices_found(tmp_path: Path) -> None:
    book_file = tmp_path / "book.txt"
    book_file.write_text("Chapter 1\n\nHello world.", encoding="utf-8")
    config = AudioBardConfig(db_path=tmp_path / "test.db", cache_dir=tmp_path / "cache")
    pipeline = AudioBookPipeline(config)

    mock_llm = AsyncMock()
    mock_llm.extract_characters.return_value = CharactersResult(characters=[])
    mock_tts = AsyncMock()
    mock_tts.list_voices.return_value = []
    pipeline.llm_client = mock_llm
    pipeline.tts_provider = mock_tts

    with pytest.raises(RuntimeError, match="No voices found for locale"):
        await pipeline.run(book_file, tmp_path / "out.mp3")


@pytest.mark.asyncio
@patch("audiobard.pipeline.AudioProcessor")
@patch("audiobard.pipeline.AudioSegment")
async def test_pipeline_multi_chapter_and_speaker_fallback(
    mock_audio_seg: MagicMock,
    mock_processor_cls: MagicMock,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    cache_dir = tmp_path / "cache"
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / "en_US.json").write_text(
        '[{"id": "v1", "locale": "en_US", "gender": "neutral", "age": "adult", "energy": 0.5}]',
        encoding="utf-8",
    )

    mock_llm = AsyncMock()
    # Return Narrator character
    mock_llm.extract_characters.return_value = CharactersResult(
        characters=[
            Character(
                canonical_id="Narrator",
                name="Narrator",
                gender_hint=GenderHint.NEUTRAL,
                age_hint=AgeHint.ADULT,
                tone=Tone.NEUTRAL,
            )
        ]
    )
    # Attribution returns an unknown character ID to test speaker fallback to Narrator
    mock_llm.attribute_dialog.return_value = AttributionResult(
        lines=[DialogLine(text="Hello", speaker="Character_Z", emotion=Emotion.NEUTRAL)]
    )

    mock_tts = AsyncMock()
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.NEUTRAL, age=AgeHint.ADULT)
    mock_tts.list_voices.return_value = [voice]
    mock_tts.synthesize.return_value = b"mp3"

    mock_proc = AsyncMock()
    mock_proc.concatenate.return_value = b"final"
    mock_processor_cls.return_value = mock_proc

    mock_segment = MagicMock()
    mock_segment.__len__ = MagicMock(return_value=200)
    mock_audio_seg.from_file.return_value = mock_segment

    # Create book with > 5000 words and multiple chapters
    long_para = "word " * 3000
    book_file = tmp_path / "book.txt"
    book_file.write_text(
        f"CHAPTER I\n\n{long_para}\n\n{long_para}\n\nCHAPTER II\n\n\"Hello\" said Z.",
        encoding="utf-8",
    )

    config = AudioBardConfig(db_path=db_path, cache_dir=cache_dir, voices_dir=voices_dir)
    pipeline = AudioBookPipeline(config)
    pipeline.llm_client = mock_llm
    pipeline.tts_provider = mock_tts

    out_file = tmp_path / "out.mp3"
    await pipeline.run(book_file, out_file, resume=False, dry_run=False)

    # Test cache reuse branch in synthesis
    await pipeline.run(book_file, out_file, resume=False, dry_run=False)


@pytest.mark.asyncio
async def test_pipeline_missing_clip_file_during_assembly(tmp_path: Path) -> None:
    from audiobard.parser.base import ParserStats

    book_file = tmp_path / "book.txt"
    book_file.write_text("Hello world.", encoding="utf-8")
    config = AudioBardConfig(db_path=tmp_path / "test.db", cache_dir=tmp_path / "cache")
    pipeline = AudioBookPipeline(config)

    mock_llm = AsyncMock()
    mock_tts = AsyncMock()
    pipeline.llm_client = mock_llm
    pipeline.tts_provider = mock_tts

    # Pre-populate DB with completed checkpoints so synthesis is skipped but cache files are missing
    book_id = pipeline.persistence.get_or_create_book(
        book_file, "book", ParserStats(total_paragraphs=1, total_words=2, dialog_ratio=0.0)
    )
    pipeline.persistence.save_checkpoint(book_id, "characters", "completed", {})
    pipeline.persistence.save_checkpoint(book_id, "voice_assignment", "completed", {})
    pipeline.persistence.save_checkpoint(book_id, "chunk_0", "completed", {})

    with pytest.raises(FileNotFoundError, match="Missing audio clip or metadata"):
        await pipeline.run(book_file, tmp_path / "out.mp3", resume=True, dry_run=False)



