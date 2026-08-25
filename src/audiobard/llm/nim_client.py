"""NVIDIA NIM LLM client (OPT-IN — cloud, NVIDIA Inference Microservices).

Uses NVIDIA NIM chat completions API (OpenAI-compatible) via ``httpx``.
No extra dependencies beyond the core install.

Required env var: ``AUDIOBARD_NIM_API_KEY`` or ``NVIDIA_NIM_API_KEY`` or ``NIM_API_KEY``.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

import httpx

from audiobard.llm.base import LLMClient

if TYPE_CHECKING:
    from audiobard.persistence import PersistenceManager

_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"


class NimClient(LLMClient):
    """LLM client backed by NVIDIA NIM.

    Parameters
    ----------
    model:
        NVIDIA NIM model identifier (default: ``meta/llama-3.3-70b-instruct``).
    api_key:
        API key. Falls back to ``NVIDIA_NIM_API_KEY``, ``AUDIOBARD_NIM_API_KEY``,
        or ``NIM_API_KEY`` env vars.
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
        persistence: PersistenceManager | None = None,
    ) -> None:
        super().__init__(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            persistence=persistence,
        )
        self.api_key = (
            api_key
            or os.environ.get("NVIDIA_NIM_API_KEY")
            or os.environ.get("AUDIOBARD_NIM_API_KEY")
            or os.environ.get("NIM_API_KEY")
            or ""
        )
        if not self.api_key:
            raise ValueError(
                "NVIDIA NIM API key not found. Set NVIDIA_NIM_API_KEY, "
                "AUDIOBARD_NIM_API_KEY, or NIM_API_KEY in your environment."
            )

    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        """POST to NVIDIA NIM with ``response_format=json_object`` and fallback."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(_NIM_URL, json=payload, headers=headers)
            if response.status_code in (400, 422):
                # Some NIM models (like deepseek-r1) do not support response_format
                payload_no_rf: dict[str, Any] = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                }
                response = await client.post(_NIM_URL, json=payload_no_rf, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected NVIDIA NIM response structure: {data}") from exc

        # 1. Strip reasoning blocks like <think>...</think> (common in DeepSeek R1 / Kimi)
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # 2. Strip markdown code fences (```json ... ```)
        if content.startswith("```"):
            lines = content.splitlines()
            inner = lines[1:-1] if lines[-1].startswith("```") else lines[1:]
            content = "\n".join(inner).strip()

        # 3. Extract JSON substring if surrounded by extra commentary
        if not (content.startswith("{") and content.endswith("}")):
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                content = content[start : end + 1]

        return str(content)
