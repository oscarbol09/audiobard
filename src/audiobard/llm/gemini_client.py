"""Gemini LLM client (OPT-IN — cloud, non-commercial free tier).

Uses the Gemini REST API directly via ``httpx`` to avoid adding
``google-generativeai`` as a hard dependency.

Install extras: ``pip install audiobard[llm-gemini]``
(The optional dep is declared for users who prefer the SDK; this client works
with httpx alone.)

Required env var: ``AUDIOBARD_GEMINI_API_KEY`` or ``GEMINI_API_KEY``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from audiobard.llm.base import LLMClient

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/{model}:generateContent?key={key}"
)


class GeminiClient(LLMClient):
    """LLM client backed by the Google Gemini API.

    Parameters
    ----------
    model:
        Gemini model name, e.g. ``"gemini-2.0-flash"`` (default).
    api_key:
        API key.  Falls back to the environment variable ``GEMINI_API_KEY``
        then ``AUDIOBARD_GEMINI_API_KEY``.
    temperature:
        Sampling temperature.
    max_retries:
        Maximum retry attempts.
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_retries=max_retries)
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("AUDIOBARD_GEMINI_API_KEY")
            or ""
        )
        if not self.api_key:
            raise ValueError(
                "Gemini API key not found.  Set GEMINI_API_KEY or "
                "AUDIOBARD_GEMINI_API_KEY in your environment."
            )

    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        """POST to the Gemini generateContent endpoint with JSON response mode."""
        url = _GEMINI_URL.format(model=self.model, key=self.api_key)
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            val: str = data["candidates"][0]["content"]["parts"][0]["text"]
            return val
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected Gemini response structure: {data}") from exc

    @staticmethod
    def _extract_json_from_response(raw: str) -> str:
        """Strip optional markdown fences the API might still return."""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            # Drop first and last fence lines.
            inner = lines[1:-1] if lines[-1].startswith("```") else lines[1:]
            return "\n".join(inner)
        return raw

    async def _raw_call_validated(self, prompt: str, schema: dict[str, Any]) -> str:
        """Wrapper that also strips markdown fences before returning."""
        raw = await self._raw_call(prompt, schema)
        return self._extract_json_from_response(raw)
