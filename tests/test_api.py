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


@pytest.fixture(autouse=True)
def _isolate_audiobard_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path_factory.mktemp("audiobard_test_home")
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    test_db = fake_home / "test_audiobard.db"
    monkeypatch.setenv("AUDIOBARD_DB_PATH", str(test_db))


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
    assert Path(body["output_path"]).name.startswith("book_")
    assert Path(body["output_path"]).suffix == ".mp3"
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


def test_generate_audiobook_missing_ffmpeg_file_not_found(client: TestClient) -> None:
    """Bare FFmpeg FileNotFoundError is rewritten to the install/MP3 hint."""
    from audiobard.audio.processor import FFMPEG_MISSING_MESSAGE

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("ffmpeg executable not found on PATH")

    with patch("audiobard.api.AudioBookPipeline", side_effect=boom):
        response = client.post("/generate", json=_generate_payload("session-ffmpeg"))

    assert response.status_code == 500
    assert FFMPEG_MISSING_MESSAGE in response.json()["detail"]
    assert progress_store.get("session-ffmpeg") == PipelineProgress(
        stage="error", percent=0, message=FFMPEG_MISSING_MESSAGE
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
    session_progress = progress_store.get("session-cb")
    assert session_progress is not None
    assert session_progress.stage == "cancelled"


def test_get_book_path_success(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /book/{id}/path returns local audio file path when file exists."""
    fake_book = {
        "id": 1,
        "title": "Test Book",
        "path": "test_book.txt",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.2,
        "created_at": "2026-01-01T00:00:00Z",
    }
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda _id: fake_book if _id == 1 else None
    )

    out_dir = tmp_path / "AudioBard" / "output"
    out_dir.mkdir(parents=True)
    audio_file = out_dir / "test_book.mp3"
    audio_file.write_bytes(b"audio-data")

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    r = client.get("/book/1/path")
    assert r.status_code == 200
    assert r.json()["path"] == str(audio_file)


def test_get_book_path_404_unknown_book(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /book/{id}/path returns 404 when book ID is unknown."""
    monkeypatch.setattr("audiobard.api._get_book_by_id", lambda _id: None)
    r = client.get("/book/999/path")
    assert r.status_code == 404


def test_get_book_path_404_missing_audio_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /book/{id}/path returns 404 when audio file is missing on disk."""
    fake_book = {"id": 2, "path": "missing.txt", "title": "Missing"}
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda _id: fake_book if _id == 2 else None
    )
    r = client.get("/book/2/path")
    assert r.status_code == 404
    assert "Audio file not found" in r.json()["detail"]


def test_regenerate_book_success(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /book/{id}/regenerate starts pipeline and returns session_id."""
    source = tmp_path / "source.txt"
    source.write_text("Hello world")

    fake_book = {"id": 10, "path": str(source), "title": "Source"}
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda _id: fake_book if _id == 10 else None
    )

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(return_value=None)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        r = client.post("/book/10/regenerate", json={"session_id": "regen-session"})

    assert r.status_code == 200
    assert r.json()["session_id"] == "regen-session"
    assert r.json()["status"] == "started"


def test_regenerate_book_404_unknown_book(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /book/{id}/regenerate returns 404 when book ID is unknown."""
    monkeypatch.setattr("audiobard.api._get_book_by_id", lambda _id: None)
    r = client.post("/book/999/regenerate", json={})
    assert r.status_code == 404


def test_regenerate_book_409_source_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /book/{id}/regenerate returns 409 when source file no longer exists."""
    fake_book = {"id": 11, "path": "nonexistent_source.txt", "title": "Missing"}
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda _id: fake_book if _id == 11 else None
    )
    r = client.post("/book/11/regenerate", json={})
    assert r.status_code == 409
    assert "Source file no longer exists" in r.json()["detail"]


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


def test_delete_book_success(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /book/{book_id} deletes the book from persistence and unlinks audio file."""
    fake_book = {
        "id": 1,
        "path": str(tmp_path / "book.epub"),
        "title": "Test Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }
    audio_dir = tmp_path / "AudioBard" / "output"
    audio_dir.mkdir(parents=True)
    audio_file = audio_dir / "book.mp3"
    audio_file.write_bytes(b"audio")

    monkeypatch.setattr(
        "audiobard.api._get_book_by_id",
        lambda bid: fake_book if bid == 1 else None,
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    deleted_id = []

    class DummyPersistence:
        def delete_book(self, bid: int) -> bool:
            deleted_id.append(bid)
            return True

    monkeypatch.setattr("audiobard.api._get_persistence", lambda: DummyPersistence())

    r = client.delete("/book/1")
    assert r.status_code == 200
    assert r.json() == {"status": "deleted"}
    assert deleted_id == [1]
    assert not audio_file.exists()


def test_delete_book_not_found(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """DELETE /book/{book_id} returns 404 when book does not exist."""
    monkeypatch.setattr("audiobard.api._get_book_by_id", lambda bid: None)
    r = client.delete("/book/999")
    assert r.status_code == 404


def test_generate_audiobook_custom_output_folder(client: TestClient, tmp_path: Path) -> None:
    """POST /generate writes the output file to the configured output_folder."""
    custom_dir = tmp_path / "custom_audio_books"
    custom_dir.mkdir()
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    payload = _generate_payload("session-custom-out")
    payload["output_folder"] = str(custom_dir)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
    ):
        response = client.post("/generate", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-custom-out"
    out_path = Path(body["output_path"])
    assert out_path.parent.resolve() == custom_dir.resolve()
    assert out_path.name.startswith("book_")
    assert out_path.exists()


def test_get_library_custom_output_folder(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /library detects audio files residing in a custom output folder."""
    fake_book = {
        "id": 1,
        "path": str(tmp_path / "book.epub"),
        "title": "Custom Library Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }
    custom_dir = tmp_path / "custom_output"
    custom_dir.mkdir()
    audio_file = custom_dir / "book.mp3"
    audio_file.write_bytes(b"x" * 2000)

    monkeypatch.setattr("audiobard.api._get_all_books", lambda: [fake_book])
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    # Without output_folder parameter, file is not found in default home
    r_default = client.get("/library")
    assert r_default.status_code == 200
    assert r_default.json()[0]["has_audio"] is False

    # With output_folder parameter, file is detected in custom folder
    r_custom = client.get("/library", params={"output_folder": str(custom_dir)})
    assert r_custom.status_code == 200
    assert r_custom.json()[0]["has_audio"] is True


def test_get_book_path_custom_output_folder(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /book/{id}/path returns disk path in custom output directory."""
    fake_book = {
        "id": 1,
        "path": str(tmp_path / "book.epub"),
        "title": "Custom Path Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }
    custom_dir = tmp_path / "custom_output"
    custom_dir.mkdir()
    audio_file = custom_dir / "book.mp3"
    audio_file.write_bytes(b"x" * 2000)

    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 1 else None
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    # Without custom folder, returns 404
    r_default = client.get("/book/1/path")
    assert r_default.status_code == 404

    # With custom folder, returns correct path
    r_custom = client.get("/book/1/path", params={"output_folder": str(custom_dir)})
    assert r_custom.status_code == 200
    assert Path(r_custom.json()["path"]).resolve() == audio_file.resolve()


def test_download_book_custom_output_folder(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /book/{id}/download serves audio file from custom output directory."""
    fake_book = {
        "id": 1,
        "path": str(tmp_path / "book.epub"),
        "title": "Download Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }
    custom_dir = tmp_path / "custom_output"
    custom_dir.mkdir()
    audio_file = custom_dir / "book.mp3"
    audio_file.write_bytes(b"mp3-custom-bytes")

    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 1 else None
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    # Without custom folder, returns 404
    r_default = client.get("/book/1/download")
    assert r_default.status_code == 404

    # With custom folder, serves file
    r_custom = client.get("/book/1/download", params={"output_folder": str(custom_dir)})
    assert r_custom.status_code == 200
    assert r_custom.content == b"mp3-custom-bytes"


def test_delete_book_custom_output_folder(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /book/{id} removes audio file from custom output directory."""
    fake_book = {
        "id": 1,
        "path": str(tmp_path / "book.epub"),
        "title": "Delete Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }
    custom_dir = tmp_path / "custom_output"
    custom_dir.mkdir()
    audio_file = custom_dir / "book.mp3"
    audio_file.write_bytes(b"audio-data")

    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 1 else None
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    deleted_id: list[int] = []

    class DummyPersistence:
        def delete_book(self, bid: int) -> bool:
            deleted_id.append(bid)
            return True

    monkeypatch.setattr("audiobard.api._get_persistence", lambda: DummyPersistence())

    r = client.delete("/book/1", params={"output_folder": str(custom_dir)})
    assert r.status_code == 200
    assert r.json() == {"status": "deleted"}
    assert deleted_id == [1]
    assert not audio_file.exists()


@pytest.mark.asyncio
async def test_regenerate_book_custom_output_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /book/{id}/regenerate saves output to custom output directory."""
    from audiobard.api import regenerate_book

    source_file = tmp_path / "book.epub"
    source_file.write_bytes(b"epub-content")
    custom_dir = tmp_path / "custom_output"

    fake_book = {
        "id": 1,
        "path": str(source_file),
        "title": "Regenerate Book",
        "total_paragraphs": 10,
        "total_words": 100,
        "dialog_ratio": 0.5,
        "created_at": "2026-08-25T10:00:00",
    }

    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 1 else None
    )

    run_event = asyncio.Event()
    captured_out: list[Path] = []

    async def _capture_run(src: Path, out: Path, **kwargs: Any) -> None:
        captured_out.append(out)
        run_event.set()

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_capture_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
    ):
        result = await regenerate_book(1, {"output_folder": str(custom_dir)})
        await asyncio.wait_for(run_event.wait(), timeout=2.0)

    assert result["status"] == "started"
    assert len(captured_out) == 1
    assert captured_out[0].resolve() == (custom_dir / "book.mp3").resolve()


def test_generate_audiobook_persists_uploaded_file(
    client: TestClient, tmp_path: Path
) -> None:
    """POST /generate saves uploaded file to persistent AudioBard/books storage."""
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload("session-persist"))

    assert response.status_code == 200, response.text
    books_dir = tmp_path / "AudioBard" / "books"
    persisted = list(books_dir.glob("book_*.txt"))
    assert len(persisted) == 1
    assert persisted[0].read_bytes() == b"book-content"
    body = response.json()
    assert Path(body["output_path"]).stem == persisted[0].stem


def test_regenerate_book_succeeds_for_uploaded_book(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /book/{id}/regenerate finds the book in persistent storage and starts pipeline."""
    books_dir = tmp_path / "AudioBard" / "books"
    books_dir.mkdir(parents=True)
    source_file = books_dir / "persisted_novel.txt"
    source_file.write_text("Chapter 1: It was the best of times.", encoding="utf-8")

    fake_book = {"id": 42, "path": str(source_file), "title": "Persisted Novel"}
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda _id: fake_book if _id == 42 else None
    )

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(return_value=None)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        r = client.post("/book/42/regenerate", json={"session_id": "regen-success"})

    assert r.status_code == 200
    assert r.json()["status"] == "started"


def test_delete_book_removes_uploaded_source_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /book/{id} removes stored book file when it resides inside books_dir."""
    books_dir = tmp_path / "AudioBard" / "books"
    books_dir.mkdir(parents=True)
    uploaded_source = books_dir / "uploaded_book.epub"
    uploaded_source.write_bytes(b"epub-content")

    audio_dir = tmp_path / "AudioBard" / "output"
    audio_dir.mkdir(parents=True)
    audio_file = audio_dir / "uploaded_book.mp3"
    audio_file.write_bytes(b"audio-content")

    fake_book = {
        "id": 5,
        "path": str(uploaded_source),
        "title": "Uploaded Book",
    }
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 5 else None
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    class DummyPersistence:
        def delete_book(self, _bid: int) -> bool:
            return True

    monkeypatch.setattr("audiobard.api._get_persistence", lambda: DummyPersistence())

    r = client.delete("/book/5")
    assert r.status_code == 200
    assert not audio_file.exists()
    assert not uploaded_source.exists()


def test_delete_book_preserves_external_source_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE /book/{id} does not delete external source files outside books_dir."""
    external_dir = tmp_path / "external_library"
    external_dir.mkdir(parents=True)
    external_source = external_dir / "my_precious_book.epub"
    external_source.write_bytes(b"important-user-file")

    audio_dir = tmp_path / "AudioBard" / "output"
    audio_dir.mkdir(parents=True)
    audio_file = audio_dir / "my_precious_book.mp3"
    audio_file.write_bytes(b"audio-content")

    fake_book = {
        "id": 6,
        "path": str(external_source),
        "title": "Precious Book",
    }
    monkeypatch.setattr(
        "audiobard.api._get_book_by_id", lambda bid: fake_book if bid == 6 else None
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    class DummyPersistence:
        def delete_book(self, _bid: int) -> bool:
            return True

    monkeypatch.setattr("audiobard.api._get_persistence", lambda: DummyPersistence())

    r = client.delete("/book/6")
    assert r.status_code == 200
    assert not audio_file.exists()
    assert external_source.exists()


def test_generate_audiobook_unregistered_failure_cleans_up_file(
    client: TestClient, tmp_path: Path
) -> None:
    """When pipeline raises before registering the book, orphan upload file is removed."""
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=ValueError("corrupt book content"))

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        response = client.post("/generate", json=_generate_payload("session-fail-cleanup"))

    assert response.status_code == 500
    books_dir = tmp_path / "AudioBard" / "books"
    if books_dir.exists():
        assert list(books_dir.glob("book_*.txt")) == []


def test_generate_audiobook_unique_filenames_no_collision(
    client: TestClient, tmp_path: Path
) -> None:
    """Repeated uploads of the same filename produce distinct source files and output paths."""
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        r1 = client.post("/generate", json=_generate_payload("session-1"))
        r2 = client.post("/generate", json=_generate_payload("session-2"))

    assert r1.status_code == 200
    assert r2.status_code == 200
    p1 = r1.json()["output_path"]
    p2 = r2.json()["output_path"]
    assert p1 != p2
    books_dir = tmp_path / "AudioBard" / "books"
    persisted = list(books_dir.glob("book_*.txt"))
    assert len(persisted) == 2
    assert persisted[0] != persisted[1]


def test_generate_audiobook_sanitizes_path_traversal(
    client: TestClient, tmp_path: Path
) -> None:
    """Path traversal in filename and session_id is safely contained within books_dir."""
    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        payload = _generate_payload()
        payload["file_name"] = "../../evil.txt"
        payload["session_id"] = "../../escape_id"
        response = client.post("/generate", json=payload)

    assert response.status_code == 200
    books_dir = tmp_path / "AudioBard" / "books"
    persisted = list(books_dir.glob("evil_*.txt"))
    assert len(persisted) == 1
    assert persisted[0].parent.resolve() == books_dir.resolve()


def test_generate_audiobook_preserves_display_title(
    client: TestClient, tmp_path: Path
) -> None:
    """Original book stem with punctuation and spaces is preserved in persistence."""
    from audiobard.api import _get_persistence
    from audiobard.parser.base import ParserStats

    async def _stub_with_db(input_path: Path, output_path: Path, **_kwargs: Any) -> None:
        _stub_pipeline_run(input_path, output_path)
        persistence = _get_persistence()
        persistence.get_or_create_book(
            input_path,
            "temporary_title",
            ParserStats(total_paragraphs=5, total_words=50, dialog_ratio=0.2),
        )

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_stub_with_db)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        payload = _generate_payload("session-title")
        payload["file_name"] = "Alice's Adventures in Wonderland.txt"
        response = client.post("/generate", json=payload)

    assert response.status_code == 200
    r = client.get("/library")
    assert r.status_code == 200
    books = r.json()
    assert len(books) == 1
    assert books[0]["title"] == "Alice's Adventures in Wonderland"


def test_repeated_upload_registering_pipeline_cleans_superseded_files(
    client: TestClient, tmp_path: Path
) -> None:
    """Repeated uploads with registering pipeline clean up older source, output, and db record."""
    from audiobard.api import _get_persistence
    from audiobard.parser.base import ParserStats

    async def _registering_pipeline_run(
        input_path: Path, output_path: Path, **_kwargs: Any
    ) -> None:
        _stub_pipeline_run(input_path, output_path)
        persistence = _get_persistence()
        persistence.get_or_create_book(
            input_path,
            input_path.stem,
            ParserStats(total_paragraphs=10, total_words=100, dialog_ratio=0.1),
        )

    fake_pipeline = MagicMock()
    fake_pipeline.run = AsyncMock(side_effect=_registering_pipeline_run)

    with (
        patch("audiobard.api.AudioBookPipeline", return_value=fake_pipeline),
        patch("audiobard.api.AudioBardConfig"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        r1 = client.post("/generate", json=_generate_payload("session-rep-1"))
        assert r1.status_code == 200
        out1 = Path(r1.json()["output_path"])
        assert out1.exists()

        books_dir = tmp_path / "AudioBard" / "books"
        source_files_1 = list(books_dir.glob("book_*.txt"))
        assert len(source_files_1) == 1

        # Second upload with the same book title/file_name
        r2 = client.post("/generate", json=_generate_payload("session-rep-2"))
        assert r2.status_code == 200
        out2 = Path(r2.json()["output_path"])
        assert out2.exists()
        assert out1 != out2

        # The superseded first output file and source file should be cleaned up
        assert not out1.exists()
        source_files_2 = list(books_dir.glob("book_*.txt"))
        assert len(source_files_2) == 1
        assert source_files_2[0] != source_files_1[0]

        # Library should have only the active, single book record
        r_lib = client.get("/library")
        assert r_lib.status_code == 200
        books = r_lib.json()
        assert len(books) == 1
        assert books[0]["title"] == "book"

        # Deleting the book removes the active files and leaves zero orphans
        del_resp = client.delete(f"/book/{books[0]['id']}")
        assert del_resp.status_code == 200
        assert not out2.exists()
        assert list(books_dir.glob("book_*.txt")) == []
