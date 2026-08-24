"""Tests for the FastAPI sidecar in audiobard.api."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from audiobard.api import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_progress(client: TestClient) -> None:
    response = client.get("/progress")
    assert response.status_code == 200
    assert response.json() == {"progress": 0}


def test_generate_audiobook_success(client: TestClient, tmp_path: Path) -> None:
    def write_output(input_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mp3-data")

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=write_output)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        payload: dict[str, Any] = {
            "file_base64": base64.b64encode(b"book-content").decode(),
            "file_name": "book.txt",
            "llm_provider": "ollama",
            "llm_model": "qwen2.5:7b",
            "tts_provider": "piper",
            "locale": "en-US",
        }
        response = client.post("/generate", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "output_path" in body
    assert Path(body["output_path"]).name == "book.mp3"


def test_generate_audiobook_handles_data_url(client: TestClient, tmp_path: Path) -> None:
    def write_output(input_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"data")

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=write_output)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        raw = base64.b64encode(b"book-content").decode()
        payload: dict[str, Any] = {
            "file_base64": f"data:text/plain;base64,{raw}",
            "file_name": "book.txt",
            "llm_provider": "ollama",
            "llm_model": "qwen2.5:7b",
            "tts_provider": "piper",
            "locale": "en-US",
        }
        response = client.post("/generate", json=payload)

    assert response.status_code == 200, response.text


def test_generate_audiobook_missing_output(client: TestClient, tmp_path: Path) -> None:
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(return_value=None)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
    ):
        payload: dict[str, Any] = {
            "file_base64": base64.b64encode(b"book-content").decode(),
            "file_name": "book.txt",
            "llm_provider": "ollama",
            "llm_model": "qwen2.5:7b",
            "tts_provider": "piper",
            "locale": "en-US",
        }
        response = client.post("/generate", json=payload)

    assert response.status_code == 500
    assert "output file not found" in response.json()["detail"]


def test_generate_audiobook_exception(client: TestClient) -> None:
    with patch("audiobard.api.AudioBookPipeline", side_effect=RuntimeError("boom")):
        payload: dict[str, Any] = {
            "file_base64": base64.b64encode(b"book-content").decode(),
            "file_name": "book.txt",
            "llm_provider": "ollama",
            "llm_model": "qwen2.5:7b",
            "tts_provider": "piper",
            "locale": "en-US",
        }
        response = client.post("/generate", json=payload)

    assert response.status_code == 500
    assert "Generation failed" in response.json()["detail"]
    assert "boom" in response.json()["detail"]


def test_generate_audiobook_missing_field(client: TestClient) -> None:
    response = client.post("/generate", json={"file_name": "book.txt"})
    assert response.status_code == 500
    assert "Generation failed" in response.json()["detail"]
