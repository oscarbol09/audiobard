"""Tests for LLMClient caching mechanisms (LLM request cache)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from audiobard.llm.base import LLMClient
from audiobard.persistence import PersistenceManager


# Concrete implementation for cache testing
class _EchoClient(LLMClient):
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


@pytest.mark.asyncio
async def test_llm_cache_hit_and_miss() -> None:
    """Test that LLM request caching hits, misses, and caches on success only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pm = PersistenceManager(db_path)

        # 1. First call: Cache miss, should execute raw call and save to cache
        client = _EchoClient([_VALID_CHARACTERS_JSON], persistence=pm)
        with patch("asyncio.sleep"):
            res1 = await client.extract_characters("Some text")

        assert res1.characters[0].canonical_id == "Narrator"
        assert client._call_count == 1

        # Verify it was saved to cache
        with pm._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
            assert row[0] == 1

        # 2. Second call (same client / prompt): Cache hit, should NOT call raw call
        res2 = await client.extract_characters("Some text")
        assert res2.characters[0].canonical_id == "Narrator"
        assert client._call_count == 1  # call count hasn't changed!

        # Verify hits counter in cache was incremented
        with pm._get_conn() as conn:
            hits = conn.execute("SELECT hits FROM llm_cache").fetchone()[0]
            assert hits == 1


@pytest.mark.asyncio
async def test_llm_cache_no_save_on_error() -> None:
    """Test that LLM failures are never cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pm = PersistenceManager(db_path)

        client = _EchoClient(
            [RuntimeError("API Error")],
            persistence=pm,
            max_retries=1,
        )

        # Call fails
        with patch("asyncio.sleep"), pytest.raises(
            RuntimeError, match="LLM call failed"
        ):
            await client.extract_characters("Some text")

        # Cache should be empty
        with pm._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
            assert row[0] == 0


@pytest.mark.asyncio
async def test_llm_cache_corrupted_json_fallback() -> None:
    """Test that corrupted JSON in cache falls back to live provider call."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pm = PersistenceManager(db_path)

        client = _EchoClient([_VALID_CHARACTERS_JSON], persistence=pm)
        # Pre-seed corrupted JSON into cache
        with patch.object(pm, "get_llm_cache", return_value="invalid-json-content"):
            with patch("asyncio.sleep"):
                res = await client.extract_characters("Some text")
            assert res.characters[0].canonical_id == "Narrator"
            assert client._call_count == 1


@pytest.mark.asyncio
async def test_llm_cache_save_error_graceful() -> None:
    """Test that failure in saving to cache does not abort the LLM call."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pm = PersistenceManager(db_path)

        client = _EchoClient([_VALID_CHARACTERS_JSON], persistence=pm)
        with patch.object(pm, "save_llm_cache", side_effect=RuntimeError("Disk Error")):
            with patch("asyncio.sleep"):
                res = await client.extract_characters("Some text")
            assert res.characters[0].canonical_id == "Narrator"
