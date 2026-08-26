"""Audio sub-package.

Public surface::

    from audiobard.audio import AudioProcessor, AudioClip, ChapterMarker
"""

from __future__ import annotations

from audiobard.audio.processor import (
    FFMPEG_MISSING_MESSAGE,
    AudioClip,
    AudioProcessor,
    ChapterMarker,
    find_ffmpeg,
)

__all__ = [
    "AudioProcessor",
    "AudioClip",
    "ChapterMarker",
    "FFMPEG_MISSING_MESSAGE",
    "find_ffmpeg",
]
