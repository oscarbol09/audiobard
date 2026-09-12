"""Unit tests for NimClient (NVIDIA NIM LLM provider) using respx wire-level mocking."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from audiobard.llm.nim_client import NimClient

_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


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
    mock_resp = {
        "choices": [{"message": {"content": '{"name": "Alice", "age": 30}'}}]
    }

    with respx.mock:
        route = respx.post(_NIM_URL).respond(status_code=200, json=mock_resp)
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Alice", "age": 30}
        assert route.called
        assert route.calls.last.request.headers["Authorization"] == "Bearer test-nim-key"


@pytest.mark.asyncio
async def test_nim_client_markdown_fences_stripping() -> None:
    client = NimClient(api_key="test-nim-key")
    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"name\": \"Bob\", \"age\": 25}\n```"
                }
            }
        ]
    }

    with respx.mock:
        respx.post(_NIM_URL).respond(status_code=200, json=mock_resp)
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Bob", "age": 25}


@pytest.mark.asyncio
async def test_nim_client_think_tag_stripping() -> None:
    client = NimClient(api_key="test-nim-key", model="deepseek-ai/deepseek-r1")
    think_content = (
        "<think>Analyzing dialog and characters...</think>\n"
        '{"name": "Charlie", "age": 40}'
    )
    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": think_content
                }
            }
        ]
    }

    with respx.mock:
        respx.post(_NIM_URL).respond(status_code=200, json=mock_resp)
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Charlie", "age": 40}


@pytest.mark.asyncio
async def test_nim_client_response_format_fallback() -> None:
    client = NimClient(api_key="test-nim-key", model="deepseek-ai/deepseek-r1")
    mock_resp = {
        "choices": [{"message": {"content": '{"name": "Dana", "age": 28}'}}]
    }

    with respx.mock:
        route = respx.post(_NIM_URL)
        route.side_effect = [
            httpx.Response(400, json={"error": "response_format unsupported"}),
            httpx.Response(200, json=mock_resp),
        ]
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Dana", "age": 28}
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_nim_client_json_extraction_from_prose() -> None:
    client = NimClient(api_key="test-nim-key")
    prose_content = "Result:\n{\"name\": \"Elena\", \"age\": 35}\nHope this helps!"
    mock_resp = {
        "choices": [
            {
                "message": {
                    "content": prose_content
                }
            }
        ]
    }

    with respx.mock:
        respx.post(_NIM_URL).respond(status_code=200, json=mock_resp)
        result = await client._raw_call("Hello", DummySchema.model_json_schema())
        assert json.loads(result) == {"name": "Elena", "age": 35}


@pytest.mark.asyncio
async def test_nim_client_invalid_structure_error() -> None:
    client = NimClient(api_key="test-nim-key")

    with respx.mock:
        respx.post(_NIM_URL).respond(status_code=200, json={"error": "Invalid structure"})
        with pytest.raises(RuntimeError, match="Unexpected NVIDIA NIM response structure"):
            await client._raw_call("Hello", DummySchema.model_json_schema())


@pytest.mark.asyncio
async def test_nim_client_http_status_error() -> None:
    client = NimClient(api_key="test-nim-key")

    with respx.mock:
        respx.post(_NIM_URL).respond(status_code=500, text="Internal Server Error")
        with pytest.raises(RuntimeError, match=r"NVIDIA NIM API error \(HTTP 500\)"):
            await client._raw_call("Hello", DummySchema.model_json_schema())

