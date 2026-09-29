"""Edge-TTS cloud provider (opt-in)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import edge_tts

from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.base import EMOTION_PROSODY, TTSProvider

logger = logging.getLogger(__name__)

# Bundled snapshot of Microsoft voice metadata, used when the live service is
# unreachable so the voice picker still populates on an offline desktop launch.
_BUNDLED_VOICES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "edge_voices_cache.json"
)


def _offline_fallback_errors() -> tuple[type[BaseException], ...]:
    """Exception types that mean the network is unavailable, not that we are broken."""
    errors: list[type[BaseException]] = [
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
        OSError,
    ]
    try:
        import aiohttp
    except ImportError:  # pragma: no cover - aiohttp ships with edge-tts
        pass
    else:
        errors.append(aiohttp.ClientError)
    return tuple(errors)


def _load_bundled_voices() -> list[dict[str, str]]:
    """Load the bundled offline voice snapshot; empty list when unreadable."""
    try:
        payload = json.loads(_BUNDLED_VOICES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Bundled Edge voice cache is unavailable: %s", exc)
        return []
    raw = payload.get("voices") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    return [
        {
            "ShortName": str(entry.get("ShortName", "")),
            "Locale": str(entry.get("Locale", "")),
            "Gender": str(entry.get("Gender", "")),
        }
        for entry in raw
        if isinstance(entry, dict) and entry.get("ShortName")
    ]


class EdgeProvider(TTSProvider):
    """Text-to-speech provider using Microsoft Edge Online TTS."""

    async def list_voices(self, locale: str) -> list[Voice]:
        """List available voices from Edge TTS for the given *locale*."""
        edge_locale = locale.replace("_", "-")
        try:
            all_voices = await edge_tts.list_voices()
        except _offline_fallback_errors() as exc:
            logger.warning(
                "Edge TTS is unreachable (%s); using the bundled offline voice snapshot.",
                exc,
            )
            all_voices = _load_bundled_voices()
        except Exception as exc:
            logger.error("Failed to fetch voices from Edge TTS: %s", exc)
            return []

        voices = []
        for v in all_voices:
            if v.get("Locale", "").lower() == edge_locale.lower():
                gender = GenderHint.NEUTRAL
                g_str = v.get("Gender", "").lower()
                if g_str == "male":
                    gender = GenderHint.MALE
                elif g_str == "female":
                    gender = GenderHint.FEMALE

                voices.append(
                    Voice(
                        id=v.get("ShortName", ""),
                        locale=locale,
                        gender=gender,
                        age=AgeHint.ADULT,  # Default since Edge-TTS doesn't metadata-tag age
                        energy=0.5,
                    )
                )
        return voices

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        """Synthesize raw MP3 bytes using edge_tts Communicate."""
        # Calculate rates/pitches based on baseline and emotion prosody
        emotion_prosody = EMOTION_PROSODY.get(emotion, {"rate": 1.0, "pitch": 1.0})
        final_rate = rate * emotion_prosody["rate"]
        final_pitch = pitch * emotion_prosody["pitch"]

        # edge-tts expects rate as an integer percentage shift string,
        # e.g., "+10%", "-15%", or "+0%"
        rate_pct = round((final_rate - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"

        # edge-tts expects pitch in Hz, e.g. "+5Hz" or "-10Hz"
        pitch_hz = round((final_pitch - 1.0) * 100)
        pitch_str = f"{pitch_hz:+d}Hz"

        logger.debug(
            "Edge TTS synthesis: voice=%s, rate=%s, pitch=%s",
            voice.id,
            rate_str,
            pitch_str,
        )

        import edge_tts.exceptions

        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice.id,
                    rate=rate_str,
                    pitch=pitch_str,
                )

                data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        data += chunk["data"]

                if not data:
                    raise RuntimeError(
                        f"Edge TTS returned no audio data for voice: {voice.id}"
                    )
                return data

            except edge_tts.exceptions.NoAudioReceived as exc:
                logger.warning(
                    "Edge TTS returned no audio on attempt %d: %s",
                    attempt + 1, exc
                )
                if attempt == 2:
                    raise RuntimeError(
                        f"Edge TTS failed completely for voice '{voice.id}'. "
                        "Text might contain invalid characters or Microsoft "
                        "is blocking the request."
                    ) from exc
                await asyncio.sleep(2 ** attempt)
            except Exception as exc:
                logger.warning(
                    "Edge TTS connection error on attempt %d: %s",
                    attempt + 1, exc
                )
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Edge TTS failed after retries.")
