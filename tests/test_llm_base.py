"""Tests for LLMClient base class — retry, backoff, and schema validation.

All network calls are mocked; no real LLM is needed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from audiobard.llm.base import LLMClient, _backoff
from audiobard.models import AttributionResult, CharactersResult

# ---------------------------------------------------------------------------
# Minimal concrete implementation for testing
# ---------------------------------------------------------------------------


class _EchoClient(LLMClient):
    """LLM client that returns whatever ``responses`` provides in order."""

    def __init__(self, responses: list[str | Exception], **kwargs: Any) -> None:
        super().__init__(model="test-model", **kwargs)
        self._responses = list(responses)
        self._call_count = 0

    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        if self._call_count >= len(self._responses):
            raise RuntimeError("No more responses configured")
        resp = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_CHARACTERS_JSON = json.dumps(
    {
        "characters": [
            {
                "canonical_id": "Narrator",
                "name": "Narrator",
                "aliases": [],
                "tone": "neutral",
                "gender_hint": "neutral",
                "age_hint": "adult",
            }
        ]
    }
)

_VALID_ATTRIBUTION_JSON = json.dumps(
    {
        "lines": [
            {
                "text": "Hello there.",
                "speaker": "Narrator",
                "emotion": "neutral",
            }
        ]
    }
)


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------


def test_backoff_grows_with_attempts() -> None:
    # Ignore jitter — just check the base grows.
    values = [_backoff(i) for i in range(5)]
    # Each value should be at least 2^i (before jitter clamp).
    for i, v in enumerate(values):
        assert v >= 2**i or v == 60.0  # clamped at 60


def test_backoff_clamped_at_60() -> None:
    assert _backoff(10) <= 60.0


# ---------------------------------------------------------------------------
# Successful call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_characters_success() -> None:
    client = _EchoClient([_VALID_CHARACTERS_JSON])
    with patch("asyncio.sleep"):  # no actual sleeping
        result = await client.extract_characters("Some text")
    assert isinstance(result, CharactersResult)
    assert result.characters[0].canonical_id == "Narrator"


@pytest.mark.asyncio
async def test_attribute_dialog_success() -> None:
    characters = CharactersResult.model_validate(json.loads(_VALID_CHARACTERS_JSON))
    client = _EchoClient([_VALID_ATTRIBUTION_JSON])
    with patch("asyncio.sleep"):
        result = await client.attribute_dialog("Some dialog text.", characters)
    assert isinstance(result, AttributionResult)
    assert result.lines[0].speaker == "Narrator"


# ---------------------------------------------------------------------------
# Retry on failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_json_error() -> None:
    """Client retries when the response is not valid JSON."""
    client = _EchoClient(
        [
            "not-json",
            "still-not-json",
            _VALID_CHARACTERS_JSON,
        ],
        max_retries=3,
    )
    with patch("asyncio.sleep"):
        result = await client.extract_characters("text")
    assert client._call_count == 3
    assert isinstance(result, CharactersResult)


@pytest.mark.asyncio
async def test_retries_on_schema_mismatch() -> None:
    """Client retries when JSON is valid but doesn't match the Pydantic model."""
    bad_json = json.dumps({"wrong_key": []})
    client = _EchoClient([bad_json, _VALID_CHARACTERS_JSON], max_retries=3)
    with patch("asyncio.sleep"):
        result = await client.extract_characters("text")
    assert isinstance(result, CharactersResult)
    assert client._call_count == 2


@pytest.mark.asyncio
async def test_retries_on_exception() -> None:
    """Client retries on a raw exception from _raw_call."""
    client = _EchoClient(
        [RuntimeError("network error"), _VALID_CHARACTERS_JSON],
        max_retries=3,
    )
    with patch("asyncio.sleep"):
        result = await client.extract_characters("text")
    assert isinstance(result, CharactersResult)
    assert client._call_count == 2


# ---------------------------------------------------------------------------
# Exhausted retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_after_max_retries() -> None:
    """RuntimeError is raised when all retries are exhausted."""
    client = _EchoClient(
        [RuntimeError("fail"), RuntimeError("fail"), RuntimeError("fail")],
        max_retries=3,
    )
    with patch("asyncio.sleep"), pytest.raises(RuntimeError, match="3 attempts"):
        await client.extract_characters("text")
    assert client._call_count == 3


@pytest.mark.asyncio
async def test_raises_after_max_retries_schema() -> None:
    """RuntimeError is raised when Pydantic validation never succeeds."""
    bad = json.dumps({"bad": "schema"})
    client = _EchoClient([bad, bad, bad], max_retries=3)
    with patch("asyncio.sleep"), pytest.raises(RuntimeError, match="3 attempts"):
        await client.extract_characters("text")
