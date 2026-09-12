"""Property-based testing with Hypothesis for text parsers and Pydantic models."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from audiobard.models import (
    AgeHint,
    Character,
    DialogLine,
    Emotion,
    GenderHint,
    Paragraph,
    Tone,
)
from audiobard.parser.text_parser import TextParser


@given(st.text())
@settings(max_examples=100)
def test_text_parser_never_crashes_on_arbitrary_string(text: str) -> None:
    """TextParser.parse must handle arbitrary Unicode strings without unhandled exceptions."""
    parser = TextParser()
    paragraphs = parser.parse(text)
    assert isinstance(paragraphs, list)
    for i, p in enumerate(paragraphs):
        assert isinstance(p, Paragraph)
        assert p.text.strip() != ""
        assert p.chapter == 0
        assert p.index == i


@given(st.binary())
@settings(max_examples=50)
def test_text_parser_handles_arbitrary_bytes(data: bytes) -> None:
    """TextParser.parse must handle arbitrary byte streams gracefully."""
    parser = TextParser()
    paragraphs = parser.parse(data)
    assert isinstance(paragraphs, list)
    for i, p in enumerate(paragraphs):
        assert isinstance(p, Paragraph)
        assert p.index == i


@given(st.text())
def test_character_tone_normalization_invariant(raw_tone: str) -> None:
    """Character.normalize_tone must always return a valid Tone enum member."""
    normalized = Character.normalize_tone(raw_tone)
    assert isinstance(normalized, Tone)
    # Invariant: Idempotence (normalizing an already normalized enum returns the same)
    assert Character.normalize_tone(normalized) == normalized


@given(st.text())
def test_character_gender_normalization_invariant(raw_gender: str) -> None:
    """Character.normalize_gender must always return a valid GenderHint enum member."""
    normalized = Character.normalize_gender(raw_gender)
    assert isinstance(normalized, GenderHint)
    assert Character.normalize_gender(normalized) == normalized


@given(st.text())
def test_character_age_normalization_invariant(raw_age: str) -> None:
    """Character.normalize_age must always return a valid AgeHint enum member."""
    normalized = Character.normalize_age(raw_age)
    assert isinstance(normalized, AgeHint)
    assert Character.normalize_age(normalized) == normalized


@given(st.text())
def test_dialog_line_emotion_normalization_invariant(raw_emotion: str) -> None:
    """DialogLine.normalize_emotion must always return a valid Emotion enum member."""
    normalized = DialogLine.normalize_emotion(raw_emotion)
    assert isinstance(normalized, Emotion)
    assert DialogLine.normalize_emotion(normalized) == normalized
