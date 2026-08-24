"""Tests for audiobard.progress and the pipeline progress callback."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audiobard.config import AudioBardConfig
from audiobard.pipeline import AudioBookPipeline
from audiobard.progress import PipelineProgress

# Pure dataclass behaviour ----------------------------------------------------


def test_progress_percent_must_be_in_range() -> None:
    with pytest.raises(ValueError, match="percent must be in 0..100"):
        PipelineProgress(stage="synthesis", percent=-1, message="bad")
    with pytest.raises(ValueError, match="percent must be in 0..100"):
        PipelineProgress(stage="synthesis", percent=101, message="bad")


def test_progress_stage_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="stage must be a non-empty string"):
        PipelineProgress(stage="", percent=50, message="bad")


def test_progress_is_immutable() -> None:
    progress = PipelineProgress(stage="synthesis", percent=50, message="ok")
    with pytest.raises(FrozenInstanceError):
        progress.percent = 60  # type: ignore[misc]


# Pipeline integration --------------------------------------------------------


@contextmanager
def _stubbed_pipeline(tmp_path: Path):
    """Yield (pipeline, llm_client, tts_provider, audio_processor) with heavy deps stubbed.

    Patches the AudioBookPipeline factories and chunk_paragraphs so the
    test can run in milliseconds without spinning real LLM/TTS calls.
    """
    config = AudioBardConfig(
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        tts_provider="piper",
        tts_locale="en-US",
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "db.sqlite",
        voices_dir=tmp_path / "voices",
    )

    llm_client = MagicMock()
    llm_client.extract_characters = AsyncMock(return_value=MagicMock(characters=[]))
    llm_client.attribute_dialog = AsyncMock(return_value=MagicMock(lines=[]))

    tts_provider = MagicMock()
    tts_provider.list_voices = AsyncMock(
        return_value=[MagicMock(id="voice-1", name="Voice 1")]
    )
    tts_provider.synthesize = AsyncMock(return_value=b"mp3-bytes")

    audio_processor = MagicMock()
    audio_processor.concatenate = AsyncMock(return_value=b"final-mp3")
    audio_processor.export_mp3 = AsyncMock(return_value=None)
    audio_processor.export_m4b = AsyncMock(return_value=None)

    persistence = MagicMock()
    persistence.get_or_create_book.return_value = 1
    persistence.get_checkpoint.return_value = None

    # Write a minimal voice pool file so VoiceMapper (when reached) does not crash.
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / "en-US.json").write_text(
        '[{"id":"voice-1","locale":"en-US","gender":"neutral","age":"adult",'
        '"energy":0.5,"sample_text":"sample"}]',
        encoding="utf-8",
    )

    paragraph_mock = MagicMock(
        index=0, text="Hello world.", is_dialog=False, chapter=0
    )

    from audiobard import pipeline as pipeline_mod

    original_chunk = pipeline_mod.chunk_paragraphs
    pipeline_mod.chunk_paragraphs = lambda _p, chunk_size=1500: [[paragraph_mock]]

    with (
        patch("audiobard.pipeline.create_llm_client", return_value=llm_client),
        patch("audiobard.pipeline.create_tts_provider", return_value=tts_provider),
    ):
        pipeline = AudioBookPipeline(config)

    # Pre-create the clip + meta files so the synthesis loop's cache-hit
    # branch fires; this keeps the test fast and avoids trying to
    # decode the fake MP3 bytes the mock TTS returns.
    clip_file = pipeline.cache_dir / "clip_1_0.mp3"
    meta_file = pipeline.cache_dir / "clip_1_0.json"
    clip_file.write_bytes(b"x")
    meta_file.write_text('{"speaker":"Narrator","emotion":"neutral","duration_ms":1000}',
                         encoding="utf-8")
    pipeline.persistence = persistence
    pipeline.audio_processor = audio_processor
    pipeline._llm_semaphore = asyncio.Semaphore(1)

    try:
        yield pipeline, llm_client, tts_provider, audio_processor
    finally:
        pipeline_mod.chunk_paragraphs = original_chunk


def _run(coro: object) -> None:
    asyncio.run(coro)


def test_progress_callback_called_at_each_stage(tmp_path: Path) -> None:
    """The pipeline must emit progress for every stage when a callback is wired."""
    book = tmp_path / "book.txt"
    book.write_text("Hello world.", encoding="utf-8")
    output = tmp_path / "out.mp3"

    with _stubbed_pipeline(tmp_path) as (pipeline, _llm, _tts, _audio):
        events: list[PipelineProgress] = []

        async def run() -> None:
            await pipeline.run(book, output, progress_callback=events.append)

        _run(run())

    stages = [e.stage for e in events]
    assert "parsing" in stages
    assert "characters" in stages
    assert "voice_assignment" in stages
    assert "synthesis" in stages
    assert "assembly" in stages
    assert stages[-1] == "complete"

    percents = [e.percent for e in events]
    assert percents[0] == 0
    assert percents[-1] == 100
    assert percents == sorted(percents), f"Progress must be monotonic, got {percents}"


def test_progress_callback_errors_do_not_abort_pipeline(tmp_path: Path) -> None:
    """A broken callback must not prevent the pipeline from completing."""
    book = tmp_path / "book.txt"
    book.write_text("Hi.", encoding="utf-8")
    output = tmp_path / "out.mp3"

    with _stubbed_pipeline(tmp_path) as (pipeline, _llm, _tts, audio):
        def broken(_progress: PipelineProgress) -> None:
            raise RuntimeError("subscriber exploded")

        async def run() -> None:
            await pipeline.run(book, output, progress_callback=broken)

        _run(run())

    assert audio.export_mp3.await_count == 1


def test_progress_callback_default_none_is_backward_compatible(tmp_path: Path) -> None:
    """Existing callers that omit progress_callback must keep working."""
    book = tmp_path / "book.txt"
    book.write_text("Backward compat.", encoding="utf-8")
    output = tmp_path / "out.mp3"

    with _stubbed_pipeline(tmp_path) as (pipeline, _llm, _tts, audio):

        async def run() -> None:
            await pipeline.run(book, output)

        _run(run())

    assert audio.export_mp3.await_count == 1


def test_progress_zero_chunks_does_not_divide_by_zero() -> None:
    """The helper must guard against total==0 without raising."""
    from audiobard.pipeline import _emit_chunk_progress

    events: list[PipelineProgress] = []
    _emit_chunk_progress(events.append, idx=0, total=0, message="empty")
    assert events[-1].percent == 90  # _PROGRESS_SYNTHESIS_END

    events.clear()
    _emit_chunk_progress(events.append, idx=-1, total=0, message="neg")
    assert events[-1].percent == 90


def test_progress_chunk_helper_progresses_monotonically() -> None:
    """The percent must advance as chunks complete and never exceed the stage end."""
    from audiobard.pipeline import _emit_chunk_progress

    percents: list[int] = []
    for idx in range(5):
        _emit_chunk_progress(
            lambda p: percents.append(p.percent),
            idx=idx,
            total=5,
            message="x",
        )
    assert percents == sorted(percents)
    assert percents[0] > 20
    assert percents[-1] == 90
