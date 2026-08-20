"""Unit tests for PersistenceManager (SQLite CRUD, checkpoints, and rollback)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from audiobard.models import (
    AgeHint,
    Character,
    GenderHint,
    Tone,
    VoiceAssignment,
)
from audiobard.parser.base import ParserStats
from audiobard.persistence import PersistenceManager


def test_persistence_manager_crud_and_rollback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pm = PersistenceManager(db_path)

        # 1. Books get_or_create (new + existing)
        stats = ParserStats(
            total_paragraphs=10,
            total_words=500,
            dialog_paragraphs=4,
            dialog_ratio=0.4,
            chapter_word_counts={1: 500},
        )
        book_path = Path(tmpdir) / "sample.txt"
        book_id1 = pm.get_or_create_book(book_path, "Sample Title", stats)
        assert book_id1 > 0

        # Query existing book
        book_id2 = pm.get_or_create_book(book_path, "Sample Title", stats)
        assert book_id1 == book_id2

        # 2. Characters save and get
        chars = [
            Character(
                canonical_id="Character_A",
                name="Alice",
                aliases=["Ally"],
                gender_hint=GenderHint.FEMALE,
                age_hint=AgeHint.YOUNG,
                tone=Tone.WARM,
            )
        ]
        pm.save_characters(book_id1, chars)
        retrieved_chars = pm.get_characters(book_id1)
        assert len(retrieved_chars) == 1
        assert retrieved_chars[0].canonical_id == "Character_A"
        assert retrieved_chars[0].name == "Alice"

        # 3. Voice mapping save and get
        mapping = [
            VoiceAssignment(
                canonical_id="Character_A",
                voice_id="voice-alice",
                rate=1.05,
                pitch=1.0,
            )
        ]
        pm.save_voice_mapping(book_id1, mapping)
        retrieved_map = pm.get_voice_mapping(book_id1)
        assert len(retrieved_map) == 1
        assert retrieved_map[0].voice_id == "voice-alice"

        # 4. Checkpoints save, get, clear
        assert pm.get_checkpoint(book_id1, "characters") is None
        pm.save_checkpoint(book_id1, "characters", "completed", {"count": 1})
        chk = pm.get_checkpoint(book_id1, "characters")
        assert chk is not None
        assert chk["status"] == "completed"
        assert chk["payload"]["count"] == 1

        pm.clear_checkpoints(book_id1)
        assert pm.get_checkpoint(book_id1, "characters") is None

        # 5. Rollback on exception
        with pytest.raises(RuntimeError, match="DB Error"), pm._get_conn() as conn:
            conn.execute("INSERT INTO books (path, title) VALUES ('err_path', 'err')")
            raise RuntimeError("DB Error")

        # Verify insertion was rolled back
        with pm._get_conn() as conn:
            row = conn.execute("SELECT * FROM books WHERE path = 'err_path'").fetchone()
            assert row is None
