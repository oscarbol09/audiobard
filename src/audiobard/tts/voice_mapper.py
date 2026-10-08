"""Tone-aware voice mapper.

Algorithm
---------
1. Load the voice pool for the configured locale (``data/voices/en_US.json``).
2. For whole-roster assignment (:meth:`VoiceMapper.assign_all`):
   a. Order unmapped characters by candidate pool constraint
      (most constrained pool first, tie-broken by ``canonical_id``). This ensures
      rare demographic matches are assigned first and produces identical results
      regardless of input roster permutation.
3. For each :class:`~audiobard.models.Character`:
   a. Filter the pool by ``gender_hint`` (mandatory).
   b. Further filter by ``age_hint`` (best-effort; fall back to gender-filtered pool if empty).
   c. Score remaining candidates by cosine similarity of the tone vector.
   d. Prioritize voice uniqueness: candidates not yet assigned in the current
      mapping (``_mapping``) are selected from the highest available similarity
      tier. If all matching candidates are already assigned, voices are reused
      from the top similarity tier.
   e. Deterministic tie-break: candidates within a tier are sorted by
      ``(zlib.crc32(canonical_id + voice_id), voice_id)``, stable across processes
      and platforms (unlike Python's salted ``hash()``).
   f. If even the gender-filtered pool is empty, assign from the full pool
      and log a warning.
4. Save the resulting mapping to ``voice_mapping.json`` (versioned).

The whole-roster assignment (:meth:`~VoiceMapper.assign_all`) is **fully deterministic**
and roster-order independent: given the same voice pool and character set, the output
is always identical, enabling reproducible tests and pipeline resumability.
"""

from __future__ import annotations

import json
import logging
import math
import re
import zlib
from pathlib import Path
from typing import Any

from audiobard.models import Character, GenderHint, Tone, Voice, VoiceAssignment

logger = logging.getLogger(__name__)

# Whole-word gender clues for NEUTRAL characters (names/aliases/description text).
# Matched with word boundaries so short tokens like "man"/"he" do not fire inside
# names such as Amanda / Michelle (issue #79).
_MALE_GENDER_CLUES: tuple[str, ...] = (
    "soñador",
    "hombre",
    "él",
    "he",
    "him",
    "boy",
    "man",
    "mr",
    "señor",
    "don",
)
_FEMALE_GENDER_CLUES: tuple[str, ...] = (
    "mujer",
    "ella",
    "she",
    "her",
    "girl",
    "woman",
    "mrs",
    "ms",
    "señora",
    "doña",
)


def _has_whole_word_clue(text: str, clues: tuple[str, ...]) -> bool:
    """True if any clue appears as a whole word in *text* (case-insensitive)."""
    return any(re.search(rf"\b{re.escape(w)}\b", text, flags=re.IGNORECASE) for w in clues)


# ---------------------------------------------------------------------------
# Tone vector space
# ---------------------------------------------------------------------------

# Each tone is represented as a 3D vector: [energy, warmth, positivity].
# Used to score voices by cosine similarity to a character's tone.
_TONE_VECTORS: dict[str, tuple[float, float, float]] = {
    Tone.NEUTRAL.value: (0.5, 0.5, 0.5),
    Tone.WARM.value: (0.4, 0.9, 0.7),
    Tone.COLD.value: (0.3, 0.1, 0.2),
    Tone.AGITATED.value: (0.9, 0.3, 0.3),
    Tone.CALM.value: (0.2, 0.6, 0.6),
    Tone.MYSTERIOUS.value: (0.4, 0.2, 0.4),
    Tone.CHEERFUL.value: (0.7, 0.8, 0.9),
    Tone.MELANCHOLIC.value: (0.2, 0.5, 0.1),
    Tone.AUTHORITATIVE.value: (0.8, 0.4, 0.5),
    Tone.TIMID.value: (0.2, 0.6, 0.4),
    Tone.SARCASTIC.value: (0.6, 0.2, 0.3),
}


