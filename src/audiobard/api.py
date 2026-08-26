"""FastAPI application for AudioBard."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from audiobard.config import AudioBardConfig
from audiobard.pipeline import AudioBookPipeline
from audiobard.progress import PipelineProgress

app = FastAPI(title="AudioBard API", version="0.1.0")

LLMChoice = Literal["ollama", "gemini", "openrouter", "nim"]
TTSChoice = Literal["piper", "edge"]


class ProgressStore:
    """Thread-safe in-memory map of session_id -> latest PipelineProgress.

    Lives in the FastAPI process for the duration of one audiobook
    generation. The Tauri shell polls /progress?session_id=... once a
    second while generation runs; a periodic poll after success or
    failure reports *stage="complete"* until the Tauri shell stops
    asking. Sessions are never evicted: the sidecar restarts with the
    app, so memory pressure is bounded by session count during one run.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, PipelineProgress] = {}
        self._cancelled: set[str] = set()

    def update(self, session_id: str, progress: PipelineProgress) -> None:
        with self._lock:
            self._entries[session_id] = progress

    def get(self, session_id: str) -> PipelineProgress | None:
        with self._lock:
            return self._entries.get(session_id)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._entries.pop(session_id, None)

    def size(self) -> int:
        """Test/diagnostic hook: number of tracked sessions."""
        with self._lock:
            return len(self._entries)

    def clear_state_for_tests(self) -> None:
        """Drop every tracked session; only used by the test suite."""
        with self._lock:
            self._entries.clear()
            self._cancelled.clear()

    def cancel(self, session_id: str) -> None:
        """Mark *session_id* as cancelled.

        Idempotent: calling cancel twice for the same session is
        harmless. The pipeline checks the flag inside its progress
        callback on every emit and raises asyncio.CancelledError to
        unwind the run. Cancelling a session that already finished
        is a no-op: the pipeline is no longer running, so the flag
        "never gets checked."
        """
        with self._lock:
            self._cancelled.add(session_id)

    def is_cancelled(self, session_id: str) -> bool:
        """True if cancel() has been called for *session_id*.

        The pipeline reads this on every progress emit so a
        long-running synthesis chunk can still abort between
        awaits when the cancel request lands mid-chunk.
        """
        with self._lock:
            return session_id in self._cancelled


progress_store = ProgressStore()


def _get_persistence() -> Any:
    """Create a PersistenceManager with default config."""
    from audiobard.config import AudioBardConfig
    from audiobard.persistence import PersistenceManager

    config = AudioBardConfig()
    return PersistenceManager(config.db_path)


def _get_all_books() -> list[dict[str, Any]]:
    """Return all books with latest run timestamp and stats."""
    persistence = _get_persistence()
    return persistence.get_all_books()  # type: ignore[no-any-return]


