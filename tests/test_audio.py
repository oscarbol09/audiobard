"""Tests for the Audio Processor and AudioClip model."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydub import AudioSegment

from audiobard.audio.processor import AudioClip, AudioProcessor, ChapterMarker
from audiobard.models import Emotion


def _create_dummy_mp3() -> bytes:
    """Generate a dummy silent MP3 segment using pydub."""
    segment = AudioSegment.silent(duration=500)
    out = io.BytesIO()
    segment.export(out, format="mp3")
    return out.getvalue()


@pytest.mark.asyncio
async def test_audio_clip_validation() -> None:
    """Test AudioClip model structure and validation."""
    dummy_bytes = b"mp3"
    clip = AudioClip(
        mp3_bytes=dummy_bytes,
        speaker="Character_A",
        emotion=Emotion.HAPPY,
        duration_ms=1000,
    )
    assert clip.mp3_bytes == dummy_bytes
    assert clip.speaker == "Character_A"
    assert clip.emotion == Emotion.HAPPY
    assert clip.duration_ms == 1000


@pytest.mark.asyncio
async def test_audio_processor_concatenate() -> None:
    """Test that concatenate merges clips, inserts silence, and normalizes."""
    dummy_mp3 = _create_dummy_mp3()
    clips = [
        AudioClip(
            mp3_bytes=dummy_mp3,
            speaker="Character_A",
            emotion=Emotion.HAPPY,
            duration_ms=500,
        ),
        AudioClip(
            mp3_bytes=dummy_mp3,
            speaker="Character_B",
            emotion=Emotion.SAD,
            duration_ms=500,
        ),
    ]

    processor = AudioProcessor()
    out_bytes = await processor.concatenate(clips)
    assert len(out_bytes) > 0

    # Load result back to verify duration.
    # Clip 1 (500ms) + happy gap (200ms) + Clip 2 (500ms) + sad gap (400ms) = ~1600ms
    segment = AudioSegment.from_file(io.BytesIO(out_bytes), format="mp3")
    assert abs(len(segment) - 1600) < 100  # allow small compression variance


@pytest.mark.asyncio
async def test_audio_processor_export_mp3() -> None:
    """Test export_mp3 writing output files."""
    processor = AudioProcessor()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "output.mp3"
        data = b"mp3-data"
        await processor.export_mp3(data, out_path)
        assert out_path.exists()
        assert out_path.read_bytes() == data


@pytest.mark.asyncio
@patch("shutil.which")
@patch("asyncio.create_subprocess_exec")
async def test_audio_processor_export_m4b(
    mock_subproc: AsyncMock, mock_which: AsyncMock
) -> None:
    """Test that export_m4b generates ffmetadata and calls ffmpeg to convert and inject."""
    mock_which.return_value = "/usr/bin/ffmpeg"

    # Mock both ffmpeg subprocess runs
    mock_proc1 = AsyncMock()
    mock_proc1.returncode = 0
    mock_proc1.communicate.return_value = (b"", b"")

    mock_proc2 = AsyncMock()
    mock_proc2.returncode = 0
    mock_proc2.communicate.return_value = (b"", b"")

    mock_subproc.side_effect = [mock_proc1, mock_proc2]

    processor = AudioProcessor()
    chapters = [
        ChapterMarker(title="Ch 1", start_ms=0, end_ms=5000),
        ChapterMarker(title="Ch 2", start_ms=5000, end_ms=10000),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "output.m4b"
        await processor.export_m4b(b"audio-data", out_path, chapters)

        assert mock_subproc.call_count == 2

        # Check call arguments
        call1_args = mock_subproc.call_args_list[0][0]
        assert call1_args[0] == "/usr/bin/ffmpeg"
        assert "-c:a" in call1_args
        assert "aac" in call1_args

        call2_args = mock_subproc.call_args_list[1][0]
        assert call2_args[0] == "/usr/bin/ffmpeg"
        assert "-map_metadata" in call2_args
        assert "1" in call2_args
        assert "-codec" in call2_args
        assert "copy" in call2_args
