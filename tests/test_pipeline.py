"""Tests for AudioBookPipeline, chunking, and CLI commands."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from audiobard.config import AudioBardConfig
from audiobard.models import (
    AgeHint,
    AttributionResult,
    BookMetadata,
    Character,
    CharactersResult,
    DialogLine,
    Emotion,
    GenderHint,
    Paragraph,
    Tone,
    Voice,
    VoiceAssignment,
    VoicePreset,
)
from audiobard.pipeline import (
    AudioBookPipeline,
    chunk_paragraphs,
    create_llm_client,
    create_tts_provider,
    load_voice_preset,
    save_voice_preset,
)
from audiobard.progress import PipelineProgress
from audiobard.tts.base import TTSProvider

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
            'CHAPTER I\n\nThis is narrator text.\n\n"Hello!" she said.',
            encoding="utf-8",
        )

        pipeline = AudioBookPipeline(config)

        # Override default llm and tts clients
        pipeline.llm_client = mock_llm
        pipeline.tts_provider = mock_tts

        output_mp3 = tmp_path / "output.mp3"
        await pipeline.run(book_file, output_mp3, resume=False, dry_run=False)

        # Verify the assembly streamed into the output file and tagged it
        concat_args = mock_proc.concatenate_to_file.call_args.args
        assert concat_args[1] == output_mp3
        assert concat_args[0], "expected the assembled clips"
        tag_args = mock_proc.apply_mp3_tags.call_args.args
        assert tag_args[0] == output_mp3
        assert isinstance(tag_args[1], BookMetadata)
        assert tag_args[1].title is None

        # The voice pool cannot change within a run, so the provider is
        # asked for it exactly once (issue #10)
        assert mock_tts.list_voices.await_count == 1

        # Test M4B format output branch: the staged MP3 is handed to FFmpeg
        output_m4b = tmp_path / "output.m4b"
        mock_proc.reset_mock()
        await pipeline.run(book_file, output_m4b, resume=True, dry_run=False)
        mock_proc.export_m4b.assert_called_once()
        assert mock_proc.concatenate_to_file.call_args.args[1].suffix == ".mp3"
        assert mock_proc.export_m4b.call_args.kwargs["audio_path"].suffix == ".mp3"
        assert mock_proc.apply_mp3_tags.call_count == 0

        # Missing FFmpeg during M4B export surfaces a friendly RuntimeError
        mock_proc.export_m4b.side_effect = FileNotFoundError("ffmpeg missing")
        with pytest.raises(RuntimeError, match="FFmpeg is required for M4B"):
            await pipeline.run(book_file, output_m4b, resume=True, dry_run=False)
        mock_proc.export_m4b.side_effect = None

        # Test dry-run branch
        output_dry = tmp_path / "output_dry.mp3"
        await pipeline.run(book_file, output_dry, resume=True, dry_run=True)


def _voice(voice_id: str) -> Voice:
    return Voice(
        id=voice_id,
        locale="en_US",
        gender=GenderHint.FEMALE,
        age=AgeHint.ADULT,
    )


def _preset_pipeline(tmp_path: Path) -> AudioBookPipeline:
    return AudioBookPipeline(
        AudioBardConfig(db_path=tmp_path / "db.sqlite", cache_dir=tmp_path / "cache")
    )


def test_save_and_load_voice_preset_round_trip(tmp_path: Path) -> None:
    preset = VoicePreset.from_assignments(
        [
            VoiceAssignment(canonical_id="Narrator", voice_id="voice-a", rate=0.9),
            VoiceAssignment(canonical_id="Character_A", voice_id="voice-b"),
        ],
        name="series",
        locale="en_US",
        provider="piper",
    )
    path = tmp_path / "nested" / "preset.json"
    save_voice_preset(path, preset)

    loaded = load_voice_preset(path)
    assert loaded == preset
    assert loaded.name == "series"
    assert loaded.locale == "en_US"
    assert loaded.provider == "piper"


def test_merge_preset_overrides_covered_speakers(tmp_path: Path) -> None:
    pipeline = _preset_pipeline(tmp_path)
    mapped = [
        VoiceAssignment(canonical_id="Narrator", voice_id="voice-a"),
        VoiceAssignment(canonical_id="Character_A", voice_id="voice-a"),
    ]
    voice_map = {"voice-a": _voice("voice-a"), "voice-b": _voice("voice-b")}
    preset = VoicePreset.from_assignments(
        [VoiceAssignment(canonical_id="Character_A", voice_id="voice-b")]
    )

    merged = pipeline._merge_preset(mapped, preset, voice_map)

    assert [a.canonical_id for a in merged] == ["Narrator", "Character_A"]
    assert merged[0].voice_id == "voice-a"  # not covered by the preset
    assert merged[1].voice_id == "voice-b"  # covered, so the preset wins


def test_merge_preset_keeps_mapped_voice_when_preset_voice_is_unavailable(
    tmp_path: Path,
) -> None:
    pipeline = _preset_pipeline(tmp_path)
    mapped = [VoiceAssignment(canonical_id="Narrator", voice_id="voice-a")]
    preset = VoicePreset.from_assignments(
        [VoiceAssignment(canonical_id="Narrator", voice_id="voice-gone")]
    )

    merged = pipeline._merge_preset(mapped, preset, {"voice-a": _voice("voice-a")})

    assert merged[0].voice_id == "voice-a"


def test_merge_preset_without_preset_is_a_no_op(tmp_path: Path) -> None:
    pipeline = _preset_pipeline(tmp_path)
    mapped = [VoiceAssignment(canonical_id="Narrator", voice_id="voice-a")]

    assert pipeline._merge_preset(mapped, None, {}) == mapped
    empty = VoicePreset.from_assignments([])
    assert pipeline._merge_preset(mapped, empty, {}) == mapped


class _FakeTTS(TTSProvider):
    """Minimal TTS provider stand-in that records in-flight concurrency."""

    def __init__(self, delay: float = 0.01) -> None:
        self.delay = delay
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls: list[str] = []

    async def list_voices(self, locale: str) -> list[Voice]:
        return []

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        return b""

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float = 1.0,
        pitch: float = 1.0,
    ) -> bytes:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            self.calls.append(text)
            return f"mp3:{text}".encode()
        finally:
            self.in_flight -= 1


class _FailingTTS(TTSProvider):
    """Provider that always fails, to prove no partial clip is left behind."""

    def __init__(self) -> None:
        pass

    async def list_voices(self, locale: str) -> list[Voice]:
        return []

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        return b""

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float = 1.0,
        pitch: float = 1.0,
    ) -> bytes:
        raise RuntimeError("engine exploded")


def _fake_audio_segment() -> MagicMock:
    module = MagicMock()
    segment = MagicMock()
    segment.__len__ = MagicMock(return_value=500)
    module.from_file.return_value = segment
    return module


def _pool_pipeline(tmp_path: Path, concurrency: int) -> AudioBookPipeline:
    config = AudioBardConfig(
        db_path=tmp_path / "db.sqlite",
        cache_dir=tmp_path / "cache",
        tts_semaphore=concurrency,
    )
    return AudioBookPipeline(config)


def _assigned(count: int) -> list[tuple[Paragraph, str, Emotion]]:
    return [
        (Paragraph(text=f"paragraph {index}", chapter=0, index=index), "Narrator", Emotion.NEUTRAL)
        for index in range(count)
    ]


def _pool_voice() -> Voice:
    return Voice(
        id="voice-a",
        locale="en_US",
        gender=GenderHint.FEMALE,
        age=AgeHint.ADULT,
    )


@pytest.mark.asyncio
async def test_synthesize_paragraphs_bounds_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chapter with many paragraphs must never exceed tts_semaphore workers."""
    monkeypatch.setattr("audiobard.pipeline.AudioSegment", _fake_audio_segment())
    pipeline = _pool_pipeline(tmp_path, concurrency=2)
    fake = _FakeTTS(delay=0.02)
    pipeline.tts_provider = fake

    await pipeline._synthesize_paragraphs(7, _assigned(8), [], {}, [_pool_voice()])

    assert len(fake.calls) == 8
    assert fake.max_in_flight == 2
    assert fake.max_in_flight <= 2


