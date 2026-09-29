"""Kokoro-82M ONNX local neural TTS provider.

Kokoro is an 82M parameter, Apache-2.0 licensed speech model that runs on CPU
through ``kokoro-onnx``. Its weights are large, so the model and the voice pack
are downloaded once into the audiobard cache directory and reused afterwards;
pre-downloaded copies can be pinned with ``AUDIOBARD_KOKORO_MODEL`` and
``AUDIOBARD_KOKORO_VOICES``.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from pathlib import Path

import httpx

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.base import EMOTION_PROSODY, TTSProvider

logger = logging.getLogger(__name__)

MODEL_ENV_VAR = "AUDIOBARD_KOKORO_MODEL"
VOICES_ENV_VAR = "AUDIOBARD_KOKORO_VOICES"

MODEL_FILENAME = "kokoro-v1.0.onnx"
VOICES_FILENAME = "voices-v1.0.bin"

MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)

INSTALL_HINT = (
    "kokoro-onnx is not installed. Install it with 'pip install "
    "audiobard[kokoro]' (or 'pip install kokoro-onnx') to use tts_provider=kokoro."
)

# Our locale -> (first letter of the Kokoro voice IDs, ``lang`` argument).
# Kokoro voice IDs encode language then gender: af_sarah is American English
# female, bm_george is British English male.
KOKORO_LOCALES: dict[str, tuple[str, str]] = {
    "en_US": ("a", "en-us"),
    "en_GB": ("b", "en-gb"),
    "es_ES": ("e", "es"),
    "fr_FR": ("f", "fr-fr"),
    "hi_IN": ("h", "hi"),
    "it_IT": ("i", "it"),
    "ja_JP": ("j", "ja"),
    "pt_BR": ("p", "pt-br"),
    "zh_CN": ("z", "zh"),
}

_LOCALE_BY_PREFIX = {prefix: locale for locale, (prefix, _) in KOKORO_LOCALES.items()}

_MIN_SPEED = 0.5
_MAX_SPEED = 2.0


def locale_for_voice(voice_id: str) -> str | None:
    """Return the audiobard locale a Kokoro voice ID belongs to, if known."""
    if not voice_id:
        return None
    return _LOCALE_BY_PREFIX.get(voice_id[0].lower())


def voice_from_id(voice_id: str, locale: str) -> Voice:
    """Build a :class:`Voice` from a Kokoro voice ID such as ``af_sarah``."""
    marker = voice_id[1:2].lower()
    if marker == "f":
        gender = GenderHint.FEMALE
    elif marker == "m":
        gender = GenderHint.MALE
    else:
        gender = GenderHint.NEUTRAL
    return Voice(id=voice_id, locale=locale, gender=gender, age=AgeHint.ADULT)


def read_voice_names(path: Path) -> list[str]:
    """Read the voice names out of a Kokoro voice pack (an ``npz`` archive).

    Reading the pack directly means voices can be listed without importing
    ``kokoro-onnx``; a missing numpy or an unreadable pack only logs a warning.
    """
    if not path.is_file():
        return []

    try:
        import numpy as np
    except ImportError as exc:
        logger.warning("numpy is unavailable; cannot list Kokoro voices: %s", exc)
        return []

    try:
        with np.load(path) as data:
            names = data["voices"]
    except Exception as exc:
        logger.warning("Could not read Kokoro voices from %s: %s", path, exc)
        return []
    return sorted(str(name) for name in names)


def _is_valid_asset(path: Path) -> bool:
    """True when *path* is a present, non-empty file."""
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


async def _download(url: str, destination: Path) -> None:
    """Download *url* to *destination* via a temporary file, then move it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            logger.info("Downloading Kokoro asset from %s", url)
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                total = 0
                with tmp_path.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        handle.write(chunk)
                        total += len(chunk)
                if total == 0:
                    raise ValueError(f"Received empty response from {url}")
        tmp_path.replace(destination)
    finally:
        tmp_path.unlink(missing_ok=True)


def samples_to_mp3(samples: object, sample_rate: int, pitch: float = 1.0) -> bytes:
    """Convert Kokoro's float samples into MP3 bytes.

    ``pitch`` is applied as a frame-rate shift, the same trick the Edge provider
    uses for its prosody cues, so the audiobook stays a single stream.
    """
    import numpy as np
    from pydub import AudioSegment

    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    rate = int(sample_rate) or 24000
    segment = AudioSegment(
        data=pcm.tobytes(), sample_width=2, frame_rate=rate, channels=1
    )
    if pitch and abs(pitch - 1.0) > 0.001:
        shifted = max(rate, int(rate * pitch))
        segment = segment._spawn(segment.raw_data, overrides={"frame_rate": shifted})
        segment = segment.set_frame_rate(rate)

    out = io.BytesIO()
    segment.export(out, format="mp3")
    return out.getvalue()


