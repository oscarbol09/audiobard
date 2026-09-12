"""Unit tests for PersistenceManager (SQLite CRUD, checkpoints, and rollback)."""

from __future__ import annotations

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


@pytest.fixture
def pm(tmp_path: Path) -> PersistenceManager:
    """Fixture providing an isolated PersistenceManager instance."""
    return PersistenceManager(tmp_path / "test.db")


@pytest.fixture
def sample_stats() -> ParserStats:
    """Fixture providing valid sample parser stats."""
    return ParserStats(
        total_paragraphs=10,
        total_words=500,
        dialog_ratio=0.4,
        chapter_word_counts={1: 500},
    )


def test_book_lifecycle_and_idempotency(
    pm: PersistenceManager, tmp_path: Path, sample_stats: ParserStats
) -> None:
    """Test get_or_create_book creates new record and returns existing book ID idempotently."""
    book_path = tmp_path / "sample.txt"
    book_id1 = pm.get_or_create_book(book_path, "Sample Title", sample_stats)
    assert book_id1 > 0

    # Querying existing book should return the same ID
    book_id2 = pm.get_or_create_book(book_path, "Sample Title", sample_stats)
    assert book_id1 == book_id2


def test_characters_persistence(
    pm: PersistenceManager, tmp_path: Path, sample_stats: ParserStats
) -> None:
    """Test saving and retrieving character lists for a book."""
    book_id = pm.get_or_create_book(tmp_path / "sample.txt", "Sample", sample_stats)
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
    pm.save_characters(book_id, chars)
    retrieved_chars = pm.get_characters(book_id)
    assert len(retrieved_chars) == 1
    assert retrieved_chars[0].canonical_id == "Character_A"
    assert retrieved_chars[0].name == "Alice"
    assert retrieved_chars[0].aliases == ["Ally"]


def test_voice_mapping_persistence(
    pm: PersistenceManager, tmp_path: Path, sample_stats: ParserStats
) -> None:
    """Test saving and retrieving voice assignments."""
    book_id = pm.get_or_create_book(tmp_path / "sample.txt", "Sample", sample_stats)
    mapping = [
        VoiceAssignment(
            canonical_id="Character_A",
            voice_id="voice-alice",
            rate=1.05,
            pitch=1.0,
        )
    ]
    pm.save_voice_mapping(book_id, mapping)
    retrieved_map = pm.get_voice_mapping(book_id)
    assert len(retrieved_map) == 1
    assert retrieved_map[0].voice_id == "voice-alice"
    assert retrieved_map[0].rate == 1.05


def test_checkpoints_lifecycle(
    pm: PersistenceManager, tmp_path: Path, sample_stats: ParserStats
) -> None:
    """Test checkpoint saving, querying, and clearing."""
    book_id = pm.get_or_create_book(tmp_path / "sample.txt", "Sample", sample_stats)
    assert pm.get_checkpoint(book_id, "characters") is None

    pm.save_checkpoint(book_id, "characters", "completed", {"count": 1})
    chk = pm.get_checkpoint(book_id, "characters")
    assert chk is not None
    assert chk["status"] == "completed"
    assert chk["payload"]["count"] == 1

    pm.clear_checkpoints(book_id)
    assert pm.get_checkpoint(book_id, "characters") is None


def test_book_cascade_deletion(
    pm: PersistenceManager, tmp_path: Path, sample_stats: ParserStats
) -> None:
    """Test deleting a book cascades to its associated characters and voice mappings."""
    book_id = pm.get_or_create_book(tmp_path / "sample.txt", "Sample", sample_stats)
    pm.save_characters(
        book_id,
        [Character(canonical_id="Character_A", name="Alice", tone=Tone.CALM)],
    )
    pm.save_voice_mapping(
        book_id,
        [VoiceAssignment(canonical_id="Character_A", voice_id="v1", rate=1.0, pitch=1.0)],
    )

    assert pm.delete_book(book_id) is True
    assert pm.delete_book(book_id) is False  # Second delete returns False
    assert pm.get_characters(book_id) == []
    assert pm.get_voice_mapping(book_id) == []


def test_transaction_rollback_on_exception(pm: PersistenceManager) -> None:
    """Test that failed database transactions rollback cleanly."""
    with pytest.raises(RuntimeError, match="DB Error"), pm._get_conn() as conn:
        conn.execute("INSERT INTO books (path, title) VALUES ('err_path', 'err')")
        raise RuntimeError("DB Error")

    # Verify insertion was rolled back
    with pm._get_conn() as conn:
        row = conn.execute("SELECT * FROM books WHERE path = 'err_path'").fetchone()
        assert row is None