def _get_book_by_id(book_id: int) -> dict[str, Any] | None:
    """Get a single book by ID."""
    persistence = _get_persistence()
    books: list[dict[str, Any]] = persistence.get_all_books()
    for book in books:
        if book["id"] == book_id:
            return book
    return None


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — Tauri queries this on startup."""
    return {"status": "ok"}


@app.get("/progress")
async def get_progress(session_id: str | None = None) -> dict[str, Any]:
    """Return the latest progress for *session_id*.

    A request without a session_id returns a synthetic zero state so a
    misbehaving client cannot crash the sidecar; missing sessions are
    also reported as zero rather than 404 because polling a finished
    or unknown session is a legitimate use case (the UI just shows an
    idle bar).
    """
    if session_id is None:
        return {"stage": "idle", "percent": 0, "message": ""}
    progress = progress_store.get(session_id)
    if progress is None:
        return {"stage": "idle", "percent": 0, "message": ""}
    return {
        "stage": progress.stage,
        "percent": progress.percent,
        "message": progress.message,
    }

@app.post("/cancel")
async def cancel_generation(request: dict[str, Any]) -> dict[str, str]:
    """Mark a generation session as cancelled.

    Body fields:
        session_id: The opaque token returned by /generate (or
        auto-generated when missing on that endpoint).

    The handler always returns {"status": "cancelled"}:
    the Tauri shell calls this idempotently, and the contract
    is that the pipeline will see the flag on its next progress
    emit and unwind on its own. An empty or missing session_id
    is treated the same way so a stale Cancel click does not
    produce a 4xx for the user.
    """
    session_id = str(request.get("session_id") or "")
    if session_id:
        progress_store.cancel(session_id)
    return {"status": "cancelled"}


@app.get("/library")
async def get_library() -> list[dict[str, Any]]:
    """Return all generated books with metadata."""
    books = _get_all_books()
    output_dir = Path.home() / "AudioBard" / "output"
    result = []
    for book in books:
        stem = Path(book["path"]).stem if book.get("path") else f"book_{book['id']}"
        audio_file = output_dir / f"{stem}.mp3"
        has_audio = audio_file.exists() and audio_file.stat().st_size > 1024
        result.append(
            {
                "id": book["id"],
                "title": book["title"],
                "path": book["path"],
                "total_paragraphs": book["total_paragraphs"],
                "total_words": book["total_words"],
                "dialog_ratio": book["dialog_ratio"],
                "created_at": book["created_at"],
                "has_audio": has_audio,
            }
        )
    return result


@app.get("/book/{book_id}")
async def get_book(book_id: int) -> dict[str, Any]:
    """Get detailed book information."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return {
        "id": book["id"],
        "title": book["title"],
        "path": book["path"],
        "total_paragraphs": book["total_paragraphs"],
        "total_words": book["total_words"],
        "dialog_ratio": book["dialog_ratio"],
        "created_at": book["created_at"],
    }


@app.get("/book/{book_id}/download")
async def download_book(book_id: int) -> FileResponse:
    """Download the generated audiobook file."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    # Reconstruct output path (same logic as generate_audiobook)
    output_dir = Path.home() / "AudioBard" / "output"
    output_path = output_dir / f"{Path(book['path']).stem}.mp3"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        output_path,
        media_type="audio/mpeg",
        filename=f"{book['title']}.mp3",
    )


@app.get("/book/{book_id}/path")
async def get_book_path(book_id: int) -> dict[str, str]:
    """Return the local filesystem path of the generated audio file."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    output_dir = Path.home() / "AudioBard" / "output"
    output_path = output_dir / f"{Path(book['path']).stem}.mp3"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    return {"path": str(output_path)}


@app.delete("/book/{book_id}")
async def delete_book(book_id: int) -> dict[str, str]:
    """Delete a book from the library and remove any generated audio files."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    output_dir = Path.home() / "AudioBard" / "output"
    output_path = output_dir / f"{Path(book['path']).stem}.mp3"
    if output_path.exists():
        with contextlib.suppress(OSError):
            output_path.unlink()

    manager = _get_persistence()
    manager.delete_book(book_id)
    return {"status": "deleted"}



@app.post("/book/{book_id}/regenerate")
async def regenerate_book(book_id: int, request: dict[str, Any]) -> dict[str, str]:
    """Regenerate audiobook reusing the stored source file and settings."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    source_path = Path(book["path"])
    if not source_path.exists():  # noqa: ASYNC240
        raise HTTPException(
            status_code=409,
            detail=f"Source file no longer exists on disk: {source_path}",
        )

    session_id = str(request.get("session_id") or uuid.uuid4().hex)
    llm_provider = cast(LLMChoice, str(request.get("llm_provider", "ollama")))
    llm_model = str(request.get("llm_model", "qwen2.5:7b"))
    tts_provider = cast(TTSChoice, str(request.get("tts_provider", "piper")))
    locale = str(request.get("locale", "en_US"))

    output_dir = Path.home() / "AudioBard" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.mp3"

    config = AudioBardConfig(
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=str(request.get("llm_base_url") or "http://localhost:11434"),
        openrouter_api_key=str(request.get("openrouter_api_key") or ""),
        gemini_api_key=str(request.get("gemini_api_key") or ""),
        nim_api_key=str(request.get("nim_api_key") or ""),
        tts_provider=tts_provider,
        tts_locale=locale,
    )

    async def _run() -> None:
        def on_progress(progress: PipelineProgress) -> None:
            progress_store.update(session_id, progress)
            if progress_store.is_cancelled(session_id):
                raise asyncio.CancelledError()

        pipeline = AudioBookPipeline(config)
        await pipeline.run(
            source_path, output_path, resume=False, progress_callback=on_progress
        )

    asyncio.create_task(_run())
    return {"session_id": session_id, "status": "started"}


