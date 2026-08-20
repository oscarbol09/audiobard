"""Base class for all Text-to-Speech (TTS) providers with caching and emotion maps."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict

from audiobard.config import AudioBardConfig
from audiobard.models import Emotion, Voice

logger = logging.getLogger(__name__)


# Shared emotion to prosody mapping (rates/pitches/silence gaps)
EMOTION_PROSODY = {
    Emotion.HAPPY: {"rate": 1.10, "pitch": 1.08, "pause_after_ms": 200},
    Emotion.SAD: {"rate": 0.85, "pitch": 0.92, "pause_after_ms": 400},
    Emotion.ANGRY: {"rate": 1.15, "pitch": 1.05, "pause_after_ms": 250},
    Emotion.FEARFUL: {"rate": 1.05, "pitch": 1.12, "pause_after_ms": 300},
    Emotion.SURPRISED: {"rate": 1.08, "pitch": 1.15, "pause_after_ms": 250},
    Emotion.WHISPER: {"rate": 0.80, "pitch": 0.95, "pause_after_ms": 350},
    Emotion.SARCASTIC: {"rate": 1.02, "pitch": 1.03, "pause_after_ms": 300},
    Emotion.NEUTRAL: {"rate": 1.00, "pitch": 1.00, "pause_after_ms": 250},
}


class MemoryCache:
    """In-memory LRU cache limited by total bytes."""

    def __init__(self, max_bytes: int = 500 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes
        self.cache: OrderedDict[tuple[str, str, str], bytes] = OrderedDict()
        self.current_bytes = 0

    def get(self, key: tuple[str, str, str]) -> bytes | None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def set(self, key: tuple[str, str, str], value: bytes) -> None:
        if key in self.cache:
            self.current_bytes -= len(self.cache[key])
            del self.cache[key]
        self.cache[key] = value
        self.current_bytes += len(value)
        while self.current_bytes > self.max_bytes and self.cache:
            _, v = self.cache.popitem(last=False)
            self.current_bytes -= len(v)


class TTSProvider(ABC):
    """Abstract base class for TTS synthesis with memory and disk caching."""

    def __init__(self, config: AudioBardConfig) -> None:
        self.config = config
        self.cache_dir = config.cache_dir / "tts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache = MemoryCache()
        import asyncio
        self._semaphore = asyncio.Semaphore(config.tts_semaphore)

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float = 1.0,
        pitch: float = 1.0,
    ) -> bytes:
        """Synthesize *text* using *voice*, *emotion*, and optional custom *rate* and *pitch*.

        Checks memory cache first, then disk cache, and falls back to
        calling the actual provider implementation.
        """
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        mem_key = (text_hash, voice.id, f"{emotion.value}:{rate:.3f}:{pitch:.3f}")

        # 1. Check memory cache
        cached_mem = self._memory_cache.get(mem_key)
        if cached_mem is not None:
            logger.debug("TTS cache hit (memory): %s", text_hash)
            return cached_mem

        # 2. Check disk cache
        disk_hash = hashlib.sha256(
            f"{text}:{voice.id}:{emotion.value}:{rate:.3f}:{pitch:.3f}".encode()
        ).hexdigest()
        disk_file = self.cache_dir / f"{disk_hash}.mp3"
        if disk_file.exists():
            logger.debug("TTS cache hit (disk): %s", disk_file)
            data = disk_file.read_bytes()
            self._memory_cache.set(mem_key, data)
            return data

        # 3. Synthesize via provider (rate-limited)
        logger.info(
            "Synthesizing speech via %s: voice=%s, emotion=%s, rate=%.2f, pitch=%.2f, text_len=%d",
            self.__class__.__name__,
            voice.id,
            emotion.value,
            rate,
            pitch,
            len(text),
        )
        async with self._semaphore:
            data = await self._synthesize_raw(text, voice, emotion, rate, pitch)

        # 4. Write back to caches
        try:
            disk_file.write_bytes(data)
        except OSError as exc:
            logger.warning("Failed to write TTS disk cache: %s", exc)

        self._memory_cache.set(mem_key, data)
        return data

    @abstractmethod
    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        """Internal synthesis call to the actual engine/subprocess."""

    @abstractmethod
    async def list_voices(self, locale: str) -> list[Voice]:
        """Return list of available voices for *locale*."""