class KokoroProvider(TTSProvider):
    """Text-to-speech provider using the local Kokoro-82M ONNX model."""

    def __init__(self, config: AudioBardConfig) -> None:
        super().__init__(config)
        self.kokoro_dir = config.cache_dir / "kokoro"
        self.kokoro_dir.mkdir(parents=True, exist_ok=True)
        # Serializes the weight downloads and the one-time session load.
        self._download_lock = asyncio.Lock()
        self._kokoro: object | None = None

    async def available_locales(self) -> dict[str, int]:
        """Locales in the local voice pack, mapped to their voice count.

        Empty until the pack is on disk: the counts must reflect what can really
        be synthesized, and nothing is downloaded just to enumerate locales.
        """
        names = await asyncio.to_thread(read_voice_names, self._voices_path())
        counts: dict[str, int] = {}
        for name in names:
            locale = locale_for_voice(name)
            if locale is None:
                continue
            counts[locale] = counts.get(locale, 0) + 1
        return counts

    async def list_voices(self, locale: str) -> list[Voice]:
        """Voices available for *locale*, downloading the voice pack if needed."""
        if locale not in KOKORO_LOCALES:
            logger.warning(
                "Kokoro has no voices for locale %s (supported: %s)",
                locale,
                ", ".join(sorted(KOKORO_LOCALES)),
            )
            return []

        try:
            await self._ensure_assets()
        except Exception as exc:
            logger.error("Could not prepare Kokoro assets for %s: %s", locale, exc)
            return []

        names = await asyncio.to_thread(read_voice_names, self._voices_path())
        prefix = KOKORO_LOCALES[locale][0]
        return [
            voice_from_id(name, locale)
            for name in names
            if name and name[0].lower() == prefix
        ]

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        model_path, voices_path = await self._ensure_assets()

        names = await asyncio.to_thread(read_voice_names, voices_path)
        if names and voice.id not in names:
            raise ValueError(
                f"Unknown Kokoro voice: {voice.id!r}. Choose one of the "
                f"{len(names)} voices in {voices_path.name} "
                "(for example af_sarah or bm_george)."
            )

        locale = voice.locale if voice.locale in KOKORO_LOCALES else self.config.tts_locale
        lang = KOKORO_LOCALES.get(locale, KOKORO_LOCALES["en_US"])[1]

        emotion_rate = EMOTION_PROSODY.get(emotion, {"rate": 1.0})["rate"]
        speed = max(_MIN_SPEED, min(rate * emotion_rate, _MAX_SPEED))

        samples, sample_rate = await asyncio.to_thread(
            self._infer, model_path, voices_path, text, voice.id, speed, lang
        )
        return await asyncio.to_thread(samples_to_mp3, samples, sample_rate, pitch)

    def _infer(
        self,
        model_path: Path,
        voices_path: Path,
        text: str,
        voice_id: str,
        speed: float,
        lang: str,
    ) -> tuple[object, int]:
        """Run one inference pass. CPU bound, so callers use a worker thread."""
        kokoro = self._session(model_path, voices_path)
        samples, sample_rate = kokoro.create(text, voice=voice_id, speed=speed, lang=lang)
        return samples, int(sample_rate)

    def _session(self, model_path: Path, voices_path: Path) -> object:
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError as exc:
                raise RuntimeError(INSTALL_HINT) from exc
            logger.info("Loading Kokoro model from %s", model_path)
            self._kokoro = Kokoro(str(model_path), str(voices_path))
        return self._kokoro

    def _model_path(self) -> Path:
        override = os.environ.get(MODEL_ENV_VAR)
        if override:
            return Path(override).expanduser()
        return self.kokoro_dir / MODEL_FILENAME

    def _voices_path(self) -> Path:
        override = os.environ.get(VOICES_ENV_VAR)
        if override:
            return Path(override).expanduser()
        return self.kokoro_dir / VOICES_FILENAME

    async def _ensure_assets(self) -> tuple[Path, Path]:
        """Return (model, voices) paths, downloading whichever is missing."""
        model_path = self._model_path()
        voices_path = self._voices_path()
        if _is_valid_asset(model_path) and _is_valid_asset(voices_path):
            return model_path, voices_path

        async with self._download_lock:
            if _is_valid_asset(model_path) and _is_valid_asset(voices_path):
                return model_path, voices_path
            if not _is_valid_asset(model_path):
                await _download(MODEL_URL, model_path)
            if not _is_valid_asset(voices_path):
                await _download(VOICES_URL, voices_path)
        return model_path, voices_path
