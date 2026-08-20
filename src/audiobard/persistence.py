import contextlib
import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from audiobard.models import AgeHint, Character, GenderHint, Tone, VoiceAssignment
from audiobard.parser.base import ParserStats

logger = logging.getLogger(__name__)


class PersistenceManager:
    """SQLite-backed storage manager for metadata, mappings, run states, and cache."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")

            # 1. Books
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    title TEXT,
                    total_paragraphs INTEGER,
                    total_words INTEGER,
                    dialog_ratio REAL
                )
            """
            )

            # 2. Characters
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    canonical_id TEXT,
                    name TEXT,
                    aliases TEXT, -- JSON string array
                    gender_hint TEXT,
                    age_hint TEXT,
                    tone TEXT,
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
                    UNIQUE(book_id, canonical_id)
                )
            """
            )

            # 3. Voice mapping (speaker_voice_map)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speaker_voice_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    canonical_id TEXT,
                    voice_id TEXT,
                    rate REAL,
                    pitch REAL,
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
                    UNIQUE(book_id, canonical_id)
                )
            """
            )

            # 4. Pipeline runs (checkpoints)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    step TEXT,
                    status TEXT, -- 'pending', 'running', 'completed', 'failed'
                    payload TEXT, -- JSON metadata
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
                    UNIQUE(book_id, step)
                )
            """
            )

            # 5. LLM Request Cache (Phase 3 spec)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hits INTEGER DEFAULT 0
                )
            """
            )
            conn.commit()

    # --------------------------------------------------------------------------
    # Books CRUD
    # --------------------------------------------------------------------------

    def get_or_create_book(self, path: Path, title: str, stats: ParserStats) -> int:
        """Get existing book ID or insert a new record."""
        path_str = str(path.resolve())
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM books WHERE path = ?", (path_str,)
            ).fetchone()
            if row:
                return int(row["id"])

            cursor = conn.execute(
                """
                INSERT INTO books (path, title, total_paragraphs, total_words, dialog_ratio)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    path_str,
                    title,
                    stats.total_paragraphs,
                    stats.total_words,
                    stats.dialog_ratio,
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore

    # --------------------------------------------------------------------------
    # Characters CRUD
    # --------------------------------------------------------------------------

    def save_characters(self, book_id: int, characters: list[Character]) -> None:
        """Insert or replace character list for a book."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM characters WHERE book_id = ?", (book_id,))
            for char in characters:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO characters
                    (book_id, canonical_id, name, aliases, gender_hint, age_hint, tone)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        book_id,
                        char.canonical_id,
                        char.name,
                        json.dumps(char.aliases),
                        char.gender_hint.value,
                        char.age_hint.value,
                        char.tone.value,
                    ),
                )
            conn.commit()

    def get_characters(self, book_id: int) -> list[Character]:
        """Fetch all characters assigned to a book."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT canonical_id, name, aliases, gender_hint, age_hint, tone"
                " FROM characters WHERE book_id = ?",
                (book_id,),
            ).fetchall()
            return [
                Character(
                    canonical_id=row["canonical_id"],
                    name=row["name"],
                    aliases=json.loads(row["aliases"]),
                    gender_hint=GenderHint(row["gender_hint"]),
                    age_hint=AgeHint(row["age_hint"]),
                    tone=Tone(row["tone"]),
                )
                for row in rows
            ]

    # --------------------------------------------------------------------------
    # Speaker Voice Map CRUD
    # --------------------------------------------------------------------------

    def save_voice_mapping(
        self, book_id: int, mapping: list[VoiceAssignment]
    ) -> None:
        """Insert or replace speaker voice maps for a book."""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM speaker_voice_map WHERE book_id = ?", (book_id,)
            )
            for va in mapping:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO speaker_voice_map
                    (book_id, canonical_id, voice_id, rate, pitch)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (book_id, va.canonical_id, va.voice_id, va.rate, va.pitch),
                )
            conn.commit()

    def get_voice_mapping(self, book_id: int) -> list[VoiceAssignment]:
        """Fetch voice assignments for a book."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT canonical_id, voice_id, rate, pitch"
                " FROM speaker_voice_map WHERE book_id = ?",
                (book_id,),
            ).fetchall()
            return [
                VoiceAssignment(
                    canonical_id=row["canonical_id"],
                    voice_id=row["voice_id"],
                    rate=row["rate"],
                    pitch=row["pitch"],
                )
                for row in rows
            ]

    # --------------------------------------------------------------------------
    # Pipeline Runs CRUD
    # --------------------------------------------------------------------------

    def save_checkpoint(
        self, book_id: int, step: str, status: str, payload: dict[str, Any]
    ) -> None:
        """Save pipeline step state checkpoint."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pipeline_runs (book_id, step, status, payload, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (book_id, step, status, json.dumps(payload)),
            )
            conn.commit()

    def get_checkpoint(self, book_id: int, step: str) -> dict[str, Any] | None:
        """Retrieve checkpoint state and metadata if completed/saved."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status, payload FROM pipeline_runs WHERE book_id = ? AND step = ?",
                (book_id, step),
            ).fetchone()
            if row:
                return {"status": row["status"], "payload": json.loads(row["payload"])}
            return None

    def clear_checkpoints(self, book_id: int) -> None:
        """Clear all checkpoints for a book (resets run)."""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM pipeline_runs WHERE book_id = ?", (book_id,)
            )
            conn.commit()

    # --------------------------------------------------------------------------
    # LLM Cache CRUD (Phase 3)
    # --------------------------------------------------------------------------

    def get_llm_cache(self, prompt_hash: str) -> str | None:
        """Retrieve cached response JSON and increment hits."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT response_json FROM llm_cache WHERE prompt_hash = ?",
                (prompt_hash,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE llm_cache SET hits = hits + 1 WHERE prompt_hash = ?",
                    (prompt_hash,),
                )
                conn.commit()
                return str(row["response_json"])
            return None

    def save_llm_cache(
        self, prompt_hash: str, response_json: str, provider: str
    ) -> None:
        """Save response to LLM cache."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (prompt_hash, response_json, provider)
                VALUES (?, ?, ?)
            """,
                (prompt_hash, response_json, provider),
            )
            conn.commit()
