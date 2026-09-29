"""Audio processor for concatenating clips, normalizing volume, and exporting formats."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
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
    """An individual audio clip synthesized by the TTS engine.

    A clip carries either its encoded bytes or, for clips already cached on
    disk, the path to that file. Concatenation accepts both, so a long book
    can be assembled without holding every clip in memory at the same time.
    """

    mp3_bytes: bytes = b""
    speaker: str
    emotion: Emotion
    duration_ms: int
    path: Path | None = None

    @model_validator(mode="after")
    def _require_audio_source(self) -> AudioClip:
        if not self.mp3_bytes and self.path is None:
            raise ValueError("AudioClip needs mp3_bytes or path")
        return self


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
        audio = MP3(str(path), ID3=ID3)  # type: ignore[no-untyped-call]
        if audio.tags is None:
            audio.add_tags()  # type: ignore[no-untyped-call]
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


_STREAM_DEFAULT_RATE = 24000
_STREAM_DEFAULT_CHANNELS = 1
_STREAM_MAX_CHANNELS = 2

_ASTATS_OVERALL_RMS = re.compile(r"RMS level dB:\s*(-?inf|[-\d.]+)")
_VOLUMEDETECT_MEAN = re.compile(r"mean_volume:\s*(-?inf|[-\d.]+) dB")


def _escape_concat_path(path: Path) -> str:
    """Quote a path for an FFmpeg concat demuxer list file."""
    posix = Path(path).resolve().as_posix()
    return posix.replace("'", "'\\''")


def _clip_stream_format(clip: AudioClip) -> tuple[int, int] | None:
    """Read a clip's sample rate and channel count from its header, undecoded."""
    try:
        from mutagen.mp3 import MP3
    except ImportError:  # pragma: no cover - mutagen is a dependency
        return None

    try:
        if clip.path is not None and clip.path.is_file():
            info = MP3(str(clip.path)).info  # type: ignore[no-untyped-call]
        else:
            info = MP3(io.BytesIO(clip.mp3_bytes)).info  # type: ignore[no-untyped-call]
    except Exception:
        return None

    rate = int(getattr(info, "sample_rate", 0) or 0)
    channels = int(getattr(info, "channels", 0) or 0)
    if rate <= 0 or channels <= 0:
        return None
    return rate, channels


def _stream_target_format(clips: list[AudioClip]) -> tuple[int, int]:
    """Pick the shared format the way ``AudioSegment._sync`` does: the maxima."""
    formats = [fmt for clip in clips if (fmt := _clip_stream_format(clip)) is not None]
    rate = max((fmt[0] for fmt in formats), default=_STREAM_DEFAULT_RATE)
    channels = max((fmt[1] for fmt in formats), default=_STREAM_DEFAULT_CHANNELS)
    return rate, min(channels, _STREAM_MAX_CHANNELS)


def _parse_loudness(stderr: str) -> float | None:
    """Overall level of a measurement run in dBFS, or None for digital silence."""
    overall = stderr.rsplit("Overall", 1)[-1]
    match = _ASTATS_OVERALL_RMS.search(overall) or _VOLUMEDETECT_MEAN.search(stderr)
    if match is None:
        return None
    token = match.group(1)
    if "inf" in token:
        return None
    return float(token)


def _measure_loudness(
    ffmpeg_bin: str, list_file: Path, rate: int, channels: int
) -> float | None:
    """Measure the concatenation's level in one bounded-memory FFmpeg pass."""
    args = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-ar",
        str(rate),
        "-ac",
        str(channels),
        "-af",
        "astats=measure_overall=RMS_level",
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(args, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg loudness measurement failed: {stderr}")
    return _parse_loudness(completed.stderr.decode("utf-8", errors="replace"))


def _write_silence(
    ffmpeg_bin: str, path: Path, pause_ms: int, rate: int, channels: int
) -> None:
    """Render a *pause_ms* long silent MP3 with FFmpeg."""
    layout = "stereo" if channels > 1 else "mono"
    args = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={rate}:cl={layout}",
        "-t",
        f"{pause_ms / 1000:.3f}",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "9",
        str(path),
    ]
    completed = subprocess.run(args, capture_output=True, check=False)
    if completed.returncode != 0 or not path.exists():
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg silence generation failed: {stderr}")


def _materialize_clip(clip: AudioClip, workdir: Path, index: int) -> Path:
    """Return the file FFmpeg should read, writing bytes out only when needed."""
    if clip.path is not None and clip.path.is_file():
        return clip.path
    clip_path = workdir / f"clip_{index:06d}.mp3"
    clip_path.write_bytes(clip.mp3_bytes)
    return clip_path


