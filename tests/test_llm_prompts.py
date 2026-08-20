"""Tests for prompt templates (prompts.py).

These tests verify that:
- Prompt strings are not empty.
- The Pydantic schema is injected into each prompt.
- Few-shot examples are present.
- The versioning sentinel is correct.
- Builder functions include the user text.
"""

from __future__ import annotations

from audiobard.llm.prompts import (
    PROMPT_VERSION,
    build_attribute_dialog_prompt,
    build_extract_characters_prompt,
)
from audiobard.models import AgeHint, Character, CharactersResult, GenderHint, Tone


def _make_characters() -> CharactersResult:
    return CharactersResult(
        characters=[
            Character(
                canonical_id="Narrator",
                name="Narrator",
                tone=Tone.NEUTRAL,
                gender_hint=GenderHint.NEUTRAL,
                age_hint=AgeHint.ADULT,
            ),
            Character(
                canonical_id="Character_A",
                name="Alice",
                aliases=["Allie"],
                tone=Tone.WARM,
                gender_hint=GenderHint.FEMALE,
                age_hint=AgeHint.YOUNG,
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Version sentinel
# ---------------------------------------------------------------------------


def test_prompt_version_is_string() -> None:
    assert isinstance(PROMPT_VERSION, str)
    assert PROMPT_VERSION  # not empty


def test_prompt_version_starts_with_v() -> None:
    assert PROMPT_VERSION.startswith("v")


# ---------------------------------------------------------------------------
# build_extract_characters_prompt
# ---------------------------------------------------------------------------


def test_extract_prompt_contains_user_text() -> None:
    text = "Unique marker text: XYZ-12345"
    prompt = build_extract_characters_prompt(text)
    assert text in prompt


def test_extract_prompt_contains_schema() -> None:
    prompt = build_extract_characters_prompt("some text")
    # Schema is injected; at minimum the top-level key "properties" appears.
    assert "properties" in prompt


def test_extract_prompt_contains_characters_key() -> None:
    prompt = build_extract_characters_prompt("some text")
    assert "characters" in prompt


def test_extract_prompt_has_few_shot_examples() -> None:
    prompt = build_extract_characters_prompt("my text")
    # Few-shot examples include "USER:" and "ASSISTANT:" markers.
    assert prompt.count("USER:") >= 2  # at least 1 example + the real request
    assert "ASSISTANT:" in prompt


def test_extract_prompt_has_system_section() -> None:
    prompt = build_extract_characters_prompt("my text")
    assert "SYSTEM:" in prompt


def test_extract_prompt_is_nonempty_string() -> None:
    prompt = build_extract_characters_prompt("x")
    assert isinstance(prompt, str)
    assert len(prompt) > 100


# ---------------------------------------------------------------------------
# build_attribute_dialog_prompt
# ---------------------------------------------------------------------------


def test_attribute_prompt_contains_user_text() -> None:
    text = "Unique marker: ATTR-99887"
    prompt = build_attribute_dialog_prompt(text, _make_characters())
    assert text in prompt


def test_attribute_prompt_contains_schema() -> None:
    prompt = build_attribute_dialog_prompt("text", _make_characters())
    assert "properties" in prompt


def test_attribute_prompt_contains_character_roster() -> None:
    characters = _make_characters()
    prompt = build_attribute_dialog_prompt("text", characters)
    assert "Narrator" in prompt
    assert "Character_A" in prompt
    assert "Alice" in prompt


def test_attribute_prompt_has_few_shot_examples() -> None:
    prompt = build_attribute_dialog_prompt("text", _make_characters())
    assert prompt.count("USER:") >= 2
    assert "ASSISTANT:" in prompt


def test_attribute_prompt_no_empty_roster(capsys: object) -> None:
    """Even with a single-character roster the prompt builds successfully."""
    single = CharactersResult(
        characters=[
            Character(
                canonical_id="Narrator",
                name="Narrator",
                tone=Tone.NEUTRAL,
                gender_hint=GenderHint.NEUTRAL,
                age_hint=AgeHint.ADULT,
            )
        ]
    )
    prompt = build_attribute_dialog_prompt("text", single)
    assert "Narrator" in prompt
    assert len(prompt) > 50
