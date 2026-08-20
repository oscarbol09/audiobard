"""Tone-aware voice mapper.

Algorithm
---------
1. Load the voice pool for the configured locale (``data/voices/en_US.json``).
2. For each :class:`~audiobard.models.Character`:
   a. Filter the pool by ``gender_hint`` (mandatory).
   b. Further filter by ``age_hint`` (best-effort; fall back to gender-filtered pool if empty).
   c. Score remaining candidates by cosine similarity of the tone vector.
   d. Deterministic tie-break: ``hash(canonical_id) % len(candidate_pool)``.
   e. If even the gender-filtered pool is empty, assign from the full pool
      via the same hash tie-break and log a warning.
3. Save the resulting mapping to ``voice_mapping.json`` (versioned).

The assignment is **fully deterministic**: given the same voice pool and
character list the output is always identical, enabling reproducible tests and
pipeline resumability.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from audiobard.models import Character, Tone, Voice, VoiceAssignment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tone vector space
# ---------------------------------------------------------------------------

# Each tone is represented as a 3D vector: [energy, warmth, positivity].
# Used to score voices by cosine similarity to a character's tone.
_TONE_VECTORS: dict[str, tuple[float, float, float]] = {
    Tone.NEUTRAL.value:       (0.5, 0.5, 0.5),
    Tone.WARM.value:          (0.4, 0.9, 0.7),
    Tone.COLD.value:          (0.3, 0.1, 0.2),
    Tone.AGITATED.value:      (0.9, 0.3, 0.3),
    Tone.CALM.value:          (0.2, 0.6, 0.6),
    Tone.MYSTERIOUS.value:    (0.4, 0.2, 0.4),
    Tone.CHEERFUL.value:      (0.7, 0.8, 0.9),
    Tone.MELANCHOLIC.value:   (0.2, 0.5, 0.1),
    Tone.AUTHORITATIVE.value: (0.8, 0.4, 0.5),
    Tone.TIMID.value:         (0.2, 0.6, 0.4),
    Tone.SARCASTIC.value:     (0.6, 0.2, 0.3),
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
        voices_path: Path | str,
        mapping_path: Path | str | None = None,
    ) -> None:
        self.voices_path = Path(voices_path)
        self.mapping_path = Path(mapping_path) if mapping_path else None
        self._pool: list[Voice] = []
        self._mapping: dict[str, VoiceAssignment] = {}
        self._load_pool()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(self, character: Character) -> VoiceAssignment:
        """Return (and cache) a :class:`VoiceAssignment` for *character*.

        The result is deterministic: the same character always maps to the
        same voice given the same pool.
        """
        if character.canonical_id in self._mapping:
            return self._mapping[character.canonical_id]

        assignment = self._compute_assignment(character)
        self._mapping[character.canonical_id] = assignment
        return assignment

    def assign_all(self, characters: list[Character]) -> dict[str, VoiceAssignment]:
        """Assign voices to a list of characters, returning the full mapping."""
        for char in characters:
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
            "assignments": {
                cid: asmt.model_dump() for cid, asmt in self._mapping.items()
            },
        }
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Voice mapping saved to %s", dest)
        return dest

    def load_mapping(self, path: Path | str | None = None) -> None:
        """Load a persisted mapping from *path* (or ``self.mapping_path``)."""
        src = Path(path) if path else self.mapping_path
        if src is None or not src.exists():
            return
        data = json.loads(src.read_text(encoding="utf-8"))
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
        if not self.voices_path.exists():
            raise FileNotFoundError(f"Voice pool not found: {self.voices_path}")
        raw: list[dict[str, Any]] = json.loads(
            self.voices_path.read_text(encoding="utf-8")
        )
        self._pool = [Voice.model_validate(v) for v in raw]
        if not self._pool:
            raise ValueError(f"Voice pool is empty: {self.voices_path}")
        logger.debug("Loaded %d voices from %s", len(self._pool), self.voices_path)

    def _compute_assignment(self, character: Character) -> VoiceAssignment:
        # Step 1: filter by gender_hint (mandatory)
        gender_pool = [v for v in self._pool if v.gender == character.gender_hint]
        if not gender_pool:
            logger.warning(
                "No voices matching gender_hint=%s for %s; using full pool.",
                character.gender_hint,
                character.canonical_id,
            )
            gender_pool = list(self._pool)

        # Step 2: filter by age_hint (best-effort)
        age_pool = [v for v in gender_pool if v.age == character.age_hint]
        candidate_pool = age_pool if age_pool else gender_pool
        if not age_pool:
            logger.debug(
                "No voices matching age_hint=%s for %s; falling back to gender pool.",
                character.age_hint,
                character.canonical_id,
            )

        # Step 3: score by cosine similarity to tone vector
        tone_vec = _TONE_VECTORS.get(character.tone.value, _TONE_VECTORS[Tone.NEUTRAL.value])
        scored = [
            (_cosine_similarity(tone_vec, _voice_vector(v)), i, v)
            for i, v in enumerate(candidate_pool)
        ]
        scored.sort(key=lambda x: (-x[0], x[1]))  # descending similarity, stable by index

        # Step 4: deterministic tie-break among top-scoring voices
        top_score = scored[0][0]
        top_voices = [v for score, _, v in scored if abs(score - top_score) < 1e-9]
        chosen = top_voices[hash(character.canonical_id) % len(top_voices)]

        return VoiceAssignment(
            canonical_id=character.canonical_id,
            voice_id=chosen.id,
            rate=1.0,
            pitch=1.0,
        )
