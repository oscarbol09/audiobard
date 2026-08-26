"""Piper offline TTS provider."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import shutil
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

    async def list_voices(self, locale: str) -> list[Voice]:
        path = self.config.voices_dir / f"{locale}.json"
        if not path.exists():
            logger.warning("Voice pool file not found: %s", path)
            return []

        def load() -> list[dict[str, object]]:
            import json

            with open(path, encoding="utf-8") as f:
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

    async def _ensure_model(self, voice_id: str) -> Path:
        """Download model and config if they do not exist locally."""
        onnx_path = self.piper_dir / f"{voice_id}.onnx"
        json_path = self.piper_dir / f"{voice_id}.onnx.json"

        if onnx_path.exists() and json_path.exists():
            return onnx_path

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

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Download config (json) first
            logger.info("Downloading Piper config from %s", json_url)
            res = await client.get(json_url, follow_redirects=True)
            res.raise_for_status()
            json_path.write_bytes(res.content)

            # Download model (onnx)
            logger.info("Downloading Piper model from %s", onnx_url)
            res = await client.get(onnx_url, follow_redirects=True)
            res.raise_for_status()
            onnx_path.write_bytes(res.content)

        return onnx_path
