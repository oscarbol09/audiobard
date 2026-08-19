"""Shared Pydantic models used across the pipeline.

These are the contracts that cross module boundaries (parser → LLM → TTS →
audio). They are also the source of truth for the LLM JSON schemas: providers
dump ``model_json_schema()`` into their prompts and validate responses against
them, so a change here is automatically reflected everywhere.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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


class CharactersResult(BaseModel):
    """Response contract of the character-extraction LLM call."""

    characters: list[Character]


class DialogLine(BaseModel):
    """One attributed line of dialog."""

    text: str = Field(min_length=1)
    speaker: str = Field(pattern=r"^(Narrator|Character_[A-Z])$")
    emotion: Emotion = Emotion.NEUTRAL


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