@app.post("/clear_cache")
async def clear_cache() -> dict[str, str]:
    """Delete all cached TTS audio clips and LLM responses."""
    config = AudioBardConfig()
    if config.cache_dir.exists():
        shutil.rmtree(config.cache_dir)
        config.cache_dir.mkdir(parents=True, exist_ok=True)
    return {"status": "ok", "message": "Cache cleared"}


@app.post("/generate")
async def generate_audiobook(request: dict[str, Any]) -> dict[str, str]:
    """Generate audiobook from an uploaded base64-encoded file.

    Body fields:
        session_id: Optional opaque token; auto-generated when missing.
            The same value must be passed to /progress to receive
            updates. Clients that omit it get back a per-request id and
            are expected to surface it to the polling code.
        file_base64, file_name, llm_provider, llm_model, tts_provider,
            locale: Book payload and pipeline configuration.
    """
    session_id = str(request.get("session_id") or uuid.uuid4().hex)

    try:
        file_base64 = str(request["file_base64"])
        file_name = str(request["file_name"])
        llm_provider = cast(LLMChoice, str(request["llm_provider"]))
        llm_model = str(request["llm_model"])
        tts_provider = cast(TTSChoice, str(request["tts_provider"]))
        locale = str(request["locale"])

        raw_b64 = file_base64.split(",")[1] if "," in file_base64 else file_base64
        file_bytes = base64.b64decode(raw_b64)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_path = tmp_path / file_name
            input_path.write_bytes(file_bytes)

            output_dir = tmp_path / "output"
            output_dir.mkdir()

            config = AudioBardConfig(
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_base_url=str(request.get("llm_base_url") or "http://localhost:11434"),
                openrouter_api_key=str(request.get("openrouter_api_key") or ""),
                gemini_api_key=str(request.get("gemini_api_key") or ""),
                nim_api_key=str(request.get("nim_api_key") or ""),
                tts_provider=tts_provider,
                tts_locale=locale,
            )
            pipeline = AudioBookPipeline(config)

            output_path = output_dir / f"{input_path.stem}.mp3"

            # Mark the session as running before we await the pipeline so
            # the first poll (which may already be in flight on the Tauri
            # side) sees a non-zero state instead of an idle placeholder.
            progress_store.update(
                session_id,
                PipelineProgress(stage="queued", percent=0, message="Starting"),
            )

            def on_progress(progress: PipelineProgress) -> None:
                progress_store.update(session_id, progress)
                if progress_store.is_cancelled(session_id):
                    raise asyncio.CancelledError()

            try:
                await pipeline.run(input_path, output_path, progress_callback=on_progress)
            except asyncio.CancelledError:
                progress_store.update(
                    session_id,
                    PipelineProgress(
                        stage="cancelled",
                        percent=0,
                        message="Cancelled by user",
                    ),
                )
                raise HTTPException(
                    status_code=499,
                    detail="Generation cancelled by user",
                ) from None

            if not output_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail="Audiobook generation failed - output file not found",
                )

            permanent_dir = Path.home() / "AudioBard" / "output"
            permanent_dir.mkdir(parents=True, exist_ok=True)
            permanent_path = permanent_dir / output_path.name
            # shutil.copy2 in this thread pool keeps the sidecar responsive.
            await asyncio.to_thread(shutil.copy2, output_path, permanent_path)
            return {"session_id": session_id, "output_path": str(permanent_path)}

    except HTTPException:
        raise
    except Exception as exc:
        # Surface the failure on the progress channel so the Tauri UI can
        # render it without parsing a one-off error path.
        progress_store.update(
            session_id,
            PipelineProgress(stage="error", percent=0, message=str(exc)),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {exc}",
        ) from exc