class AudioProcessor:
    """Handles audio concatenation, normalization, and export to formats."""

    def __init__(self, target_dbfs: float = -16.0) -> None:
        self.target_dbfs = target_dbfs

    async def concatenate(self, clips: list[AudioClip]) -> bytes:
        """Concatenate clips, insert emotion-based silence gaps, and normalize to target dBFS.

        The join happens inside FFmpeg, so no uncompressed PCM is ever built in
        Python and memory no longer grows with the length of the book.
        """
        return await asyncio.to_thread(self._concatenate_sync, clips)

    async def concatenate_to_file(self, clips: list[AudioClip], path: Path) -> None:
        """Stream the normalized concatenation straight into *path*.

        Same audio as :meth:`concatenate`, but the finished file is written by
        FFmpeg, so assembling a book no longer holds the clips, the PCM, and the
        encoded result in memory at once. The write is staged next to *path* and
        moved into place, so a locked destination still raises ``PermissionError``
        and a failed run never leaves a partial file behind.
        """
        await asyncio.to_thread(self._concatenate_to_path_sync, clips, path)

    def _concatenate_to_path_sync(self, clips: list[AudioClip], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = path.with_name(f"{path.name}.part")
        try:
            ffmpeg_bin = find_ffmpeg()
            streamed = False
            if ffmpeg_bin:
                try:
                    self._stream_concatenate(ffmpeg_bin, clips, staging)
                    streamed = True
                except Exception as exc:
                    logger.warning(
                        "Streaming concatenation failed (%s); using the in-memory join",
                        exc,
                    )
            if not streamed:
                staging.write_bytes(self._concatenate_in_memory(clips))
            staging.replace(path)
        finally:
            staging.unlink(missing_ok=True)

    def _stream_concatenate(
        self, ffmpeg_bin: str, clips: list[AudioClip], destination: Path
    ) -> None:
        """Join *clips* into *destination* through the FFmpeg concat demuxer."""
        if not clips:
            destination.write_bytes(b"")
            return

        rate, channels = _stream_target_format(clips)
        with tempfile.TemporaryDirectory(prefix="audiobard-concat-") as tmpdir:
            workdir = Path(tmpdir)
            entries: list[Path] = []
            silences: dict[int, Path] = {}
            for index, clip in enumerate(clips):
                entries.append(_materialize_clip(clip, workdir, index))
                prosody = EMOTION_PROSODY.get(clip.emotion, {"pause_after_ms": 250})
                pause_ms = int(prosody.get("pause_after_ms") or 0)
                if pause_ms <= 0:
                    continue
                silence = silences.get(pause_ms)
                if silence is None:
                    silence = workdir / f"silence_{pause_ms}.mp3"
                    _write_silence(ffmpeg_bin, silence, pause_ms, rate, channels)
                    silences[pause_ms] = silence
                entries.append(silence)

            list_file = workdir / "clips.txt"
            list_file.write_text(
                "".join(f"file '{_escape_concat_path(entry)}'\n" for entry in entries),
                encoding="utf-8",
                newline="\n",
            )

            loudness = _measure_loudness(ffmpeg_bin, list_file, rate, channels)
            gain_db = None if loudness is None else self.target_dbfs - loudness
            self._encode_concat(
                ffmpeg_bin, list_file, rate, channels, gain_db, destination
            )

    def _encode_concat(
        self,
        ffmpeg_bin: str,
        list_file: Path,
        rate: int,
        channels: int,
        gain_db: float | None,
        destination: Path,
    ) -> None:
        args = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-ar",
            str(rate),
            "-ac",
            str(channels),
        ]
        if gain_db is not None:
            args += ["-af", f"volume={gain_db:.2f}dB"]
        args += ["-f", "mp3", "-c:a", "libmp3lame", "-q:a", "2", str(destination)]
        completed = subprocess.run(args, capture_output=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"FFmpeg concatenation failed: {stderr}")

    def _concatenate_sync(self, clips: list[AudioClip]) -> bytes:
        """Stream the clips through FFmpeg, falling back to the in-memory join."""
        if not clips:
            return b""

        ffmpeg_bin = find_ffmpeg()
        if ffmpeg_bin:
            try:
                with tempfile.TemporaryDirectory(prefix="audiobard-concat-") as tmpdir:
                    streamed = Path(tmpdir) / "combined.mp3"
                    self._stream_concatenate(ffmpeg_bin, clips, streamed)
                    return streamed.read_bytes()
            except Exception as exc:
                logger.warning(
                    "Streaming concatenation failed (%s); using the in-memory join", exc
                )
        return self._concatenate_in_memory(clips)

    def _concatenate_in_memory(self, clips: list[AudioClip]) -> bytes:
        """Legacy join: decode every clip to PCM, then re-encode once.

        Kept as the fallback for hosts without FFmpeg; memory scales with the
        book, so the streaming path above is preferred whenever FFmpeg exists.
        """
        if not clips:
            return b""

        segments: list[AudioSegment] = []
        for clip in clips:
            if clip.path is not None and clip.path.is_file():
                segment = AudioSegment.from_file(str(clip.path), format="mp3")
            else:
                segment = AudioSegment.from_file(
                    io.BytesIO(clip.mp3_bytes), format="mp3"
                )
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
        await self.apply_mp3_tags(path, metadata)

    async def apply_mp3_tags(self, path: Path, metadata: BookMetadata | None) -> None:
        """Embed *metadata* into an already written MP3 file, when it has tags."""
        if metadata is None or not metadata.has_tags():
            return
        await asyncio.to_thread(_embed_mp3_tags, path, metadata)

    async def export_m4b(
        self,
        audio_bytes: bytes,
        path: Path,
        chapters: list[ChapterMarker],
        metadata: BookMetadata | None = None,
        audio_path: Path | None = None,
    ) -> None:
        """Convert MP3 bytes (or the MP3 file at *audio_path*) to AAC/M4B via FFmpeg."""
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
            source_args = ["-i", str(audio_path)] if audio_path else ["-i", "pipe:0"]
            payload = None if audio_path else audio_bytes
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                *source_args,
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
            _, stderr = await proc.communicate(payload)
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
