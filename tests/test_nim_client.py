"""Unit tests for NimClient (NVIDIA NIM LLM provider)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from audiobard.llm.nim_client import NimClient


class DummySchema(BaseModel):
    name: str
    age: int


@pytest.mark.asyncio
async def test_nim_client_init_error() -> None:
    with pytest.raises(ValueError, match="NVIDIA NIM API key not found"):
        NimClient(api_key="")


@pytest.mark.asyncio
async def test_nim_client_raw_call_success() -> None:
    client = NimClient(api_key="test-nim-key", model="meta/llama-3.3-70b-instruct")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "choices": [{"message": {"content": '{"name": "Alice", "age": 30}'}}]
    }
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Alice", "age": 30}
        mock_post.assert_called_once()
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-nim-key"


@pytest.mark.asyncio
async def test_nim_client_markdown_fences_stripping() -> None:
    client = NimClient(api_key="test-nim-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"name\": \"Bob\", \"age\": 25}\n```"
                }
            }
        ]
    }
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Bob", "age": 25}


@pytest.mark.asyncio
async def test_nim_client_think_tag_stripping() -> None:
    client = NimClient(api_key="test-nim-key", model="deepseek-ai/deepseek-r1")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    think_content = (
        "<think>Analyzing dialog and characters...</think>\n"
        "{\"name\": \"Charlie\", \"age\": 40}"
    )
    mock_response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": think_content
                }
            }
        ]
    }
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Charlie", "age": 40}


@pytest.mark.asyncio
async def test_nim_client_response_format_fallback() -> None:
    client = NimClient(api_key="test-nim-key", model="deepseek-ai/deepseek-r1")

    mock_response_fail = AsyncMock()
    mock_response_fail.status_code = 400

    mock_response_ok = AsyncMock()
    mock_response_ok.status_code = 200
    mock_response_ok.json = lambda: {
        "choices": [{"message": {"content": '{"name": "Dana", "age": 28}'}}]
    }
    mock_response_ok.raise_for_status = AsyncMock()

    patcher = patch("httpx.AsyncClient.post", side_effect=[mock_response_fail, mock_response_ok])
    with patcher as mock_post:
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Dana", "age": 28}
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_nim_client_json_extraction_from_prose() -> None:
    client = NimClient(api_key="test-nim-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    prose_content = "Result:\n{\"name\": \"Elena\", \"age\": 35}\nHope this helps!"
    mock_response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": prose_content
                }
            }
        ]
    }
    mock_response.raise_for_status = AsyncMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Elena", "age": 35}


@pytest.mark.asyncio
async def test_nim_client_invalid_structure_error() -> None:
    client = NimClient(api_key="test-nim-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"error": "Invalid structure"}
    mock_response.raise_for_status = AsyncMock()

    with (
        patch("httpx.AsyncClient.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="Unexpected NVIDIA NIM response structure"),
    ):
        await client._raw_call("Hello", DummySchema.model_json_schema())
