"""Piper offline TTS provider."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import shutil
import uuid
from pathlib import Path

import httpx
from pydub import AudioSegment

from audiobard.config import AudioBardConfig
from audiobard.models import Emotion, Voice
from audiobard.tts.base import EMOTION_PROSODY, TTSProvider

logger = logging.getLogger(__name__)


def _wav_to_mp3(wav_data: bytes) -> bytes:
    """Convert raw WAV bytes to MP3 bytes using pydub."""
    segment = AudioSegment.from_wav(io.BytesIO(wav_data))
    out = io.BytesIO()
    segment.export(out, format="mp3")
    return out.getvalue()


class PiperProvider(TTSProvider):
    """Text-to-speech provider using Piper local CLI subprocess."""

    def __init__(self, config: AudioBardConfig) -> None:
        super().__init__(config)
        self.piper_dir = config.cache_dir / "piper"
        self.piper_dir.mkdir(parents=True, exist_ok=True)
        # Serializes model downloads so concurrent synthesizers cannot
        # race-write the same .onnx / .onnx.json paths.
        self._download_lock = asyncio.Lock()

    async def list_voices(self, locale: str) -> list[Voice]:
        path = self.config.voices_dir / f"{locale}.json"
        if not path.exists():
            logger.warning("Voice pool file not found: %s", path)
            return []

        def load() -> list[dict[str, object]]:
            import json

            with open(path, encoding="utf-8-sig") as f:
                res = json.load(f)
                if isinstance(res, list):
                    return res
                return []

        try:
            data = await asyncio.to_thread(load)
            return [Voice.model_validate(v) for v in data]
        except Exception as exc:
            logger.error("Failed to load voices from %s: %s", path, exc)
            return []

    async def _synthesize_raw(
        self,
        text: str,
        voice: Voice,
        emotion: Emotion,
        rate: float,
        pitch: float,
    ) -> bytes:
        # 1. Locate piper binary
        piper_bin = shutil.which("piper")
        if not piper_bin:
            raise FileNotFoundError(
                "piper executable not found on PATH. Please make sure Piper is installed."
            )

        # 2. Ensure model files exist (download if missing)
        model_path = await self._ensure_model(voice.id)

        # 3. Calculate length scale (reciprocal of rate)
        emotion_rate = EMOTION_PROSODY.get(emotion, {"rate": 1.0})["rate"]
        final_rate = rate * emotion_rate
        # Clamp rate to avoid extreme values causing division by zero or errors
        final_rate = max(0.5, min(final_rate, 2.0))
        length_scale = 1.0 / final_rate

        # 4. Invoke subprocess
        cmd = [
            piper_bin,
            "--model",
            str(model_path),
            "--output_file",
            "-",
            "--length_scale",
            f"{length_scale:.3f}",
        ]

        logger.debug("Running command: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate(text.encode("utf-8"))

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Piper process exited with code {proc.returncode}: {err_msg}"
            )

        # 5. Convert WAV to MP3 in worker thread
        return await asyncio.to_thread(_wav_to_mp3, stdout)

    @staticmethod
    def _is_valid_cache(onnx_path: Path, json_path: Path) -> bool:
        """Check if both model and metadata files exist with non-zero size."""
        try:
            return (
                onnx_path.is_file()
                and json_path.is_file()
                and onnx_path.stat().st_size > 0
                and json_path.stat().st_size > 0
            )
        except OSError:
            return False

    async def _ensure_model(self, voice_id: str) -> Path:
        """Download model and config if they do not exist locally.

        Concurrent callers for the same (or different) missing voices are
        serialized via ``_download_lock``. Existence is re-checked under the
        lock so only the first waiter performs the download.
        """
        onnx_path = self.piper_dir / f"{voice_id}.onnx"
        json_path = self.piper_dir / f"{voice_id}.onnx.json"

        # Fast path: already cached with valid content.
        if self._is_valid_cache(onnx_path, json_path):
            return onnx_path

        async with self._download_lock:
            # Re-check after acquiring the lock in case another task finished downloading.
            if self._is_valid_cache(onnx_path, json_path):
                return onnx_path

            # Clean up corrupted or zero-byte files from prior aborted downloads.
            for path in (onnx_path, json_path):
                try:
                    if path.exists() and path.stat().st_size == 0:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass

            regex = r"^([a-z]{2,3}_[A-Z]{2,3})-([a-zA-Z0-9_]+)-(x_low|low|medium|high)$"
            match = re.match(regex, voice_id)
            if not match:
                raise ValueError(
                    f"Invalid Piper voice ID format: {voice_id}. "
                    "Expected format: locale-name-quality (e.g. en_US-amy-medium)"
                )

            locale, name, quality = match.groups()
            lang_prefix = locale.split("_")[0]

            base_url = (
                f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
                f"{lang_prefix}/{locale}/{name}/{quality}/{voice_id}"
            )

            onnx_url = f"{base_url}.onnx"
            json_url = f"{base_url}.onnx.json"

            unique_id = uuid.uuid4().hex
            tmp_json_path = self.piper_dir / f"{voice_id}.{unique_id}.onnx.json.tmp"
            tmp_onnx_path = self.piper_dir / f"{voice_id}.{unique_id}.onnx.tmp"

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    logger.info("Downloading Piper config from %s", json_url)
                    res = await client.get(json_url, follow_redirects=True)
                    res.raise_for_status()
                    if not res.content:
                        raise ValueError(f"Received empty response from {json_url}")
                    tmp_json_path.write_bytes(res.content)

                    logger.info("Downloading Piper model from %s", onnx_url)
                    async with client.stream("GET", onnx_url, follow_redirects=True) as stream_res:
                        stream_res.raise_for_status()
                        total_bytes = 0
                        with tmp_onnx_path.open("wb") as f:
                            async for chunk in stream_res.aiter_bytes():
                                f.write(chunk)
                                total_bytes += len(chunk)
                        if total_bytes == 0:
                            raise ValueError(f"Received empty response from {onnx_url}")

                tmp_json_path.replace(json_path)
                tmp_onnx_path.replace(onnx_path)
            finally:
                tmp_json_path.unlink(missing_ok=True)
                tmp_onnx_path.unlink(missing_ok=True)

            return onnx_path

