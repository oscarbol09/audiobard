"""Abstract base class and statistics model for book parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from audiobard.models import Paragraph


class ParserStats(BaseModel):
    """Summary statistics produced after parsing a book."""

    total_paragraphs: int = Field(ge=0)
    total_words: int = Field(ge=0)
    dialog_ratio: float = Field(
        ge=0.0, le=1.0, description="Fraction of paragraphs marked is_dialog"
    )
    chapter_word_counts: dict[int, int] = Field(
        default_factory=dict,
        description="Mapping of chapter index → word count",
    )


class BookParser(ABC):
    """Abstract parser that turns a book source into a list of Paragraphs.

    Subclasses implement :meth:`parse` for a specific format (TXT, EPUB, …).
    Call :meth:`stats` *after* :meth:`parse` to get aggregated statistics.
    """

    def __init__(self) -> None:
        self._paragraphs: list[Paragraph] | None = None

    @abstractmethod
    def parse(self, source: str | bytes | Path) -> list[Paragraph]:
        """Parse *source* and return an ordered list of :class:`Paragraph`.

        The returned list is also stored internally so :meth:`stats` works
        without re-parsing.

        Parameters
        ----------
        source:
            File path (``Path`` or ``str``) **or** raw bytes for in-memory
            sources (useful in tests).
        """

    def stats(self) -> ParserStats:
        """Return aggregate statistics for the last :meth:`parse` call.

        Raises ``RuntimeError`` if called before :meth:`parse`.
        """
        if self._paragraphs is None:
            raise RuntimeError("Call parse() before stats().")

        total_words = 0
        dialog_count = 0
        chapter_word_counts: dict[int, int] = {}

        for p in self._paragraphs:
            words = len(p.text.split())
            total_words += words
            if p.is_dialog:
                dialog_count += 1
            chapter_word_counts[p.chapter] = chapter_word_counts.get(p.chapter, 0) + words

        n = len(self._paragraphs)
        return ParserStats(
            total_paragraphs=n,
            total_words=total_words,
            dialog_ratio=dialog_count / n if n else 0.0,
            chapter_word_counts=chapter_word_counts,
        )
