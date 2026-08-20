"""TTS sub-package.

Public surface::

    from audiobard.tts import VoiceMapper, TTSProvider, PiperProvider, EdgeProvider, EMOTION_PROSODY
"""

from __future__ import annotations

from audiobard.tts.base import EMOTION_PROSODY, TTSProvider
from audiobard.tts.edge_provider import EdgeProvider
from audiobard.tts.piper_provider import PiperProvider
from audiobard.tts.voice_mapper import VoiceMapper

__all__ = [
    "VoiceMapper",
    "TTSProvider",
    "PiperProvider",
    "EdgeProvider",
    "EMOTION_PROSODY",
]
