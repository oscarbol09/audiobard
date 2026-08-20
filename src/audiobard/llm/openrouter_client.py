"""OpenRouter LLM client (OPT-IN — cloud, non-commercial free tier).

Uses the OpenRouter chat completions API (OpenAI-compatible) via ``httpx``.
No extra dependencies beyond the core install.

Required env var: ``AUDIOBARD_OPENROUTER_API_KEY`` or ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from audiobard.llm.base import LLMClient

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324:free"


class OpenRouterClient(LLMClient):
    """LLM client backed by OpenRouter.

    Parameters
    ----------
    model:
        OpenRouter model identifier (default: ``deepseek/deepseek-chat-v3-0324:free``).
    api_key:
        API key.  Falls back to ``OPENROUTER_API_KEY`` then
        ``AUDIOBARD_OPENROUTER_API_KEY`` env vars.
    temperature:
        Sampling temperature.
    max_retries:
        Maximum retry attempts.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_retries=max_retries)
        self.api_key = (
            api_key
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("AUDIOBARD_OPENROUTER_API_KEY")
            or ""
        )
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found.  Set OPENROUTER_API_KEY or "
                "AUDIOBARD_OPENROUTER_API_KEY in your environment."
            )

    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        """POST to OpenRouter with ``response_format=json_object``.

        Note: OpenRouter does not guarantee JSON schema adherence for all
        models on the free tier; the base class validates via Pydantic after
        receiving the response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/oscarbol09/audiobard",
            "X-Title": "AudioBard",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected OpenRouter response structure: {data}") from exc

        # Some models wrap with markdown fences even with json_object mode.
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            inner = lines[1:-1] if lines[-1].startswith("```") else lines[1:]
            content = "\n".join(inner)

        return str(content)