@pytest.mark.asyncio
async def test_synthesize_paragraphs_writes_every_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("audiobard.pipeline.AudioSegment", _fake_audio_segment())
    pipeline = _pool_pipeline(tmp_path, concurrency=3)
    fake = _FakeTTS(delay=0.005)
    pipeline.tts_provider = fake

    await pipeline._synthesize_paragraphs(1, _assigned(6), [], {}, [_pool_voice()])

    for index in range(6):
        clip = pipeline.cache_dir / f"clip_1_{index}.mp3"
        meta = pipeline.cache_dir / f"clip_1_{index}.json"
        assert clip.exists()
        assert meta.exists()
        assert json.loads(meta.read_text(encoding="utf-8"))["duration_ms"] == 500
    assert not list(pipeline.cache_dir.glob("*.tmp"))


@pytest.mark.asyncio
async def test_synthesize_paragraphs_skips_cached_clips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("audiobard.pipeline.AudioSegment", _fake_audio_segment())
    pipeline = _pool_pipeline(tmp_path, concurrency=2)
    assert pipeline.cache_dir.is_dir()
    (pipeline.cache_dir / "clip_1_0.mp3").write_bytes(b"cached")
    (pipeline.cache_dir / "clip_1_0.json").write_text("{}", encoding="utf-8")
    fake = _FakeTTS(delay=0.005)
    pipeline.tts_provider = fake

    await pipeline._synthesize_paragraphs(1, _assigned(4), [], {}, [_pool_voice()])

    assert len(fake.calls) == 3  # paragraph 0 reused its cached clip
    assert (pipeline.cache_dir / "clip_1_0.mp3").read_bytes() == b"cached"


