"""Tests for Piper TTS Provider."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.piper_provider import PiperProvider


@pytest.mark.asyncio
async def test_piper_list_voices() -> None:
    """Test that list_voices parses the voice file pool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        # Write dummy voice pool file
        pool_file = voices_dir / "en_US.json"
        pool_file.write_text(
            """[
            {"id": "en_US-dummy-medium", "locale": "en_US",
             "gender": "male", "age": "adult", "energy": 0.5}
        ]""",
            encoding="utf-8",
        )

        config = AudioBardConfig(
            cache_dir=tmp_path,
            voices_dir=voices_dir,
            db_path=tmp_path / "test.db",
        )

        provider = PiperProvider(config)
        voices = await provider.list_voices("en_US")
        assert len(voices) == 1
        assert voices[0].id == "en_US-dummy-medium"
        assert voices[0].gender == GenderHint.MALE


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_downloads_if_missing() -> None:
    """Test that ensure_model downloads missing voice files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        # Mock download URLs
        base_url = (
            "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
            "en/en_US/dummy/medium/en_US-dummy-medium"
        )
        respx.get(f"{base_url}.onnx").mock(
            return_value=Response(200, content=b"onnx-data")
        )
        respx.get(f"{base_url}.onnx.json").mock(
            return_value=Response(200, content=b'{"config": true}')
        )

        provider = PiperProvider(config)
        onnx_file = await provider._ensure_model("en_US-dummy-medium")

        assert onnx_file.exists()
        assert onnx_file.read_bytes() == b"onnx-data"
        assert (tmp_path / "piper" / "en_US-dummy-medium.onnx.json").exists()


@pytest.mark.asyncio
@patch("shutil.which")
@patch("asyncio.create_subprocess_exec")
async def test_piper_synthesize_raw(
    mock_subproc: AsyncMock, mock_which: AsyncMock
) -> None:
    """Test that subprocess is run correctly and returns converted MP3 bytes."""
    mock_which.return_value = "/usr/bin/piper"

    # Mock subprocess return value
    # Piper outputs WAV. We will mock the output to be a valid basic WAV header + silent bytes,
    # so that pydub doesn't fail to decode it.
    # Standard 44-byte WAV header:
    wav_header = (
        b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x22\x56\x00\x00\x44\xAC\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
        b"\x00\x00\x00\x00"
    )

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (wav_header, b"")
    mock_process.returncode = 0
    mock_subproc.return_value = mock_process

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        # Pre-seed cached voice files so we don't try to download them
        piper_dir = tmp_path / "piper"
        piper_dir.mkdir()
        (piper_dir / "en_US-dummy-medium.onnx").write_bytes(b"onnx-data")
        (piper_dir / "en_US-dummy-medium.onnx.json").write_bytes(b"{}")

        provider = PiperProvider(config)
        voice = Voice(
            id="en_US-dummy-medium",
            locale="en_US",
            gender=GenderHint.MALE,
            age=AgeHint.ADULT,
        )

        # Override ensure_model call to avoid checks
        with patch.object(
            provider, "_ensure_model", return_value=piper_dir / "en_US-dummy-medium.onnx"
        ):
            mp3_bytes = await provider._synthesize_raw(
                "Hello", voice, Emotion.HAPPY, rate=1.1, pitch=1.0
            )

            # verify that the conversion yielded non-empty audio output bytes
            assert len(mp3_bytes) > 0
            assert mock_subproc.called

            # Check that length_scale was set according to rate
            # (1 / (1.1 * happy_emotion_rate(1.1)))
            # happy_emotion_rate = 1.10
            # final_rate = 1.1 * 1.1 = 1.21
            # length_scale = 1.0 / 1.21 = 0.826
            called_args = mock_subproc.call_args[0]
            assert called_args[0] == "/usr/bin/piper"
            assert "--length_scale" in called_args
            scale_idx = called_args.index("--length_scale")
            assert called_args[scale_idx + 1] == "0.826"


@pytest.mark.asyncio
async def test_piper_list_voices_missing_pool(tmp_path: Path) -> None:
    config = AudioBardConfig(
        cache_dir=tmp_path,
        voices_dir=tmp_path / "nonexistent_voices",
        db_path=tmp_path / "test.db",
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []


@pytest.mark.asyncio
@patch("shutil.which", return_value=None)
async def test_piper_missing_executable(mock_which: Any, tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)
    with pytest.raises(FileNotFoundError, match="piper executable not found"):
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/piper")
@patch("asyncio.create_subprocess_exec")
async def test_piper_subprocess_error(
    mock_subproc: AsyncMock, mock_which: Any, tmp_path: Path
) -> None:
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Piper internal error")
    mock_subproc.return_value = mock_proc

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)

    with (
        patch.object(provider, "_ensure_model", return_value=tmp_path / "v1.onnx"),
        pytest.raises(RuntimeError, match="Piper process exited with code 1"),
    ):
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)


@pytest.mark.asyncio
async def test_piper_list_voices_not_list(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US.json").write_text('{"not": "a list"}', encoding="utf-8")
    config = AudioBardConfig(
        cache_dir=tmp_path, voices_dir=voices_dir, db_path=tmp_path / "test.db"
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []


@pytest.mark.asyncio
async def test_piper_list_voices_invalid_json(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US.json").write_text("invalid json content", encoding="utf-8")
    config = AudioBardConfig(
        cache_dir=tmp_path, voices_dir=voices_dir, db_path=tmp_path / "test.db"
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []



@pytest.mark.asyncio
async def test_piper_ensure_model_cached(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)
    onnx_file = piper_dir / "en_US-dummy-medium.onnx"
    json_file = piper_dir / "en_US-dummy-medium.onnx.json"
    onnx_file.write_bytes(b"cached-onnx")
    json_file.write_bytes(b"{}")

    provider = PiperProvider(config)
    result = await provider._ensure_model("en_US-dummy-medium")
    assert result == onnx_file


@pytest.mark.asyncio
async def test_piper_ensure_model_invalid_voice_id(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    with pytest.raises(ValueError, match="Invalid voice ID format"):
        await provider._ensure_model("invalid_id")

