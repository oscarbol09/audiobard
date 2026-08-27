"""Tests for VoiceMapper.

Uses an in-memory voice pool so no filesystem access is required
for the core determinism and filtering tests.  The save/load tests use
``tmp_path`` (pytest fixture).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
# Gender clue deduction (NEUTRAL → male/female from name/aliases)
# Issue #79: must be whole-word, not substring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,aliases",
    [
        ("Amanda", []),
        ("Michelle", []),
        ("Shelly", []),
        ("Hermione", []),  # contains "he"/"her" as substrings only
        ("humana", []),  # Spanish: "man" inside "humana"
    ],
)
def test_neutral_name_with_male_substring_stays_neutral(
    mapper: VoiceMapper, name: str, aliases: list[str]
) -> None:
    """Names that embed male clue substrings must not flip to male voices."""
    char = Character(
        canonical_id="Character_A",
        name=name,
        aliases=aliases,
        gender_hint=GenderHint.NEUTRAL,
        age_hint=AgeHint.ADULT,
        tone=Tone.NEUTRAL,
    )
    result = mapper.assign(char)
    assert "male" not in result.voice_id, (
        f"{name!r} was wrongly gender-clued male via substring match → {result.voice_id}"
    )
    assert "neutral" in result.voice_id


def test_neutral_with_whole_word_male_clue_gets_male_voice(mapper: VoiceMapper) -> None:
    char = Character(
        canonical_id="Character_B",
        name="Alex",
        aliases=["the man from the shop"],
        gender_hint=GenderHint.NEUTRAL,
        age_hint=AgeHint.ADULT,
        tone=Tone.NEUTRAL,
    )
    result = mapper.assign(char)
    assert "male" in result.voice_id


def test_neutral_with_whole_word_female_clue_gets_female_voice(mapper: VoiceMapper) -> None:
    char = Character(
        canonical_id="Character_A",
        name="Alex",
        aliases=["she who waits"],
        gender_hint=GenderHint.NEUTRAL,
        age_hint=AgeHint.ADULT,
        tone=Tone.NEUTRAL,
    )
    result = mapper.assign(char)
    assert "female" in result.voice_id


def test_has_whole_word_clue_helper() -> None:
    from audiobard.tts.voice_mapper import _has_whole_word_clue

    assert _has_whole_word_clue("Amanda", ("man",)) is False
    assert _has_whole_word_clue("the man arrived", ("man",)) is True
    assert _has_whole_word_clue("Michelle", ("he",)) is False
    assert _has_whole_word_clue("he said", ("he",)) is True
    assert _has_whole_word_clue("humana", ("man",)) is False
    assert _has_whole_word_clue("Mr. Darcy", ("mr",)) is True


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


def test_pool_with_utf8_bom(tmp_path: Path) -> None:
    """VoiceMapper loads voice pool files containing Windows UTF-8 BOM without error."""
    p = tmp_path / "bom_pool.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps([
        {"id": "v1", "locale": "es_CO", "gender": "male", "age": "adult", "energy": 0.5}
    ]).encode("utf-8"))
    mapper = VoiceMapper(voices_path=p)
    assert len(mapper.pool) == 1
    assert mapper.pool[0].id == "v1"



def test_pool_property_returns_copy(mapper: VoiceMapper) -> None:
    pool = mapper.pool
    pool.clear()  # mutating the returned list should not affect mapper
    assert len(mapper.pool) == len(_POOL)


def test_cosine_similarity_zero_vector() -> None:
    from audiobard.tts.voice_mapper import _cosine_similarity

    assert _cosine_similarity((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)) == 0.0
    assert _cosine_similarity((1.0, 1.0, 1.0), (0.0, 0.0, 0.0)) == 0.0



def test_assignment_is_stable_across_processes(tmp_path: Path) -> None:
    """The tie-break must not depend on the process hash seed (issue #9).

    Runs the same assignment in two subprocesses with different, fixed
    PYTHONHASHSEED values. Built-in hash() gives different answers in
    the two seeds, so this pins that the tie-break no longer uses it.
    The pool holds four identical-energy voices so the top-score tie
    group is larger than one; with a single candidate the tie-break
    never runs and this test would pin nothing.
    """
    pool = [
        {
            "id": f"v{i}",
            "locale": "en_US",
            "gender": "neutral",
            "age": "adult",
            "energy": 0.5,
        }
        for i in range(4)
    ]
    pool_path = tmp_path / "en_US.json"
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    script = (
        "import json, sys\n"
        "from audiobard.tts.voice_mapper import VoiceMapper\n"
        "from audiobard.models import Character, GenderHint, AgeHint, Tone\n"
        "mapper = VoiceMapper(voices_path=sys.argv[1])\n"
        "out = {}\n"
        "for letter in 'ABCDEFGH':\n"
        "    c = Character(canonical_id='Character_' + letter, name=letter,\n"
        "                  gender_hint=GenderHint.NEUTRAL,\n"
        "                  age_hint=AgeHint.ADULT, tone=Tone.NEUTRAL)\n"
        "    out[c.canonical_id] = mapper.assign(c).voice_id\n"
        "print(json.dumps(out, sort_keys=True))\n"
    )
    results = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", script, str(pool_path)],
            capture_output=True, text=True, env=env, check=True,
        )
        results.append(proc.stdout.strip())
    assert results[0] == results[1], (
        "voice assignment differs between processes: "
        f"{results[0]} vs {results[1]}"
    )
