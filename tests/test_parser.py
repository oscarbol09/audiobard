"""Tests for the text and EPUB parsers.

All tests use inline fixtures (no external files) so they run in CI without
any data/ dependencies.
"""

from __future__ import annotations

import pytest

from audiobard.models import Paragraph
from audiobard.parser import ParserStats, TextParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text(*blocks: str) -> str:
    """Join blocks with double newlines (standard paragraph separator)."""
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# TextParser — basic parsing
# ---------------------------------------------------------------------------


class TestTextParserBasic:
    def test_single_paragraph(self) -> None:
        parser = TextParser()
        result = parser.parse("Hello, world.")
        assert len(result) == 1
        assert result[0].text == "Hello, world."
        assert result[0].chapter == 0
        assert result[0].index == 0

    def test_multiple_paragraphs(self) -> None:
        parser = TextParser()
        text = _make_text("First paragraph.", "Second paragraph.", "Third paragraph.")
        result = parser.parse(text)
        assert len(result) == 3
        assert [p.index for p in result] == [0, 1, 2]

    def test_whitespace_normalised(self) -> None:
        parser = TextParser()
        result = parser.parse("  Hello    world   ")
        assert result[0].text == "Hello world"

    def test_empty_paragraphs_skipped(self) -> None:
        parser = TextParser()
        text = "Para one.\n\n   \n\nPara two."
        result = parser.parse(text)
        assert len(result) == 2

    def test_bytes_input(self) -> None:
        parser = TextParser()
        result = parser.parse(b"Hello, bytes world.")
        assert result[0].text == "Hello, bytes world."

    def test_returns_paragraph_models(self) -> None:
        parser = TextParser()
        result = parser.parse("Some text.")
        assert all(isinstance(p, Paragraph) for p in result)


# ---------------------------------------------------------------------------
# TextParser — Project Gutenberg boilerplate stripping
# ---------------------------------------------------------------------------


class TestTextParserGutenberg:
    def test_strips_pg_header(self) -> None:
        text = (
            "Some licensing preamble.\n\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n\n"
            "Chapter One\n\n"
            "Actual content here.\n\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK FOO ***\n\n"
            "More licensing footer."
        )
        parser = TextParser()
        result = parser.parse(text)
        # "Some licensing preamble" and footer should not appear
        texts = [p.text for p in result]
        assert not any("licensing" in t.lower() for t in texts)
        assert any("Actual content" in t for t in texts)

    def test_no_pg_markers_parses_whole_text(self) -> None:
        parser = TextParser()
        text = "Para one.\n\nPara two."
        result = parser.parse(text)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TextParser — chapter detection
# ---------------------------------------------------------------------------


class TestTextParserChapters:
    def test_chapter_heading_increments_chapter(self) -> None:
        text = _make_text(
            "Chapter I",
            "First chapter content.",
            "Chapter II",
            "Second chapter content.",
        )
        parser = TextParser()
        result = parser.parse(text)
        # Chapter headings are NOT emitted as paragraphs
        assert len(result) == 2
        assert result[0].chapter == 1
        assert result[1].chapter == 2

    def test_chapter_heading_not_in_output(self) -> None:
        text = _make_text("CHAPTER ONE", "Actual text.")
        parser = TextParser()
        result = parser.parse(text)
        assert not any("CHAPTER" in p.text for p in result)

    def test_no_chapters_all_in_chapter_zero(self) -> None:
        parser = TextParser()
        text = _make_text("Para A.", "Para B.", "Para C.")
        result = parser.parse(text)
        assert all(p.chapter == 0 for p in result)


# ---------------------------------------------------------------------------
# TextParser — dialog detection
# ---------------------------------------------------------------------------


class TestTextParserDialog:
    @pytest.mark.parametrize(
        "text",
        [
            '"I cannot believe it," she said.',
            "\u201cThis uses curly quotes,\u201d he replied.",
            "\u2014 I do not know what to say.",  # em-dash speech
        ],
    )
    def test_dialog_detected(self, text: str) -> None:
        parser = TextParser()
        result = parser.parse(text)
        assert result[0].is_dialog is True

    def test_narration_not_marked_dialog(self) -> None:
        parser = TextParser()
        result = parser.parse("The night was cold and the streets were empty.")
        assert result[0].is_dialog is False


# ---------------------------------------------------------------------------
# ParserStats
# ---------------------------------------------------------------------------


class TestParserStats:
    def test_stats_after_parse(self) -> None:
        parser = TextParser()
        text = _make_text(
            "CHAPTER I",
            "Narration paragraph here with several words.",
            '"Dialog line," said someone.',
            "CHAPTER II",
            "More narration.",
        )
        parser.parse(text)
        stats = parser.stats()
        assert isinstance(stats, ParserStats)
        assert stats.total_paragraphs == 3
        assert stats.total_words > 0
        assert 0.0 <= stats.dialog_ratio <= 1.0
        assert set(stats.chapter_word_counts.keys()) == {1, 2}

    def test_stats_before_parse_raises(self) -> None:
        parser = TextParser()
        with pytest.raises(RuntimeError, match="parse()"):
            parser.stats()

    def test_dialog_ratio_all_dialog(self) -> None:
        parser = TextParser()
        text = _make_text(
            '"Line one," she said.',
            '"Line two," he replied.',
        )
        parser.parse(text)
        stats = parser.stats()
        assert stats.dialog_ratio == 1.0

    def test_dialog_ratio_no_dialog(self) -> None:
        parser = TextParser()
        text = _make_text("Pure narration.", "More narration.")
        parser.parse(text)
        stats = parser.stats()
        assert stats.dialog_ratio == 0.0
