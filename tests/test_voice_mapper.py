"""Tests for VoiceMapper.

Uses an in-memory voice pool so no filesystem access is required
for the core determinism and filtering tests.  The save/load tests use
``tmp_path`` (pytest fixture).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from audiobard.models import AgeHint, Character, GenderHint, Tone, VoiceAssignment
from audiobard.tts.voice_mapper import VoiceMapper

# ---------------------------------------------------------------------------
# Minimal voice pool fixture
# ---------------------------------------------------------------------------

_POOL = [
    {
        "id": "en_US-female-young-high",
        "locale": "en_US",
        "gender": "female",
        "age": "young",
        "energy": 0.8,
    },
    {
        "id": "en_US-female-adult-medium",
        "locale": "en_US",
        "gender": "female",
        "age": "adult",
        "energy": 0.5,
    },
    {
        "id": "en_US-male-adult-medium",
        "locale": "en_US",
        "gender": "male",
        "age": "adult",
        "energy": 0.55,
    },
    {
        "id": "en_US-male-elderly-low",
        "locale": "en_US",
        "gender": "male",
        "age": "elderly",
        "energy": 0.25,
    },
    {
        "id": "en_US-neutral-adult-medium",
        "locale": "en_US",
        "gender": "neutral",
        "age": "adult",
        "energy": 0.5,
    },
]


@pytest.fixture()
def pool_path(tmp_path: Path) -> Path:
    """Write the minimal pool to a temp file and return the path."""
    p = tmp_path / "en_US.json"
    p.write_text(json.dumps(_POOL), encoding="utf-8")
    return p


@pytest.fixture()
def mapper(pool_path: Path) -> VoiceMapper:
    return VoiceMapper(voices_path=pool_path)


def _char(
    canonical_id: str = "Character_A",
    name: str = "Alice",
    tone: Tone = Tone.NEUTRAL,
    gender: GenderHint = GenderHint.FEMALE,
    age: AgeHint = AgeHint.ADULT,
) -> Character:
    return Character(
        canonical_id=canonical_id,
        name=name,
        tone=tone,
        gender_hint=gender,
        age_hint=age,
    )


# ---------------------------------------------------------------------------
# Basic assignment
# ---------------------------------------------------------------------------


def test_assign_returns_voice_assignment(mapper: VoiceMapper) -> None:
    result = mapper.assign(_char())
    assert isinstance(result, VoiceAssignment)


def test_assignment_canonical_id_matches(mapper: VoiceMapper) -> None:
    char = _char(canonical_id="Character_B")
    result = mapper.assign(char)
    assert result.canonical_id == "Character_B"


def test_assignment_voice_id_in_pool(mapper: VoiceMapper) -> None:
    pool_ids = {v["id"] for v in _POOL}
    result = mapper.assign(_char())
    assert result.voice_id in pool_ids


# ---------------------------------------------------------------------------
# Gender filtering
# ---------------------------------------------------------------------------


def test_male_character_gets_male_voice(mapper: VoiceMapper) -> None:
    result = mapper.assign(_char(canonical_id="Character_B", gender=GenderHint.MALE))
    assert "male" in result.voice_id


def test_female_character_gets_female_voice(mapper: VoiceMapper) -> None:
    result = mapper.assign(_char(canonical_id="Character_A", gender=GenderHint.FEMALE))
    assert "female" in result.voice_id


def test_neutral_character_gets_neutral_voice(mapper: VoiceMapper) -> None:
    result = mapper.assign(_char(canonical_id="Narrator", gender=GenderHint.NEUTRAL))
    assert "neutral" in result.voice_id


# ---------------------------------------------------------------------------
# Age filtering
# ---------------------------------------------------------------------------


def test_age_hint_respected_when_possible(mapper: VoiceMapper) -> None:
    result = mapper.assign(
        _char(canonical_id="Character_A", gender=GenderHint.FEMALE, age=AgeHint.YOUNG)
    )
    assert "young" in result.voice_id


def test_fallback_to_gender_pool_when_age_missing(mapper: VoiceMapper) -> None:
    """Elderly female doesn't exist in pool — should fall back to female pool."""
    result = mapper.assign(
        _char(canonical_id="Character_A", gender=GenderHint.FEMALE, age=AgeHint.ELDERLY)
    )
    # Should still be a female voice (gender filter respected)
    assert "female" in result.voice_id


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_character_always_same_voice(mapper: VoiceMapper) -> None:
    char = _char(canonical_id="Character_A")
    r1 = mapper.assign(char)
    r2 = mapper.assign(char)
    assert r1.voice_id == r2.voice_id


