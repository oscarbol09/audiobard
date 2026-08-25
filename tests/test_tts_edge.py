"""Tests for Edge-TTS Cloud Provider."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.edge_provider import EdgeProvider


@pytest.mark.asyncio
@patch("edge_tts.list_voices")
async def test_edge_list_voices(mock_list: MagicMock) -> None:
    """Test that list_voices maps fields and filters correctly."""
    mock_list.return_value = [
        {
            "ShortName": "en-US-EmmaMultilingualNeural",
            "Locale": "en-US",
            "Gender": "Female",
        },
        {
            "ShortName": "es-ES-AlvaroNeural",
            "Locale": "es-ES",
            "Gender": "Male",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        provider = EdgeProvider(config)

        # Querying en_US
        voices = await provider.list_voices("en_US")
        assert len(voices) == 1
        assert voices[0].id == "en-US-EmmaMultilingualNeural"
        assert voices[0].gender == GenderHint.FEMALE
        assert voices[0].age == AgeHint.ADULT


@pytest.mark.asyncio
@patch("edge_tts.Communicate")
async def test_edge_synthesize_raw(mock_comm_cls: MagicMock) -> None:
    """Test that pitch and rate formatting is correct and stream returns audio data."""
    # Mock stream async generator
    mock_comm = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"mp3-bytes"}

    mock_comm.stream = mock_stream
    mock_comm_cls.return_value = mock_comm

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        provider = EdgeProvider(config)
        voice = Voice(
            id="en-US-EmmaNeural",
            locale="en_US",
            gender=GenderHint.FEMALE,
            age=AgeHint.ADULT,
        )

        # Emotion.HAPPY has rate 1.10, pitch 1.08 in EMOTION_PROSODY
        # Pass custom rate=1.1, pitch=1.0
        # final_rate = 1.1 * 1.1 = 1.21 -> +21.0%
        # final_pitch = 1.0 * 1.08 = 1.08 -> +8Hz
        audio_data = await provider._synthesize_raw(
            "Hello", voice, Emotion.HAPPY, rate=1.1, pitch=1.0
        )

        assert audio_data == b"mp3-bytes"
        mock_comm_cls.assert_called_once_with(
            text="Hello",
            voice="en-US-EmmaNeural",
            rate="+21%",
            pitch="+8Hz",
        )


@pytest.mark.asyncio
@patch("edge_tts.list_voices", side_effect=RuntimeError("Network Error"))
async def test_edge_list_voices_error(mock_list: MagicMock, tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = EdgeProvider(config)
    voices = await provider.list_voices("en_US")
    assert voices == []


@pytest.mark.asyncio
@patch("edge_tts.Communicate")
async def test_edge_synthesize_negative_prosody(mock_comm_cls: MagicMock, tmp_path: Path) -> None:
    mock_comm = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"mp3-bytes"}

    mock_comm.stream = mock_stream
    mock_comm_cls.return_value = mock_comm

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = EdgeProvider(config)
    voice = Voice(
        id="en-US-EmmaNeural",
        locale="en_US",
        gender=GenderHint.FEMALE,
        age=AgeHint.ADULT,
    )

    # SAD emotion has rate 0.85, pitch 0.92
    await provider._synthesize_raw("Hello", voice, Emotion.SAD, rate=1.0, pitch=1.0)
    mock_comm_cls.assert_called_once_with(
        text="Hello",
        voice="en-US-EmmaNeural",
        rate="-15%",
        pitch="-8Hz",
    )


@pytest.mark.asyncio
@patch("edge_tts.list_voices")
async def test_edge_list_voices_male(mock_list: MagicMock, tmp_path: Path) -> None:
    mock_list.return_value = [
        {
            "ShortName": "es-ES-AlvaroNeural",
            "Locale": "es-ES",
            "Gender": "Male",
        }
    ]
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = EdgeProvider(config)
    voices = await provider.list_voices("es_ES")
    assert len(voices) == 1
    assert voices[0].gender == GenderHint.MALE


@pytest.mark.asyncio
@patch("edge_tts.Communicate")
async def test_edge_synthesize_empty_stream(mock_comm_cls: MagicMock, tmp_path: Path) -> None:
    mock_comm = MagicMock()

    async def empty_stream():
        if False:
            yield {}

    mock_comm.stream = empty_stream
    mock_comm_cls.return_value = mock_comm

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = EdgeProvider(config)
    voice = Voice(
        id="en-US-EmmaNeural",
        locale="en_US",
        gender=GenderHint.FEMALE,
        age=AgeHint.ADULT,
    )
    with pytest.raises(RuntimeError, match="Edge TTS returned no audio data"):
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, rate=1.0, pitch=1.0)

