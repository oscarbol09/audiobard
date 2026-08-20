"""Audio sub-package.

Public surface::

    from audiobard.audio import AudioProcessor, AudioClip, ChapterMarker
"""

from __future__ import annotations

from audiobard.audio.processor import AudioClip, AudioProcessor, ChapterMarker

__all__ = [
    "AudioProcessor",
    "AudioClip",
    "ChapterMarker",
]
