"""Unit tests for concrete LLM clients (Gemini, Ollama, OpenRouter)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx

from audiobard.llm.gemini_client import GeminiClient
from audiobard.llm.ollama_client import OllamaClient
from audiobard.llm.openrouter_client import OpenRouterClient


@pytest.mark.asyncio
async def test_gemini_client_success() -> None:
    client = GeminiClient(api_key="dummy-key")
    prompt = "Extract characters"
    schema = {"type": "object"}

    mock_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '```json\n{"characters": []}\n```'}]
                }
            }
        ]
    }

    with respx.mock:
        respx.post(url__regex=r"https://generativelanguage\.googleapis\.com/.*").respond(
            status_code=200, json=mock_resp
        )
        raw = await client._raw_call(prompt, schema)
        assert raw == '{"characters": []}'


@pytest.mark.asyncio
async def test_gemini_client_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AUDIOBARD_GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Gemini API key not found"):
        GeminiClient(api_key="")


@pytest.mark.asyncio
async def test_gemini_client_unexpected_structure() -> None:
    client = GeminiClient(api_key="dummy-key")
    with respx.mock:
        respx.post(url__regex=r"https://generativelanguage\.googleapis\.com/.*").respond(
            status_code=200, json={"unexpected": []}
        )
        with pytest.raises(RuntimeError, match="Unexpected Gemini response structure"):
            await client._raw_call("prompt", {})


@pytest.mark.asyncio
async def test_openrouter_client_success() -> None:
    client = OpenRouterClient(api_key="dummy-key")
    mock_resp = {
        "choices": [
            {"message": {"content": '```json\n{"lines": []}\n```'}}
        ]
    }
    with respx.mock:
        respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
            status_code=200, json=mock_resp
        )
        raw = await client._raw_call("prompt", {})
        assert raw == '{"lines": []}'


@pytest.mark.asyncio
async def test_openrouter_client_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AUDIOBARD_OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenRouter API key not found"):
        OpenRouterClient(api_key="")


@pytest.mark.asyncio
async def test_openrouter_client_unexpected_structure() -> None:
    client = OpenRouterClient(api_key="dummy-key")
    with respx.mock:
        respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
            status_code=200, json={"unexpected": []}
        )
        with pytest.raises(RuntimeError, match="Unexpected OpenRouter response structure"):
            await client._raw_call("prompt", {})


@pytest.mark.asyncio
async def test_ollama_client_success() -> None:
    import sys
    import types

    client = OllamaClient(model="test-model")
    mock_msg = MagicMock()
    mock_msg.content = '{"characters": []}'
    mock_resp = MagicMock()
    mock_resp.message = mock_msg

    mock_ollama = types.ModuleType("ollama")
    mock_async_client_cls = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.chat.return_value = mock_resp
    mock_async_client_cls.return_value = mock_instance
    mock_ollama.AsyncClient = mock_async_client_cls

    with patch.dict(sys.modules, {"ollama": mock_ollama}):
        raw = await client._raw_call("prompt", {})
        assert raw == '{"characters": []}'


def test_gemini_client_extract_json_unfenced() -> None:
    raw = '{"key": "value"}'
    assert GeminiClient._extract_json_from_response(raw) == '{"key": "value"}'

