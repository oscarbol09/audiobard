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

from audiobard.audio.processor import FFMPEG_MISSING_MESSAGE
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
    books: list[dict[str, Any]] = _get_all_books()
    for book in books:
        if book["id"] == book_id:
            return book
    return None


def _get_books_dir() -> Path:
    """Return the persistent directory for uploaded books, ensuring it exists."""
    books_dir = Path.home() / "AudioBard" / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    return books_dir


def _get_output_dir(custom_path: str | Path | None = None) -> Path:
    """Return the output directory, prioritizing a configured custom path."""
    if custom_path:
        custom_str = str(custom_path).strip()
        if custom_str:
            out = Path(custom_str).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            return out
    output_dir = Path.home() / "AudioBard" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _find_audio_file(stem: str, custom_output: str | Path | None = None) -> Path:
    """Locate an audiobook file, checking custom output dir before default."""
    if custom_output:
        custom_file = _get_output_dir(custom_output) / f"{stem}.mp3"
        if custom_file.exists():
            return custom_file
    return _get_output_dir() / f"{stem}.mp3"


def _save_uploaded_book(books_dir: Path, clean_name: str, file_bytes: bytes) -> Path:
    """Write uploaded book bytes atomically into books_dir."""
    input_path = books_dir / clean_name
    if input_path.exists():
        raise FileExistsError(f"Destination file already exists: {input_path}")
    with tempfile.NamedTemporaryFile(
        dir=books_dir,
        prefix=f".{clean_name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_input:
        temp_input_path = Path(temp_input.name)

    try:
        temp_input_path.write_bytes(file_bytes)
        if input_path.exists():
            raise FileExistsError(f"Destination file already exists: {input_path}")
        temp_input_path.replace(input_path)
    except BaseException:
        with contextlib.suppress(OSError):
            temp_input_path.unlink(missing_ok=True)
        raise
    return input_path


def _delete_book_source(source_path: Path) -> None:
    """Remove stored book file if inside books_dir."""
    books_dir = _get_books_dir().resolve()
    resolved = source_path.resolve()
    with contextlib.suppress(ValueError, OSError):
        if resolved.is_relative_to(books_dir) and resolved.is_file():
            resolved.unlink(missing_ok=True)


def _cleanup_book_files(
    book: dict[str, Any], custom_output: str | Path | None = None
) -> None:
    """Remove generated audio file and stored uploaded book if present."""
    stem = Path(book["path"]).stem if book.get("path") else f"book_{book['id']}"
    if custom_output:
        custom_path = _get_output_dir(custom_output) / f"{stem}.mp3"
        if custom_path.exists():
            with contextlib.suppress(OSError):
                custom_path.unlink()
    default_output = _get_output_dir() / f"{stem}.mp3"
    if default_output.exists():
        with contextlib.suppress(OSError):
            default_output.unlink()

    if book.get("path"):
        _delete_book_source(Path(book["path"]))


def _update_book_title(
    path: Path, title: str, custom_output: str | Path | None = None
) -> None:
    """Update book title in persistence, cleaning up older superseded duplicates."""
    persistence = _get_persistence()
    path_str = str(path.resolve())
    with persistence._get_conn() as conn:
        old_rows = conn.execute(
            "SELECT id, path, title FROM books WHERE title = ? AND path != ?",
            (title, path_str),
        ).fetchall()
        for old in old_rows:
            _cleanup_book_files(dict(old), custom_output=custom_output)
            conn.execute("DELETE FROM books WHERE id = ?", (old["id"],))
        conn.execute("UPDATE books SET title = ? WHERE path = ?", (title, path_str))
        conn.commit()


def _is_book_registered(path: Path) -> bool:
    """Check if a book record exists in persistence for the given path."""
    persistence = _get_persistence()
    path_str = str(path.resolve())
    with persistence._get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM books WHERE path = ?", (path_str,)
        ).fetchone()
        return row is not None


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
async def get_library(output_folder: str | None = None) -> list[dict[str, Any]]:
    """Return all generated books with metadata."""
    books = _get_all_books()
    result = []
    for book in books:
        stem = Path(book["path"]).stem if book.get("path") else f"book_{book['id']}"
        audio_file = _find_audio_file(stem, output_folder)
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
async def download_book(book_id: int, output_folder: str | None = None) -> FileResponse:
    """Download the generated audiobook file."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    stem = Path(book["path"]).stem if book.get("path") else f"book_{book['id']}"
    output_path = _find_audio_file(stem, output_folder)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        output_path,
        media_type="audio/mpeg",
        filename=f"{book['title']}.mp3",
    )


@app.get("/book/{book_id}/path")
async def get_book_path(book_id: int, output_folder: str | None = None) -> dict[str, str]:
    """Return the local filesystem path of the generated audio file."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    stem = Path(book["path"]).stem if book.get("path") else f"book_{book['id']}"
    output_path = _find_audio_file(stem, output_folder)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    return {"path": str(output_path)}


@app.delete("/book/{book_id}")
async def delete_book(book_id: int, output_folder: str | None = None) -> dict[str, str]:
    """Delete a book from the library and remove any generated audio files."""
    book = _get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    await asyncio.to_thread(_cleanup_book_files, book, output_folder)

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

    output_dir = _get_output_dir(request.get("output_folder"))
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
        await pipeline.run(source_path, output_path, resume=False, progress_callback=on_progress)

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

        clean_name = Path(file_name).name.strip()
        raw_stem = Path(clean_name).stem.strip() or "book"
        display_title = raw_stem
        safe_stem = (
            "".join(c for c in raw_stem if c.isalnum() or c in ("-", "_")).strip("._")
            or "book"
        )
        raw_suffix = Path(clean_name).suffix if clean_name else ".txt"
        safe_suffix = "".join(c for c in raw_suffix if c.isalnum() or c == ".").strip() or ".txt"
        if not safe_suffix.startswith("."):
            safe_suffix = f".{safe_suffix}"

        unique_upload_id = uuid.uuid4().hex
        unique_filename = f"{safe_stem}_{unique_upload_id}{safe_suffix}"

        books_dir = _get_books_dir()
        input_path = await asyncio.to_thread(
            _save_uploaded_book, books_dir, unique_filename, file_bytes
        )

        book_registered = False
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
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

                permanent_dir = _get_output_dir(request.get("output_folder"))
                permanent_path = permanent_dir / output_path.name
                # shutil.copy2 in this thread pool keeps the sidecar responsive.
                await asyncio.to_thread(shutil.copy2, output_path, permanent_path)
                book_registered = True
                await asyncio.to_thread(
                    _update_book_title,
                    input_path,
                    display_title,
                    request.get("output_folder"),
                )
                return {"session_id": session_id, "output_path": str(permanent_path)}
        finally:
            if not book_registered:
                is_reg = await asyncio.to_thread(_is_book_registered, input_path)
                if not is_reg:
                    await asyncio.to_thread(_delete_book_source, input_path)

    except HTTPException:
        raise
    except Exception as exc:
        # Surface the failure on the progress channel so the Tauri UI can
        # render it without parsing a one-off error path. Normalize bare
        # FFmpeg FileNotFoundError into the same user-facing install hint
        # the pipeline raises as RuntimeError.
        detail = str(exc)
        if isinstance(exc, FileNotFoundError) and "ffmpeg" in detail.lower():
            detail = FFMPEG_MISSING_MESSAGE
        progress_store.update(
            session_id,
            PipelineProgress(stage="error", percent=0, message=detail),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {detail}",
        ) from exc
