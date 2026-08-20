"""Tests for the base TTS provider and caching mechanisms."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.base import MemoryCache, TTSProvider


class DummyProvider(TTSProvider):
    """Subclass of TTSProvider for testing caching behavior."""

    def __init__(self, config: AudioBardConfig) -> None:
        super().__init__(config)
        self.synthesize_calls = 0

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        self.synthesize_calls += 1
        return f"audio:{text}:{voice.id}:{emotion.value}".encode()

    async def list_voices(self, locale: str) -> list[Voice]:
        return []


def test_memory_cache_eviction() -> None:
    """Test that MemoryCache pops items to stay under max_bytes limit."""
    cache = MemoryCache(max_bytes=15)

    # Adding a 10 byte item
    cache.set(("h1", "v1", "e1"), b"1234567890")
    assert cache.get(("h1", "v1", "e1")) == b"1234567890"

    # Adding another 10 byte item triggers eviction of the first one
    cache.set(("h2", "v2", "e2"), b"abcdefghij")
    assert cache.get(("h2", "v2", "e2")) == b"abcdefghij"
    assert cache.get(("h1", "v1", "e1")) is None


@pytest.mark.asyncio
async def test_tts_provider_cache_flow() -> None:
    """Test that TTSProvider checks memory and disk cache correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = AudioBardConfig(
            cache_dir=Path(tmpdir),
            db_path=Path(tmpdir) / "test.db",
        )
        provider = DummyProvider(config)
        voice = Voice(
            id="en_US-test-medium",
            locale="en_US",
            gender=GenderHint.MALE,
            age=AgeHint.ADULT,
        )

        text = "Hello, world!"
        emotion = Emotion.HAPPY

        # First call: should call internal synthesize
        data1 = await provider.synthesize(text, voice, emotion)
        assert provider.synthesize_calls == 1
        assert data1 == b"audio:Hello, world!:en_US-test-medium:happy"

        # Second call: should hit memory cache (no increase in synthesize_calls)
        data2 = await provider.synthesize(text, voice, emotion)
        assert provider.synthesize_calls == 1
        assert data2 == data1

        # Bypass/Clear memory cache to force disk cache check
        provider._memory_cache = MemoryCache()
        data3 = await provider.synthesize(text, voice, emotion)
        assert provider.synthesize_calls == 1
        assert data3 == data1


def test_memory_cache_update_existing() -> None:
    cache = MemoryCache(max_bytes=100)
    key = ("h1", "v1", "e1")
    cache.set(key, b"123")
    assert cache.get(key) == b"123"
    assert cache.current_bytes == 3

    # Update existing key
    cache.set(key, b"12345")
    assert cache.get(key) == b"12345"
    assert cache.current_bytes == 5


@pytest.mark.asyncio
async def test_tts_disk_write_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from unittest.mock import patch

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = DummyProvider(config)
    voice = Voice(
        id="en_US-test-medium",
        locale="en_US",
        gender=GenderHint.MALE,
        age=AgeHint.ADULT,
    )

    with patch("pathlib.Path.write_bytes", side_effect=OSError("Disk Full")):
        data = await provider.synthesize("Hello", voice, Emotion.NEUTRAL)
        assert len(data) > 0