def test_different_mapper_instances_same_result(pool_path: Path) -> None:
    """Two fresh VoiceMapper instances produce the same assignment."""
    char = _char(canonical_id="Character_A")
    r1 = VoiceMapper(voices_path=pool_path).assign(char)
    r2 = VoiceMapper(voices_path=pool_path).assign(char)
    assert r1.voice_id == r2.voice_id


def test_assign_all_returns_all_ids(mapper: VoiceMapper) -> None:
    chars = [
        _char(canonical_id="Narrator", gender=GenderHint.NEUTRAL),
        _char(canonical_id="Character_A", gender=GenderHint.FEMALE),
        _char(canonical_id="Character_B", gender=GenderHint.MALE),
    ]
    mapping = mapper.assign_all(chars)
    assert set(mapping.keys()) == {"Narrator", "Character_A", "Character_B"}


# ---------------------------------------------------------------------------
# Caching (second call uses cache, not recomputed)
# ---------------------------------------------------------------------------


def test_second_assign_uses_cache(mapper: VoiceMapper) -> None:
    char = _char(canonical_id="Character_A")
    r1 = mapper.assign(char)
    # Wipe the pool to confirm cache is used
    mapper._pool = []
    r2 = mapper.assign(char)
    assert r1.voice_id == r2.voice_id


# ---------------------------------------------------------------------------
# Save / Load mapping
# ---------------------------------------------------------------------------


def test_save_and_load_mapping(mapper: VoiceMapper, tmp_path: Path) -> None:
    char = _char(canonical_id="Character_A")
    mapper.assign(char)
    dest = tmp_path / "mapping.json"
    mapper.save_mapping(dest)

    # Load into fresh mapper
    mapper2 = VoiceMapper(voices_path=mapper.voices_path)
    mapper2.load_mapping(dest)
    assert "Character_A" in mapper2._mapping
    assert mapper2._mapping["Character_A"].voice_id == mapper._mapping["Character_A"].voice_id


def test_save_creates_parent_dirs(mapper: VoiceMapper, tmp_path: Path) -> None:
    char = _char(canonical_id="Narrator", gender=GenderHint.NEUTRAL)
    mapper.assign(char)
    dest = tmp_path / "nested" / "deep" / "mapping.json"
    mapper.save_mapping(dest)
    assert dest.exists()


def test_load_nonexistent_mapping_is_noop(pool_path: Path) -> None:
    m = VoiceMapper(voices_path=pool_path, mapping_path=Path("/nonexistent/path.json"))
    m.load_mapping()  # Should not raise


def test_save_without_path_raises(mapper: VoiceMapper) -> None:
    with pytest.raises(ValueError, match="mapping_path"):
        mapper.save_mapping()


# ---------------------------------------------------------------------------
# Pool validation
# ---------------------------------------------------------------------------


def test_missing_pool_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        VoiceMapper(voices_path=tmp_path / "missing.json")


def test_empty_pool_raises(tmp_path: Path) -> None:
    p = tmp_path / "empty.json"
    p.write_text("[]")
    with pytest.raises(ValueError, match="empty"):
        VoiceMapper(voices_path=p)


def test_pool_property_returns_copy(mapper: VoiceMapper) -> None:
    pool = mapper.pool
    pool.clear()  # mutating the returned list should not affect mapper
    assert len(mapper.pool) == len(_POOL)
