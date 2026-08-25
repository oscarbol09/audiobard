"""Tests for the FastAPI sidecar in audiobard.api."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from audiobard.api import ProgressStore, app, progress_store
from audiobard.progress import PipelineProgress


@pytest.fixture(autouse=True)
def _clear_progress_store() -> None:
    progress_store.clear_state_for_tests()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_progress_default_when_no_session(client: TestClient) -> None:
    response = client.get("/progress")
    assert response.status_code == 200
    assert response.json() == {"stage": "idle", "percent": 0, "message": ""}


def test_progress_default_when_unknown_session(client: TestClient) -> None:
    response = client.get("/progress", params={"session_id": "does-not-exist"})
    assert response.status_code == 200
    assert response.json() == {"stage": "idle", "percent": 0, "message": ""}


def test_progress_returns_latest_update(client: TestClient) -> None:
    progress_store.update("abc", PipelineProgress(stage="synthesis", percent=42, message="ok"))
    response = client.get("/progress", params={"session_id": "abc"})
    assert response.status_code == 200
    assert response.json() == {"stage": "synthesis", "percent": 42, "message": "ok"}


def test_progress_store_roundtrip() -> None:
    store = ProgressStore()
    store.update("a", PipelineProgress(stage="parsing", percent=10, message="x"))
    store.update("b", PipelineProgress(stage="synthesis", percent=50, message="y"))
    assert store.size() == 2
    assert store.get("a") == PipelineProgress(stage="parsing", percent=10, message="x")
    assert store.get("b") == PipelineProgress(stage="synthesis", percent=50, message="y")
    store.clear("a")
    assert store.get("a") is None
    assert store.size() == 1


def test_progress_store_thread_safe() -> None:
    import threading

    store = ProgressStore()

    def writer(prefix: str) -> None:
        for i in range(200):
            store.update(
                f"{prefix}-{i}",
                PipelineProgress(stage="x", percent=i % 101, message="m"),
            )

    threads = [threading.Thread(target=writer, args=(f"t{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.size() == 4 * 200


def _stub_pipeline_run(input_path: Path, output_path: Path, **_kwargs: Any) -> None:
    """Stand-in for AudioBookPipeline.run that writes a fake output file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake-mp3-data")


def _generate_payload(session_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "file_base64": base64.b64encode(b"book-content").decode(),
        "file_name": "book.txt",
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
        "tts_provider": "piper",
        "locale": "en-US",
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


def test_generate_audiobook_success(client: TestClient, tmp_path: Path) -> None:
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload("session-A"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-A"
    assert "output_path" in body
    assert Path(body["output_path"]).name == "book.mp3"
    # Pipeline should have been invoked with a progress callback that
    # updates the store for the same session.
    fake_pipeline.run.assert_awaited_once()
    call_kwargs = fake_pipeline.run.await_args.kwargs
    assert "progress_callback" in call_kwargs
    cb = call_kwargs["progress_callback"]
    cb(PipelineProgress(stage="synthesis", percent=33, message="x"))
    assert progress_store.get("session-A") == PipelineProgress(
        stage="synthesis", percent=33, message="x"
    )


def test_generate_audiobook_auto_generates_session(client: TestClient, tmp_path: Path) -> None:
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert "session_id" in body and len(body["session_id"]) >= 16


def test_generate_audiobook_handles_data_url(client: TestClient, tmp_path: Path) -> None:
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        raw = base64.b64encode(b"book-content").decode()
        payload = _generate_payload()
        payload["file_base64"] = f"data:text/plain;base64,{raw}"
        response = client.post("/generate", json=payload)

    assert response.status_code == 200, response.text


def test_generate_audiobook_missing_output(client: TestClient) -> None:
    def no_output(*_args: Any, **_kwargs: Any) -> None:
        return None

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=no_output)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
    ):
        response = client.post("/generate", json=_generate_payload("session-noop"))

    assert response.status_code == 500
    assert "output file not found" in response.json()["detail"]


