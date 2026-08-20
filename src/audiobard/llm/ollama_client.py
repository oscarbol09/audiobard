"""Ollama LLM client (PRIMARY — offline, no rate limits).

Uses the ``ollama`` Python SDK with ``format=<schema>`` for native JSON mode
(supported by Llama 3.1+ and Qwen 2.5+).

Install extras: ``pip install audiobard[llm-ollama]``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from audiobard.llm.base import LLMClient

if TYPE_CHECKING:
    from audiobard.persistence import PersistenceManager


class OllamaClient(LLMClient):
    """LLM client backed by a local Ollama server.

    Parameters
    ----------
    model:
        Ollama model tag, e.g. ``"qwen2.5:7b"`` or ``"llama3.1:8b"``.
    base_url:
        Ollama API base URL (default: ``http://localhost:11434``).
    temperature:
        Sampling temperature.
    max_retries:
        Maximum number of retry attempts on failure.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
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
        self.base_url = base_url

    async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
        """Send *prompt* to Ollama with ``format=schema`` for JSON mode."""
        try:
            import ollama
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "ollama package is required: pip install audiobard[llm-ollama]"
            ) from exc

        client = ollama.AsyncClient(host=self.base_url)
        response = await client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            format=schema,
            options={"temperature": self.temperature},
        )
        return response.message.content  # type: ignore[no-any-return]
