"""LLM sub-package.

Public surface::

    from audiobard.llm import LLMClient, OllamaClient, GeminiClient, OpenRouterClient
"""

from __future__ import annotations

from audiobard.llm.base import LLMClient
from audiobard.llm.gemini_client import GeminiClient
from audiobard.llm.ollama_client import OllamaClient
from audiobard.llm.openrouter_client import OpenRouterClient

__all__ = ["GeminiClient", "LLMClient", "OllamaClient", "OpenRouterClient"]
