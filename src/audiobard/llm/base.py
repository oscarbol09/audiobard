"""Abstract LLM client with retry, schema validation, and token logging.

All concrete providers (:class:`OllamaClient`, :class:`GeminiClient`,
:class:`OpenRouterClient`) inherit from :class:`LLMClient` and only need to
implement :meth:`_raw_call`.

Retry policy:
- Up to ``max_retries`` attempts.
- Exponential backoff: ``min(60, 2 ** attempt + jitter)`` seconds.
- Schema mismatch (Pydantic ``ValidationError``) counts as a retriable error.
- On exhaustion, the last exception is re-raised.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from audiobard.models import AttributionResult, CharactersResult

if TYPE_CHECKING:
    from audiobard.persistence import PersistenceManager

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

# Bump this when prompts or schema logic changes — old cache entries are
# automatically invalidated because the key includes this version.
_CACHE_VERSION = "v1"


def _backoff(attempt: int) -> float:
    """Return seconds to sleep before attempt *attempt* (0-indexed)."""
    return float(min(60.0, float((2**attempt) + random.uniform(0.0, 1.0))))


class LLMClient(ABC):
    """Base class for all LLM providers.

    Parameters
    ----------
    model:
        Model identifier (provider-specific string).
    temperature:
        Sampling temperature passed to the provider.
    max_retries:
        Number of attempts before giving up (includes the first try).
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.2,
        max_retries: int = 3,
        persistence: PersistenceManager | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._persistence = persistence

    # ------------------------------------------------------------------
    # Provider contract
    # ------------------------------------------------------------------

    @abstractmethod
    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        """Send *prompt* to the LLM and return the raw response string.

        Parameters
        ----------
        prompt:
            The full prompt (system + user merged, or role-separated — up to
            the concrete implementation).
        schema:
            The JSON Schema dict to pass to the provider for constrained
            generation (JSON mode / format parameter).

        Returns
        -------
        str
            Raw text response from the provider (should be valid JSON).
        """

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def extract_characters(self, text: str) -> CharactersResult:
        """Identify characters in *text* and return a :class:`CharactersResult`.

        The prompt and few-shot examples come from :mod:`audiobard.llm.prompts`.
        """
        from audiobard.llm.prompts import build_extract_characters_prompt

        prompt = build_extract_characters_prompt(text)
        schema = CharactersResult.model_json_schema()
        return await self._call_with_retry(prompt, schema, CharactersResult)

    async def attribute_dialog(
        self,
        chapter_text: str,
        characters: CharactersResult,
    ) -> AttributionResult:
        """Attribute each dialog line in *chapter_text* to a speaker.

        Parameters
        ----------
        chapter_text:
            The raw chapter text (≤ ``chunk_words`` words, chunked by the
            pipeline before this call).
        characters:
            Character roster from :meth:`extract_characters`.
        """
        from audiobard.llm.prompts import build_attribute_dialog_prompt

        prompt = build_attribute_dialog_prompt(chapter_text, characters)
        schema = AttributionResult.model_json_schema()
        return await self._call_with_retry(prompt, schema, AttributionResult)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_cls: type[_T],
    ) -> _T:
        """Call :meth:`_raw_call` up to ``max_retries`` times.

        Before the first attempt, checks the SQLite LLM cache (if a
        :class:`~audiobard.persistence.PersistenceManager` was injected).
        A successful response is stored in the cache; errors are never cached.

        Retries on:
        - Any exception from ``_raw_call`` (network errors, timeouts, etc.)
        - :class:`~pydantic.ValidationError` (malformed JSON or schema mismatch)
        - :class:`json.JSONDecodeError` (non-JSON response)
        """
        # ------------------------------------------------------------------
        # 1. Cache lookup — key = SHA-256(version + model + temperature + prompt)
        # ------------------------------------------------------------------
        cache_key_material = (
            f"{_CACHE_VERSION}:{self.model}:{self.temperature:.4f}:{prompt}"
        )
        prompt_hash = hashlib.sha256(cache_key_material.encode()).hexdigest()

        if self._persistence is not None:
            cached_raw = self._persistence.get_llm_cache(prompt_hash)
            if cached_raw is not None:
                logger.debug(
                    "LLM cache hit: hash=%s model=%s", prompt_hash[:12], self.model
                )
                try:
                    return model_cls.model_validate(json.loads(cached_raw))
                except (ValidationError, json.JSONDecodeError) as exc:
                    # Stale or corrupt cache entry — fall through to live call
                    logger.warning("LLM cache entry invalid, re-querying: %s", exc)

        # ------------------------------------------------------------------
        # 2. Live call with retries
        # ------------------------------------------------------------------
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            t0 = time.monotonic()
            try:
                raw = await self._raw_call(prompt, schema)
                data = json.loads(raw)
                result = model_cls.model_validate(data)
                elapsed = time.monotonic() - t0
                logger.debug(
                    "LLM call succeeded",
                    extra={
                        "provider": type(self).__name__,
                        "model": self.model,
                        "attempt": attempt,
                        "elapsed_s": round(elapsed, 3),
                    },
                )
                # Store in cache only on success
                if self._persistence is not None:
                    try:
                        self._persistence.save_llm_cache(
                            prompt_hash, raw, type(self).__name__
                        )
                    except Exception as cache_exc:
                        logger.warning("Failed to write LLM cache: %s", cache_exc)
                return result
            except (ValidationError, json.JSONDecodeError, Exception) as exc:
                last_exc = exc
                elapsed = time.monotonic() - t0
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.max_retries,
                    exc,
                    extra={"elapsed_s": round(elapsed, 3)},
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(_backoff(attempt))

        raise RuntimeError(
            f"LLM call failed after {self.max_retries} attempts"
        ) from last_exc