def test_generate_audiobook_exception(client: TestClient) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("boom")

    with patch("audiobard.api.AudioBookPipeline", side_effect=boom):
        response = client.post("/generate", json=_generate_payload("session-err"))

    assert response.status_code == 500
    assert "Generation failed" in response.json()["detail"]
    assert "boom" in response.json()["detail"]
    assert progress_store.get("session-err") == PipelineProgress(
        stage="error", percent=0, message="boom"
    )


def test_generate_audiobook_missing_field(client: TestClient) -> None:
    response = client.post("/generate", json={"file_name": "book.txt"})
    assert response.status_code == 500
    assert "Generation failed" in response.json()["detail"]


def test_progress_store_cancel_and_is_cancelled() -> None:
    store = ProgressStore()
    assert not store.is_cancelled("abc")
    store.cancel("abc")
    assert store.is_cancelled("abc")
    store.cancel("abc")
    assert store.is_cancelled("abc")


def test_progress_store_cancel_does_not_affect_others() -> None:
    store = ProgressStore()
    store.cancel("a")
    assert store.is_cancelled("a")
    assert not store.is_cancelled("b")


def test_cancel_endpoint_marks_session(client: TestClient) -> None:
    response = client.post("/cancel", json={"session_id": "sess-cancel"})
    assert response.status_code == 200
    assert response.json() == {"status": "cancelled"}
    assert progress_store.is_cancelled("sess-cancel")


def test_cancel_endpoint_unknown_session_is_idempotent(client: TestClient) -> None:
    response = client.post("/cancel", json={"session_id": "never-existed"})
    assert response.status_code == 200
    assert response.json() == {"status": "cancelled"}


def test_cancel_endpoint_missing_session_id_is_idempotent(client: TestClient) -> None:
    response = client.post("/cancel", json={})
    assert response.status_code == 200
    assert response.json() == {"status": "cancelled"}


def test_generate_audiobook_cancelled_via_callback(client: TestClient, tmp_path: Path) -> None:
    fake_pipeline = MagicMock()

    async def cancel_mid_run(input_path: Path, output_path: Path, **_kwargs: Any) -> None:
        progress_callback = _kwargs["progress_callback"]
        progress_callback(PipelineProgress(stage="synthesis", percent=10, message="chunk 1"))
        progress_callback(PipelineProgress(stage="synthesis", percent=20, message="chunk 2"))
        raise asyncio.CancelledError()

    fake_pipeline.run = AsyncMock(side_effect=cancel_mid_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload("session-cancel"))

    assert response.status_code == 499
    assert "cancelled" in response.json()["detail"]
    assert progress_store.get("session-cancel") == PipelineProgress(
        stage="cancelled", percent=0, message="Cancelled by user"
    )


def test_generate_audiobook_cancelled_writes_stage_before_http_exception(
    client: TestClient, tmp_path: Path
) -> None:
    fake_pipeline = MagicMock()

    async def cancel_then_check_store(input_path: Path, output_path: Path, **_kwargs: Any) -> None:
        progress_callback = _kwargs["progress_callback"]
        progress_store.cancel("session-cb")
        progress_callback(PipelineProgress(stage="synthesis", percent=5, message="x"))

    fake_pipeline.run = AsyncMock(side_effect=cancel_then_check_store)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload("session-cb"))

    assert response.status_code == 499
    assert progress_store.get("session-cb").stage == "cancelled"


def test_clear_cache_removes_cache_dir(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /clear_cache deletes cache contents and returns ok."""
    fake_cache = tmp_path / "cache"
    fake_cache.mkdir()
    (fake_cache / "clip.mp3").write_bytes(b"fake")
    monkeypatch.setattr(
        "audiobard.api.AudioBardConfig",
        lambda: type("C", (), {"cache_dir": fake_cache})(),
    )
    r = client.post("/clear_cache")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert not (fake_cache / "clip.mp3").exists()
    assert fake_cache.exists()


def test_clear_cache_ok_when_no_cache_dir(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /clear_cache is idempotent when cache dir does not exist."""
    missing = tmp_path / "nonexistent"
    monkeypatch.setattr(
        "audiobard.api.AudioBardConfig",
        lambda: type("C", (), {"cache_dir": missing})(),
    )
    r = client.post("/clear_cache")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
