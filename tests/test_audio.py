"""Tests for the Audio Processor and AudioClip model."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydub import AudioSegment

from audiobard.audio.processor import (
    FFMPEG_MISSING_MESSAGE,
    AudioClip,
    AudioProcessor,
    ChapterMarker,
    find_ffmpeg,
)
from audiobard.models import Emotion


def _create_dummy_mp3() -> bytes:
    """Generate a dummy silent MP3 segment using pydub."""
    segment = AudioSegment.silent(duration=500)
    out = io.BytesIO()
    segment.export(out, format="mp3")
    return out.getvalue()


def _create_audible_mp3() -> bytes:
    """Generate a dummy non-silent MP3 segment using pydub."""
    # A 500ms segment of noise/signal with finite dBFS
    raw_data = (b"\x10\x20\x30\x40" * 2500)
    segment = AudioSegment(data=raw_data, sample_width=2, frame_rate=44100, channels=2)
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
async def test_audio_processor_concatenate_normalizes_audible() -> None:
    """Test that concatenate applies gain normalization when audio is audible (finite dBFS)."""
    audible_mp3 = _create_audible_mp3()
    clips = [
        AudioClip(
            mp3_bytes=audible_mp3,
            speaker="Character_A",
            emotion=Emotion.NEUTRAL,
            duration_ms=500,
        )
    ]
    processor = AudioProcessor()
    out_bytes = await processor.concatenate(clips)
    assert len(out_bytes) > 0



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
@patch("audiobard.audio.processor.find_ffmpeg", return_value="/usr/bin/ffmpeg")
@patch("asyncio.create_subprocess_exec")
async def test_audio_processor_export_m4b(
    mock_subproc: AsyncMock, mock_find: Any
) -> None:
    """Test that export_m4b generates ffmetadata and calls ffmpeg to convert and inject."""
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


@pytest.mark.asyncio
async def test_audio_processor_concatenate_empty() -> None:
    processor = AudioProcessor()
    out = await processor.concatenate([])
    assert out == b""


@pytest.mark.asyncio
@patch("audiobard.audio.processor.find_ffmpeg", return_value=None)
async def test_audio_processor_export_m4b_missing_ffmpeg(mock_find: Any) -> None:
    processor = AudioProcessor()
    with pytest.raises(FileNotFoundError, match="FFmpeg is required for M4B"):
        await processor.export_m4b(b"data", Path("out.m4b"), [])
    with pytest.raises(FileNotFoundError) as exc_info:
        await processor.export_m4b(b"data", Path("out.m4b"), [])
    assert str(exc_info.value) == FFMPEG_MISSING_MESSAGE


@pytest.mark.asyncio
@patch("audiobard.audio.processor.find_ffmpeg", return_value="/usr/bin/ffmpeg")
@patch("asyncio.create_subprocess_exec")
async def test_audio_processor_export_m4b_proc1_error(
    mock_subproc: AsyncMock, mock_find: Any
) -> None:
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Conversion Error")
    mock_subproc.return_value = mock_proc

    processor = AudioProcessor()
    with pytest.raises(RuntimeError, match="FFmpeg raw M4B export failed"):
        await processor.export_m4b(b"data", Path("out.m4b"), [])


@pytest.mark.asyncio
@patch("audiobard.audio.processor.find_ffmpeg", return_value="/usr/bin/ffmpeg")
@patch("asyncio.create_subprocess_exec")
async def test_audio_processor_export_m4b_proc2_error(
    mock_subproc: AsyncMock, mock_find: Any
) -> None:
    mock_proc1 = AsyncMock()
    mock_proc1.returncode = 0
    mock_proc1.communicate.return_value = (b"", b"")

    mock_proc2 = AsyncMock()
    mock_proc2.returncode = 1
    mock_proc2.communicate.return_value = (b"", b"Injection Error")

    mock_subproc.side_effect = [mock_proc1, mock_proc2]

    processor = AudioProcessor()
    with pytest.raises(RuntimeError, match="FFmpeg chapter injection failed"):
        await processor.export_m4b(b"data", Path("out.m4b"), [])


def _clear_ffmpeg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("AUDIOBARD_FFMPEG", "FFMPEG_BINARY", "FFMPEG_PATH"):
        monkeypatch.delenv(name, raising=False)


def _block_imageio_import() -> Any:
    import builtins

    real_import = builtins.__import__

    def _import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "imageio_ffmpeg":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    return _import


def test_find_ffmpeg_prefers_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    binary.write_bytes(b"")
    monkeypatch.setenv("AUDIOBARD_FFMPEG", str(binary))
    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        assert find_ffmpeg() == str(binary.resolve())


def test_find_ffmpeg_uses_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ffmpeg_env(monkeypatch)
    with patch("shutil.which", return_value="/usr/local/bin/ffmpeg"):
        assert find_ffmpeg() == "/usr/local/bin/ffmpeg"


def test_find_ffmpeg_falls_back_to_imageio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_ffmpeg_env(monkeypatch)
    bundled = tmp_path / "imageio-ffmpeg"
    bundled.write_bytes(b"")
    fake_mod = MagicMock()
    fake_mod.get_ffmpeg_exe.return_value = str(bundled)
    with (
        patch("shutil.which", return_value=None),
        patch.dict(sys.modules, {"imageio_ffmpeg": fake_mod}),
    ):
        assert find_ffmpeg() == str(bundled.resolve())


def test_find_ffmpeg_falls_back_to_tools_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_ffmpeg_env(monkeypatch)
    tools = tmp_path / "tools"
    tools.mkdir()
    binary = tools / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    binary.write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    with (
        patch("shutil.which", return_value=None),
        patch("builtins.__import__", side_effect=_block_imageio_import()),
    ):
        assert find_ffmpeg() == str(binary.resolve())


def test_find_ffmpeg_returns_none_when_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_ffmpeg_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    with (
        patch("shutil.which", return_value=None),
        patch("builtins.__import__", side_effect=_block_imageio_import()),
    ):
        assert find_ffmpeg() is None
