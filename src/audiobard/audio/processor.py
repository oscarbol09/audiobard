"""Audio processor for concatenating clips, normalizing volume, and exporting formats."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field
from pydub import AudioSegment

from audiobard.models import Emotion
from audiobard.tts.base import EMOTION_PROSODY

logger = logging.getLogger(__name__)

FFMPEG_MISSING_MESSAGE = (
    "FFmpeg is required for M4B/chapter support. "
    "Please install FFmpeg or select MP3 output."
)

_FFMPEG_ENV_VARS = ("AUDIOBARD_FFMPEG", "FFMPEG_BINARY", "FFMPEG_PATH")
_FFMPEG_TOOL_SUBDIRS = (
    Path("tools"),
    Path("tools") / "bin",
    Path("tools") / "ffmpeg",
    Path("bin"),
)


def find_ffmpeg() -> str | None:
    """Locate an ``ffmpeg`` binary for M4B export.

    Search order:
    1. ``AUDIOBARD_FFMPEG`` / ``FFMPEG_BINARY`` / ``FFMPEG_PATH`` env vars
    2. System ``PATH`` via ``shutil.which``
    3. Bundled binary from optional ``imageio_ffmpeg`` package
    4. Local ``tools/`` (and ``bin/``) directories under cwd and the repo root
    """
    import shutil

    for env_name in _FFMPEG_ENV_VARS:
        raw = os.environ.get(env_name)
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())

    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]
    except ImportError:
        imageio_ffmpeg = None
    if imageio_ffmpeg is not None:
        try:
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
        except (OSError, RuntimeError) as exc:
            logger.debug("imageio_ffmpeg lookup failed: %s", exc)
        else:
            if bundled and Path(bundled).is_file():
                return str(Path(bundled).resolve())

    names = ("ffmpeg.exe", "ffmpeg") if sys.platform == "win32" else ("ffmpeg",)
    roots: list[Path] = [Path.cwd()]
    # processor.py -> audio -> audiobard -> src -> repo root (editable installs)
    here = Path(__file__).resolve()
    for idx in (2, 3, 4):
        if idx < len(here.parents):
            roots.append(here.parents[idx])

    seen: set[str] = set()
    for root in roots:
        for sub in _FFMPEG_TOOL_SUBDIRS:
            for name in names:
                candidate = (root / sub / name).resolve()
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if candidate.is_file():
                    return key
    return None


class AudioClip(BaseModel):
    """An individual audio clip synthesized by the TTS engine."""

    mp3_bytes: bytes
    speaker: str
    emotion: Emotion
    duration_ms: int


class ChapterMarker(BaseModel):
    """Marker indicating chapter boundaries in the final audiobook file."""

    title: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


def generate_ffmetadata(chapters: list[ChapterMarker]) -> str:
    """Generate FFmpeg FFMETADATA1 content for chapter markers."""
    lines = [";FFMETADATA1"]
    for ch in chapters:
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={ch.start_ms}",
                f"END={ch.end_ms}",
                f"title={ch.title}",
                "",
            ]
        )
    return "\n".join(lines)


class AudioProcessor:
    """Handles audio concatenation, normalization, and export to formats."""

    async def concatenate(self, clips: list[AudioClip]) -> bytes:
        """Concatenate clips, insert emotion-based silence gaps, and normalize to -16 dBFS."""
        return await asyncio.to_thread(self._concatenate_sync, clips)

    def _concatenate_sync(self, clips: list[AudioClip]) -> bytes:
        if not clips:
            return b""

        combined = AudioSegment.empty()
        for clip in clips:
            segment = AudioSegment.from_file(io.BytesIO(clip.mp3_bytes), format="mp3")
            combined += segment

            # Add silence gap after the clip based on its emotion
            pause_ms = EMOTION_PROSODY.get(clip.emotion, {"pause_after_ms": 250})[
                "pause_after_ms"
            ]
            combined += AudioSegment.silent(duration=pause_ms)

        # Normalize volume to -16 dBFS (approx -16 LUFS for speech)
        if combined.dBFS != float("-inf"):
            gain_change = -16.0 - combined.dBFS
            combined = combined.apply_gain(gain_change)

        out = io.BytesIO()
        combined.export(out, format="mp3")
        return out.getvalue()

    async def export_mp3(self, audio_bytes: bytes, path: Path) -> None:
        """Export raw MP3 bytes to *path*."""

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio_bytes)

        await asyncio.to_thread(write)

    async def export_m4b(
        self,
        audio_bytes: bytes,
        path: Path,
        chapters: list[ChapterMarker],
    ) -> None:
        """Convert MP3 bytes to AAC/M4B and inject chapter markers via FFmpeg."""
        ffmpeg_bin = find_ffmpeg()
        if not ffmpeg_bin:
            raise FileNotFoundError(FFMPEG_MISSING_MESSAGE)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_m4b = tmp_path / "raw.m4b"
            metadata_file = tmp_path / "metadata.txt"

            # 1. Convert MP3 to AAC/M4B (64k bitrate is optimal for voice audiobooks)
            logger.info("Converting MP3 to raw M4B audio...")
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-i",
                "pipe:0",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-y",
                str(raw_m4b),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(audio_bytes)
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"FFmpeg raw M4B export failed: {err}")

            # 2. Write metadata file
            metadata_content = generate_ffmetadata(chapters)
            metadata_file.write_text(metadata_content, encoding="utf-8")

            # 3. Inject metadata into final M4B file
            logger.info("Injecting chapter markers into final M4B...")
            path.parent.mkdir(parents=True, exist_ok=True)
            proc2 = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-i",
                str(raw_m4b),
                "-i",
                str(metadata_file),
                "-map_metadata",
                "1",
                "-codec",
                "copy",
                "-y",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr2 = await proc2.communicate()
            if proc2.returncode != 0:
                err = stderr2.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"FFmpeg chapter injection failed: {err}")
