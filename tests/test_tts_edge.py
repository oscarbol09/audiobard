"""Tests for Edge-TTS Cloud Provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts import edge_provider
from audiobard.tts.edge_provider import EdgeProvider


@pytest.mark.asyncio
@patch("edge_tts.list_voices")
async def test_edge_list_voices(mock_list: MagicMock, tmp_path: Path) -> None:
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
async def test_edge_synthesize_raw(mock_comm_cls: MagicMock, tmp_path: Path) -> None:
    """Test that pitch and rate formatting is correct and stream returns audio data."""
    # Mock stream async generator
    mock_comm = MagicMock()

    async def mock_stream() -> Any:
        yield {"type": "audio", "data": b"mp3-bytes"}

    mock_comm.stream = mock_stream
    mock_comm_cls.return_value = mock_comm

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

    async def mock_stream() -> Any:
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

    async def empty_stream() -> Any:
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


@pytest.mark.asyncio
async def test_edge_offline_falls_back_to_bundled_snapshot(tmp_path: Path) -> None:
    """Regression (#64): an unreachable service must not empty the voice picker."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=ConnectionError("offline")):
        voices = await EdgeProvider(config).list_voices("en_US")

    assert voices
    assert all(v.locale == "en_US" for v in voices)
    by_id = {v.id: v for v in voices}
    assert by_id["en-US-AriaNeural"].gender is GenderHint.FEMALE
    assert by_id["en-US-GuyNeural"].gender is GenderHint.MALE
    assert by_id["en-US-AriaNeural"].age is AgeHint.ADULT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [ConnectionError("offline"), TimeoutError("timed out"), OSError("no route to host")],
)
async def test_edge_offline_fallback_error_types(error: Exception, tmp_path: Path) -> None:
    """Every "network is down" error type must trigger the snapshot fallback."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=error):
        voices = await EdgeProvider(config).list_voices("es_ES")
    assert voices
    assert all(v.locale == "es_ES" for v in voices)


@pytest.mark.asyncio
async def test_edge_offline_fallback_still_filters_by_locale(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=ConnectionError("offline")):
        voices = await EdgeProvider(config).list_voices("de_DE")
    assert voices
    assert {v.locale for v in voices} == {"de_DE"}
    assert all(v.id.startswith("de-DE-") for v in voices)


@pytest.mark.asyncio
async def test_edge_offline_fallback_unknown_locale_is_empty(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=ConnectionError("offline")):
        voices = await EdgeProvider(config).list_voices("xx_XX")
    assert voices == []


@pytest.mark.asyncio
async def test_edge_offline_fallback_missing_snapshot_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing snapshot must degrade to the previous empty-list behaviour."""
    monkeypatch.setattr(
        edge_provider, "_BUNDLED_VOICES_PATH", tmp_path / "missing.json"
    )
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=ConnectionError("offline")):
        voices = await EdgeProvider(config).list_voices("en_US")
    assert voices == []


def test_load_bundled_voices_handles_malformed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "edge_voices_cache.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(edge_provider, "_BUNDLED_VOICES_PATH", broken)
    assert edge_provider._load_bundled_voices() == []


def test_load_bundled_voices_handles_unexpected_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shaped = tmp_path / "edge_voices_cache.json"
    shaped.write_text('{"voices": "not-a-list"}', encoding="utf-8")
    monkeypatch.setattr(edge_provider, "_BUNDLED_VOICES_PATH", shaped)
    assert edge_provider._load_bundled_voices() == []


def test_bundled_snapshot_is_well_formed() -> None:
    """The shipped snapshot must stay loadable and internally consistent."""
    import json

    payload = json.loads(
        edge_provider._BUNDLED_VOICES_PATH.read_text(encoding="utf-8")
    )
    entries = edge_provider._load_bundled_voices()
    assert entries
    assert payload["voice_count"] == len(entries)
    assert sorted({e["Locale"] for e in entries}) == payload["locales"]
    for entry in entries:
        assert entry["ShortName"]
        assert entry["Locale"]
        assert entry["Gender"] in {"Male", "Female", "Neutral"}
    # Every snapshot entry must be accepted by the Voice contract.
    for entry in entries:
        Voice(
            id=entry["ShortName"],
            locale=entry["Locale"].replace("-", "_"),
            gender=GenderHint.MALE,
            age=AgeHint.ADULT,
        )


def test_bundled_locale_counts_matches_snapshot() -> None:
    counts = edge_provider.bundled_locale_counts()
    entries = edge_provider._load_bundled_voices()
    assert sum(counts.values()) == len(entries)
    assert counts["en_US"] >= 1
    assert counts["es_ES"] >= 1
    assert all(isinstance(count, int) and count > 0 for count in counts.values())


@pytest.mark.asyncio
async def test_edge_available_locales_is_offline(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    with patch("edge_tts.list_voices", side_effect=ConnectionError("offline")):
        counts = await EdgeProvider(config).available_locales()
    assert counts["en_US"] >= 1