def _cosine_similarity(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _voice_vector(voice: Voice) -> tuple[float, float, float]:
    """Project a voice's single ``energy`` scalar into the 3D space."""
    e = voice.energy
    return (e, 1.0 - e * 0.5, e * 0.6)


class VoiceMapper:
    """Assigns TTS voices to characters using a tone-aware, deterministic algorithm.

    Parameters
    ----------
    voices_path:
        Path to the locale voice pool JSON (e.g. ``data/voices/en_US.json``).
    mapping_path:
        Optional path to load/save the resulting character→voice mapping.
    """

    def __init__(
        self,
        voices_path: Path | str | None = None,
        mapping_path: Path | str | None = None,
        voices: list[Voice] | None = None,
    ) -> None:
        self.voices_path = Path(voices_path) if voices_path else None
        self.mapping_path = Path(mapping_path) if mapping_path else None
        self._pool: list[Voice] = []
        self._mapping: dict[str, VoiceAssignment] = {}
        if voices is not None:
            self._pool = list(voices)
        elif self.voices_path is not None:
            self._load_pool()
        else:
            raise ValueError("Either voices_path or voices must be provided to VoiceMapper.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(self, character: Character) -> VoiceAssignment:
        """Return (and cache) a :class:`VoiceAssignment` for *character*.

        Assignments prioritize voice uniqueness against previously assigned
        characters in this mapper. For whole-roster allocation that canonicalizes
        assignment order and prioritizes constrained pools, use :meth:`assign_all`.
        """
        if character.canonical_id in self._mapping:
            return self._mapping[character.canonical_id]

        assignment = self._compute_assignment(character)
        self._mapping[character.canonical_id] = assignment
        return assignment

    def assign_all(self, characters: list[Character]) -> dict[str, VoiceAssignment]:
        """Assign voices to a list of characters, returning the full mapping.

        Sorts unmapped characters to allocate constrained candidate pools first
        and canonicalizes by ID for strict determinism independent of input order.
        """
        unmapped = [c for c in characters if c.canonical_id not in self._mapping]
        sorted_chars = sorted(
            unmapped,
            key=lambda c: (len(self._candidate_pool_for(c)), c.canonical_id),
        )
        for char in sorted_chars:
            self.assign(char)
        return dict(self._mapping)

    def save_mapping(self, path: Path | str | None = None) -> Path:
        """Persist the current mapping to *path* (or ``self.mapping_path``)."""
        dest = Path(path) if path else self.mapping_path
        if dest is None:
            raise ValueError("No mapping_path configured and no path provided to save_mapping().")
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": 1,
            "assignments": {cid: asmt.model_dump() for cid, asmt in self._mapping.items()},
        }
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Voice mapping saved to %s", dest)
        return dest

    def load_mapping(self, path: Path | str | None = None) -> None:
        """Load a persisted mapping from *path* (or ``self.mapping_path``)."""
        src = Path(path) if path else self.mapping_path
        if src is None or not src.exists():
            return
        data = json.loads(src.read_text(encoding="utf-8-sig"))
        for cid, raw in data.get("assignments", {}).items():
            self._mapping[cid] = VoiceAssignment.model_validate(raw)
        logger.info("Voice mapping loaded from %s (%d entries)", src, len(self._mapping))

    @property
    def pool(self) -> list[Voice]:
        """The loaded voice pool (read-only)."""
        return list(self._pool)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_pool(self) -> None:
        if self.voices_path is None or not self.voices_path.exists():
            raise FileNotFoundError(f"Voice pool not found: {self.voices_path}")
        raw: list[dict[str, Any]] = json.loads(self.voices_path.read_text(encoding="utf-8-sig"))
        self._pool = [Voice.model_validate(v) for v in raw]
        if not self._pool:
            raise ValueError(f"Voice pool is empty: {self.voices_path}")
        logger.debug("Loaded %d voices from %s", len(self._pool), self.voices_path)

    def _candidate_pool_for(self, character: Character) -> list[Voice]:
        """Return candidate voices for *character* filtered by gender and age hints."""
        effective_gender = character.gender_hint
        if effective_gender == GenderHint.NEUTRAL:
            # Whole-word clues only — substring "man"/"he" mis-gendered Amanda/Michelle (#79).
            combined_text = f"{character.name} {' '.join(character.aliases)}"
            if _has_whole_word_clue(combined_text, _MALE_GENDER_CLUES):
                effective_gender = GenderHint.MALE
            elif _has_whole_word_clue(combined_text, _FEMALE_GENDER_CLUES):
                effective_gender = GenderHint.FEMALE

        gender_pool = [v for v in self._pool if v.gender == effective_gender]
        if not gender_pool:
            if character.gender_hint != GenderHint.NEUTRAL:
                logger.warning(
                    "No voices matching gender_hint=%s for %s; using full pool.",
                    character.gender_hint,
                    character.canonical_id,
                )
            gender_pool = list(self._pool)

        age_pool = [v for v in gender_pool if v.age == character.age_hint]
        if not age_pool:
            logger.debug(
                "No voices matching age_hint=%s for %s; falling back to gender pool.",
                character.age_hint,
                character.canonical_id,
            )
        return age_pool if age_pool else gender_pool

    def _compute_assignment(self, character: Character) -> VoiceAssignment:
        candidate_pool = self._candidate_pool_for(character)

        # Step 3: score by cosine similarity to tone vector
        tone_vec = _TONE_VECTORS.get(character.tone.value, _TONE_VECTORS[Tone.NEUTRAL.value])
        scored = [
            (_cosine_similarity(tone_vec, _voice_vector(v)), i, v)
            for i, v in enumerate(candidate_pool)
        ]
        scored.sort(key=lambda x: (-x[0], x[1]))  # descending similarity, stable by index

        # Step 4: deterministic tie-break prioritizing voice uniqueness across characters
        assigned_voice_ids = {asmt.voice_id for asmt in self._mapping.values()}

        unused_candidates = [(score, v) for score, _, v in scored if v.id not in assigned_voice_ids]
        if unused_candidates:
            best_unused_score = unused_candidates[0][0]
            pool_to_pick = [
                v for score, v in unused_candidates if abs(score - best_unused_score) < 1e-9
            ]
        else:
            top_score = scored[0][0]
            pool_to_pick = [v for score, _, v in scored if abs(score - top_score) < 1e-9]

        chosen = min(
            pool_to_pick,
            key=lambda v: (
                zlib.crc32(character.canonical_id.encode("utf-8") + v.id.encode("utf-8")),
                v.id,
            ),
        )

        return VoiceAssignment(
            canonical_id=character.canonical_id,
            voice_id=chosen.id,
            rate=1.0,
            pitch=1.0,
        )
