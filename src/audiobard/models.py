"""Shared Pydantic models used across the pipeline.

These are the contracts that cross module boundaries (parser → LLM → TTS →
audio). They are also the source of truth for the LLM JSON schemas: providers
dump ``model_json_schema()`` into their prompts and validate responses against
them, so a change here is automatically reflected everywhere.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Emotion(str, Enum):
    """Emotional label attached to a dialog line by the LLM."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    WHISPER = "whisper"
    SARCASTIC = "sarcastic"


_EMOTION_SYNONYMS: dict[str, Emotion] = {
    "impatient": Emotion.ANGRY,
    "annoyed": Emotion.ANGRY,
    "irritated": Emotion.ANGRY,
    "furious": Emotion.ANGRY,
    "rage": Emotion.ANGRY,
    "joyful": Emotion.HAPPY,
    "excited": Emotion.HAPPY,
    "cheerful": Emotion.HAPPY,
    "glad": Emotion.HAPPY,
    "amused": Emotion.HAPPY,
    "depressed": Emotion.SAD,
    "grief": Emotion.SAD,
    "sorrow": Emotion.SAD,
    "crying": Emotion.SAD,
    "scared": Emotion.FEARFUL,
    "afraid": Emotion.FEARFUL,
    "nervous": Emotion.FEARFUL,
    "panicked": Emotion.FEARFUL,
    "anxious": Emotion.FEARFUL,
    "shocked": Emotion.SURPRISED,
    "astonished": Emotion.SURPRISED,
    "amazed": Emotion.SURPRISED,
    "confused": Emotion.SURPRISED,
    "quiet": Emotion.WHISPER,
    "soft": Emotion.WHISPER,
    "muffled": Emotion.WHISPER,
    "whispering": Emotion.WHISPER,
    "ironic": Emotion.SARCASTIC,
    "mocking": Emotion.SARCASTIC,
    "cynical": Emotion.SARCASTIC,
    "calm": Emotion.NEUTRAL,
    "serious": Emotion.NEUTRAL,
    "curious": Emotion.NEUTRAL,
    "thoughtful": Emotion.NEUTRAL,
    "normal": Emotion.NEUTRAL,
}


class Tone(str, Enum):
    """Voice-tone hint the LLM assigns to a character."""

    NEUTRAL = "neutral"
    WARM = "warm"
    COLD = "cold"
    AGITATED = "agitated"
    CALM = "calm"
    MYSTERIOUS = "mysterious"
    CHEERFUL = "cheerful"
    MELANCHOLIC = "melancholic"
    AUTHORITATIVE = "authoritative"
    TIMID = "timid"
    SARCASTIC = "sarcastic"


class GenderHint(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class AgeHint(str, Enum):
    CHILD = "child"
    YOUNG = "young"
    ADULT = "adult"
    ELDERLY = "elderly"


class Paragraph(BaseModel):
    """A parsed paragraph with its position in the book."""

    text: str = Field(min_length=1)
    chapter: int = Field(ge=0)
    index: int = Field(ge=0)
    is_dialog: bool = False


class Character(BaseModel):
    """A canonical character extracted by the LLM."""

    canonical_id: str = Field(pattern=r"^(Narrator|Character_[A-Z])$")
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    tone: Tone = Tone.NEUTRAL
    gender_hint: GenderHint = GenderHint.NEUTRAL
    age_hint: AgeHint = AgeHint.ADULT

    @field_validator("tone", mode="before")
    @classmethod
    def normalize_tone(cls, v: Any) -> Tone:
        if isinstance(v, Tone):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            try:
                return Tone(val)
            except ValueError:
                return Tone.NEUTRAL
        return Tone.NEUTRAL

    @field_validator("gender_hint", mode="before")
    @classmethod
    def normalize_gender(cls, v: Any) -> GenderHint:
        if isinstance(v, GenderHint):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            try:
                return GenderHint(val)
            except ValueError:
                return GenderHint.NEUTRAL
        return GenderHint.NEUTRAL

    @field_validator("age_hint", mode="before")
    @classmethod
    def normalize_age(cls, v: Any) -> AgeHint:
        if isinstance(v, AgeHint):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            try:
                return AgeHint(val)
            except ValueError:
                return AgeHint.ADULT
        return AgeHint.ADULT


class CharactersResult(BaseModel):
    """Response contract of the character-extraction LLM call."""

    characters: list[Character]


class DialogLine(BaseModel):
    """One attributed line of dialog."""

    text: str = Field(min_length=1)
    speaker: str = Field(pattern=r"^(Narrator|Character_[A-Z])$")
    emotion: Emotion = Emotion.NEUTRAL

    @field_validator("speaker", mode="before")
    @classmethod
    def normalize_speaker(cls, v: Any) -> str:
        if isinstance(v, str):
            v_clean = v.strip()
            if v_clean.lower() == "narrator":
                return "Narrator"
            m = re.match(r"^[Cc]haracter_?([A-Za-z0-9])$", v_clean)
            if m:
                char_suffix = m.group(1).upper()
                if char_suffix.isdigit():
                    idx = int(char_suffix)
                    char_suffix = chr(ord("A") + min(idx, 25))
                return f"Character_{char_suffix}"
            return v_clean
        return "Narrator"

    @field_validator("emotion", mode="before")
    @classmethod
    def normalize_emotion(cls, v: Any) -> Emotion:
        if isinstance(v, Emotion):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            try:
                return Emotion(val)
            except ValueError:
                return _EMOTION_SYNONYMS.get(val, Emotion.NEUTRAL)
        return Emotion.NEUTRAL


class AttributionResult(BaseModel):
    """Response contract of the dialog-attribution LLM call."""

    lines: list[DialogLine]


class Voice(BaseModel):
    """A TTS voice with the metadata the voice mapper filters on."""

    id: str
    locale: str
    gender: GenderHint
    age: AgeHint
    energy: float = Field(default=0.5, ge=0.0, le=1.0)


class VoiceAssignment(BaseModel):
    """A voice bound to a canonical speaker."""

    canonical_id: str = Field(pattern=r"^(Narrator|Character_[A-Z])$")
    voice_id: str
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
