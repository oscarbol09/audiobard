"""Tests for the shared Pydantic contracts.

The models in ``src/audiobard/models.py`` are the cross-module contracts, so
their validation behavior is pinned: a regex change that silently breaks the
canonical speaker-ID contract would otherwise go unnoticed until the LLM
prompts and the persistence layer disagree.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from audiobard.models import Character, DialogLine, Emotion, Paragraph, Tone


def test_paragraph_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        Paragraph(text="", chapter=0, index=0)


def test_paragraph_accepts_whitespace_text() -> None:
    # Parsers may emit paragraphs that are only punctuation (e.g. "—").
    p = Paragraph(text="—", chapter=1, index=4)
    assert p.is_dialog is False


def test_character_canonical_id_regex() -> None:
    for bad in ["she", "Character_1", "character_a", "NarratorX"]:
        with pytest.raises(ValidationError, match="canonical_id"):
            Character(canonical_id=bad, name="x")


def test_character_accepts_canonical_ids() -> None:
    for good in ["Narrator", "Character_A", "Character_Z"]:
        c = Character(canonical_id=good, name="x")
        assert c.canonical_id == good


def test_character_aliases_default_to_empty() -> None:
    c = Character(canonical_id="Character_A", name="Alice")
    assert c.aliases == []


def test_character_tone_normalizes_unknown_to_neutral() -> None:
    c = Character(canonical_id="Character_A", name="Alice", tone="aggressive")
    assert c.tone == Tone.NEUTRAL


def test_dialog_line_speaker_regex() -> None:
    with pytest.raises(ValidationError, match="speaker"):
        DialogLine(text="hello", speaker="the young woman")


def test_dialog_line_normalizes_creative_emotions() -> None:
    line1 = DialogLine(text="hello", speaker="Narrator", emotion="impatient")
    assert line1.emotion == Emotion.ANGRY

    line2 = DialogLine(text="hello", speaker="Character_A", emotion="joyful")
    assert line2.emotion == Emotion.HAPPY

    line3 = DialogLine(text="hello", speaker="Character_A", emotion="completely_unknown_emotion")
    assert line3.emotion == Emotion.NEUTRAL


def test_dialog_line_default_emotion_is_neutral() -> None:
    line = DialogLine(text="hello", speaker="Narrator")
    assert line.emotion == Emotion.NEUTRAL


def test_tone_enum_has_expected_members() -> None:
    members = {t.value for t in Tone}
    assert members == {
        "neutral",
        "warm",
        "cold",
        "agitated",
        "calm",
        "mysterious",
        "cheerful",
        "melancholic",
        "authoritative",
        "timid",
        "sarcastic",
    }
