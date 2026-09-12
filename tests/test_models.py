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


@pytest.mark.parametrize(
    "bad_id",
    ["she", "Character_1", "character_a", "NarratorX", "", "Character_AA"],
    ids=[
        "pronoun_rejected",
        "numeric_suffix_rejected",
        "lowercase_suffix_rejected",
        "prefix_extension_rejected",
        "empty_string_rejected",
        "multi_letter_suffix_rejected",
    ],
)
def test_character_canonical_id_regex_rejects_invalid(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="canonical_id"):
        Character(canonical_id=bad_id, name="x")


@pytest.mark.parametrize(
    "good_id",
    ["Narrator", "Character_A", "Character_M", "Character_Z"],
    ids=["narrator", "character_a", "character_middle", "character_z"],
)
def test_character_accepts_canonical_ids(good_id: str) -> None:
    c = Character(canonical_id=good_id, name="x")
    assert c.canonical_id == good_id


def test_character_aliases_default_to_empty() -> None:
    c = Character(canonical_id="Character_A", name="Alice")
    assert c.aliases == []


@pytest.mark.parametrize(
    ("raw_tone", "expected_tone"),
    [
        ("aggressive", Tone.NEUTRAL),
        ("warm", Tone.WARM),
        ("completely_unknown_tone", Tone.NEUTRAL),
    ],
    ids=[
        "unknown_aggressive_normalizes_to_neutral",
        "valid_string_normalizes_to_warm",
        "arbitrary_string_normalizes_to_neutral",
    ],
)
def test_character_tone_normalizes_unknown_to_neutral(
    raw_tone: str, expected_tone: Tone
) -> None:
    c = Character.model_validate(
        {"canonical_id": "Character_A", "name": "Alice", "tone": raw_tone}
    )
    assert c.tone == expected_tone


def test_dialog_line_speaker_regex() -> None:
    with pytest.raises(ValidationError, match="speaker"):
        DialogLine(text="hello", speaker="the young woman")


@pytest.mark.parametrize(
    ("raw_emotion", "expected_emotion"),
    [
        ("impatient", Emotion.ANGRY),
        ("joyful", Emotion.HAPPY),
        ("completely_unknown_emotion", Emotion.NEUTRAL),
        ("whispering", Emotion.WHISPER),
        ("furious", Emotion.ANGRY),
    ],
    ids=[
        "synonym_impatient_to_angry",
        "synonym_joyful_to_happy",
        "unknown_emotion_to_neutral",
        "synonym_whispering_to_whisper",
        "synonym_furious_to_angry",
    ],
)
def test_dialog_line_normalizes_creative_emotions(
    raw_emotion: str, expected_emotion: Emotion
) -> None:
    line = DialogLine.model_validate(
        {"text": "hello", "speaker": "Character_A", "emotion": raw_emotion}
    )
    assert line.emotion == expected_emotion


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

