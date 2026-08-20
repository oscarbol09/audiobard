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
