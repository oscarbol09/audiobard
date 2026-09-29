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

from audiobard.models import BookMetadata, Emotion
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


def _escape_ffmetadata(value: str) -> str:
    """Escape metadata delimiters and line breaks, starting with backslashes."""
    for char in ("\\", "=", ";", "#", "\r", "\n"):
        value = value.replace(char, f"\\{char}")
    return value


def generate_ffmetadata(chapters: list[ChapterMarker]) -> str:
    """Generate FFMETADATA1 chapter markers with escaped, literal title values."""
    lines = [";FFMETADATA1"]
    for ch in chapters:
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={ch.start_ms}",
                f"END={ch.end_ms}",
                f"title={_escape_ffmetadata(ch.title)}",
                "",
            ]
        )
    return "\n".join(lines)


_COVER_SUFFIX_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


def _write_cover_file(directory: Path, metadata: BookMetadata | None) -> Path | None:
    """Write the cover image into *directory* for FFmpeg to attach, if any."""
    if metadata is None or not metadata.cover_bytes:
        return None
    suffix = _COVER_SUFFIX_BY_MIME.get((metadata.cover_mime or "").lower(), ".jpg")
    cover_path = directory / f"cover{suffix}"
    cover_path.write_bytes(metadata.cover_bytes)
    return cover_path


def _embed_mp3_tags(path: Path, metadata: BookMetadata) -> None:
    """Best-effort ID3v2 embedding of title, author, and cover art.

    Tagging never fails an otherwise successful export: an untaggable or
    unexpected file only logs a warning.
    """
    try:
        from mutagen.id3 import APIC, ID3, TIT2, TPE1
        from mutagen.mp3 import MP3
    except ImportError as exc:  # pragma: no cover - mutagen is a dependency
        logger.warning("mutagen is unavailable; skipping MP3 tags: %s", exc)
        return

    try:
        audio = MP3(str(path), ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        if tags is None:  # pragma: no cover - add_tags() always installs ID3
            return
        if metadata.title:
            tags.add(TIT2(encoding=3, text=metadata.title))
        if metadata.author:
            tags.add(TPE1(encoding=3, text=metadata.author))
        if metadata.cover_bytes:
            tags.add(
                APIC(
                    encoding=3,
                    mime=metadata.cover_mime or "image/jpeg",
                    type=3,
                    desc="Cover",
                    data=metadata.cover_bytes,
                )
            )
        audio.save()
    except Exception as exc:
        logger.warning("Could not embed MP3 tags in %s: %s", path, exc)


class AudioProcessor:
    """Handles audio concatenation, normalization, and export to formats."""

    def __init__(self, target_dbfs: float = -16.0) -> None:
        self.target_dbfs = target_dbfs

    async def concatenate(self, clips: list[AudioClip]) -> bytes:
        """Concatenate clips, insert emotion-based silence gaps, and normalize to target dBFS."""
        return await asyncio.to_thread(self._concatenate_sync, clips)

    def _concatenate_sync(self, clips: list[AudioClip]) -> bytes:
        if not clips:
            return b""

        segments: list[AudioSegment] = []
        for clip in clips:
            segment = AudioSegment.from_file(io.BytesIO(clip.mp3_bytes), format="mp3")
            segments.append(segment)

            # Add silence gap after the clip based on its emotion
            pause_ms = EMOTION_PROSODY.get(clip.emotion, {"pause_after_ms": 250})[
                "pause_after_ms"
            ]
            if pause_ms > 0:
                silence = AudioSegment.silent(
                    duration=pause_ms,
                    frame_rate=segment.frame_rate,
                )
                if segment.channels != 1:
                    silence = silence.set_channels(segment.channels)
                if segment.sample_width != silence.sample_width:
                    silence = silence.set_sample_width(segment.sample_width)
                segments.append(silence)

        if not segments:
            return b""

        # Linear O(N) concatenation: synchronize audio properties across segments once,
        # then join underlying PCM byte buffers in a single pass to avoid O(N^2) reallocation.
        synced = AudioSegment._sync(*segments)
        raw_data = b"".join(s.raw_data for s in synced)
        combined = synced[0]._spawn(raw_data)

        # Normalize volume to target dBFS (default -16 dBFS approx -16 LUFS for speech)
        if combined.dBFS != float("-inf"):
            gain_change = self.target_dbfs - combined.dBFS
            combined = combined.apply_gain(gain_change)

        out = io.BytesIO()
        combined.export(out, format="mp3")
        return out.getvalue()

    async def export_mp3(
        self,
        audio_bytes: bytes,
        path: Path,
        metadata: BookMetadata | None = None,
    ) -> None:
        """Export raw MP3 bytes to *path*, embedding *metadata* tags if given."""

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio_bytes)

        await asyncio.to_thread(write)

        if metadata is not None and metadata.has_tags():
            await asyncio.to_thread(_embed_mp3_tags, path, metadata)

    async def export_m4b(
        self,
        audio_bytes: bytes,
        path: Path,
        chapters: list[ChapterMarker],
        metadata: BookMetadata | None = None,
    ) -> None:
        """Convert MP3 bytes to AAC/M4B and inject chapters and metadata via FFmpeg."""
        ffmpeg_bin = find_ffmpeg()
        if not ffmpeg_bin:
            raise FileNotFoundError(FFMPEG_MISSING_MESSAGE)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_m4b = tmp_path / "raw.m4b"
            metadata_file = tmp_path / "metadata.txt"
            cover_file = _write_cover_file(tmp_path, metadata)

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
            metadata_file.write_text(metadata_content, encoding="utf-8", newline="\n")

            # 3. Inject metadata into final M4B file
            logger.info("Injecting chapter markers into final M4B...")
            path.parent.mkdir(parents=True, exist_ok=True)
            attach_args: list[str] = []
            if cover_file is not None:
                attach_args = [
                    "-i",
                    str(cover_file),
                    "-map",
                    "0:a",
                    "-map",
                    "2:v",
                    "-disposition:v",
                    "attached_pic",
                    "-c:v",
                    "copy",
                ]

            tag_args: list[str] = []
            if metadata is not None and metadata.title:
                tag_args += ["-metadata", f"title={metadata.title}"]
            if metadata is not None and metadata.author:
                tag_args += ["-metadata", f"artist={metadata.author}"]

            proc2 = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-i",
                str(raw_m4b),
                "-i",
                str(metadata_file),
                *attach_args,
                "-map_metadata",
                "1",
                *tag_args,
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