@pytest.mark.asyncio
async def test_synthesize_paragraphs_stops_when_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("audiobard.pipeline.AudioSegment", _fake_audio_segment())
    pipeline = _pool_pipeline(tmp_path, concurrency=1)
    fake = _FakeTTS(delay=0.005)
    pipeline.tts_provider = fake

    checks = {"count": 0}

    def cancel_check() -> bool:
        checks["count"] += 1
        return checks["count"] > 2

    with pytest.raises(asyncio.CancelledError):
        await pipeline._synthesize_paragraphs(
            1, _assigned(8), [], {}, [_pool_voice()], cancel_check=cancel_check
        )

    assert len(fake.calls) == 2


@pytest.mark.asyncio
async def test_failed_synthesis_leaves_no_partial_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("audiobard.pipeline.AudioSegment", _fake_audio_segment())
    pipeline = _pool_pipeline(tmp_path, concurrency=1)
    pipeline.tts_provider = _FailingTTS()

    with pytest.raises(RuntimeError, match="engine exploded"):
        await pipeline._synthesize_paragraphs(1, _assigned(2), [], {}, [_pool_voice()])

    assert list(pipeline.cache_dir.glob("*.mp3")) == []
    assert list(pipeline.cache_dir.glob("*.tmp")) == []


def test_chunk_band_is_contiguous_and_reaches_stage_end() -> None:
    from audiobard.pipeline import (
        _PROGRESS_SYNTHESIS_END,
        _PROGRESS_VOICE_END,
        _chunk_band,
    )

    bands = [_chunk_band(index, 4) for index in range(4)]
    assert bands[0][0] == _PROGRESS_VOICE_END
    assert bands[-1][1] == _PROGRESS_SYNTHESIS_END
    assert all(bands[i][1] == bands[i + 1][0] for i in range(3))


def test_paragraph_progress_stays_inside_its_band_and_monotonic() -> None:
    from audiobard.pipeline import _make_paragraph_progress

    events: list[PipelineProgress] = []
    report = _make_paragraph_progress(events.append, idx=1, total_chunks=4, band=(30, 50))
    assert report is not None
    for done in (1, 2, 3):
        report(done, 3)

    percents = [event.percent for event in events]
    assert percents == sorted(percents)
    assert percents[0] >= 30
    assert percents[-1] <= 50
    assert all(event.stage == "synthesis" for event in events)


def test_paragraph_progress_without_callback_returns_none() -> None:
    from audiobard.pipeline import _make_paragraph_progress

    assert _make_paragraph_progress(None, 0, 1, (20, 90)) is None


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
        f'CHAPTER I\n\n{long_para}\n\n{long_para}\n\nCHAPTER II\n\n"Hello" said Z.',
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


@pytest.mark.asyncio
async def test_pipeline_pdf_file_raises_pdf2bard_hint(tmp_path: Path) -> None:
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy")
    config = AudioBardConfig(db_path=tmp_path / "test.db", cache_dir=tmp_path / "cache")
    pipeline = AudioBookPipeline(config)

    with pytest.raises(ValueError, match="PDF2Bard"):
        await pipeline.run(pdf_file, tmp_path / "out.mp3")
