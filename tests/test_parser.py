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

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("First.\n\nSecond.", ["First.", "Second."]),
            ("First.\r\n\r\nSecond.", ["First.", "Second."]),
            ("First.\r\rSecond.", ["First.", "Second."]),
            ("First.\r\n\r\nSecond.\n\nThird.", ["First.", "Second.", "Third."]),
        ],
    )
    def test_paragraph_boundaries_support_line_endings(
        self, text: str, expected: list[str]
    ) -> None:
        parser = TextParser()
        result = parser.parse(text)
        assert [paragraph.text for paragraph in result] == expected

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
        with pytest.raises(RuntimeError, match=r"Call parse\(\) before stats\(\)"):
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


# ---------------------------------------------------------------------------
# EpubParser — unit tests
# ---------------------------------------------------------------------------


class _MockEpubItem:
    def __init__(self, item_id: str, name: str, content: bytes) -> None:
        self._id = item_id
        self._name = name
        self._content = content

    def get_id(self) -> str:
        return self._id

    def get_name(self) -> str:
        return self._name

    def get_content(self) -> bytes:
        return self._content


class _MockEpubBook:
    def __init__(self, items: list[_MockEpubItem]) -> None:
        self._items = items

    def get_items_of_type(self, item_type: int) -> list[_MockEpubItem]:
        return self._items


class TestEpubParser:
    def test_epub_parser_parsing(self) -> None:
        from unittest.mock import patch

        from audiobard.parser.epub_parser import EpubParser

        items = [
            _MockEpubItem("cover_page", "cover.xhtml", b"<h1>Cover</h1>"),
            _MockEpubItem("toc_page", "toc.xhtml", b"<nav>Table of Contents</nav>"),
            _MockEpubItem(
                "ch1",
                "ch1.xhtml",
                b"<p>Hello &amp; welcome &mdash; world &ndash; &lsquo;test&rsquo; "
                b"&#39;quote&#39; &quot;double&quot; &ldquo;smart&rdquo; &lt;tag&gt;.</p>"
                b"<p>&ldquo;Hello!&rdquo; she said.</p>",
            ),
            _MockEpubItem("empty_ch", "empty.xhtml", b"   "),
            _MockEpubItem("ch2", "ch2.xhtml", b"<div>Second chapter content.</div>"),
        ]
        mock_book = _MockEpubBook(items)

        with patch("ebooklib.epub.read_epub", return_value=mock_book):
            parser = EpubParser()
            paragraphs = parser.parse(b"dummy-epub-bytes")
            assert len(paragraphs) == 3
            assert paragraphs[0].chapter == 0
            assert "Hello & welcome" in paragraphs[0].text
            assert paragraphs[1].is_dialog is True
            assert paragraphs[2].chapter == 1
            assert paragraphs[2].text == "Second chapter content."

            stats = parser.stats()
            assert stats.total_paragraphs == 3
            assert stats.dialog_ratio > 0.0

    def test_epub_parser_filepath_input(self) -> None:
        from unittest.mock import patch

        from audiobard.parser.epub_parser import EpubParser

        items = [
            _MockEpubItem("ch1", "ch1.xhtml", b"<p>Simple paragraph from file path.</p>")
        ]
        mock_book = _MockEpubBook(items)

        with patch("ebooklib.epub.read_epub", return_value=mock_book):
            parser = EpubParser()
            paragraphs = parser.parse("fake_book.epub")
            assert len(paragraphs) == 1
            assert paragraphs[0].text == "Simple paragraph from file path."

    def test_html_entity_decoding(self) -> None:
        from audiobard.parser.epub_parser import _html_to_text

        raw = (
            "<p>&apos;Hello&apos; &copy; 2026 &#8217;test&#8217; "
            "&#x2019;hex&#x2019; &reg; &euro; &pound; &cent; &sect; &hellip; &bull;</p>"
        )
        res = _html_to_text(raw).strip()
        assert res == "'Hello' © 2026 \u2019test\u2019 \u2019hex\u2019 ® € £ ¢ § … •"


class TestEpubStyleScriptStripping:
    def test_style_block_contents_are_not_narrated(self) -> None:
        from audiobard.parser.epub_parser import _html_to_text

        raw = "<style>body { color: #333; }</style><p>Hello world</p>"
        res = _html_to_text(raw).strip()
        assert res == "Hello world"
        assert "color" not in res

    def test_script_block_contents_are_not_narrated(self) -> None:
        from audiobard.parser.epub_parser import _html_to_text

        raw = "<script>console.log('hi');</script><p>Hello world</p>"
        res = _html_to_text(raw).strip()
        assert res == "Hello world"
        assert "console" not in res

    def test_style_block_with_attributes_is_stripped(self) -> None:
        from audiobard.parser.epub_parser import _html_to_text

        raw = '<style type="text/css">p { margin: 0; }</style><p>Text.</p>'
        res = _html_to_text(raw).strip()
        assert res == "Text."

    def test_epub_parser_end_to_end_excludes_style_contents(self) -> None:
        from unittest.mock import patch

        from audiobard.parser.epub_parser import EpubParser

        items = [
            _MockEpubItem(
                "ch1",
                "ch1.xhtml",
                b"<style>body { color: #333; }</style><p>Hello world</p>",
            ),
        ]
        mock_book = _MockEpubBook(items)

        with patch("ebooklib.epub.read_epub", return_value=mock_book):
            parser = EpubParser()
            paragraphs = parser.parse(b"dummy-epub-bytes")
            assert len(paragraphs) == 1
            assert paragraphs[0].text == "Hello world"


class TestProjectGutenbergBoilerplate:
    def test_both_start_and_end_markers(self) -> None:
        text = (
            "Header boilerplate\n"
            "*** START OF THIS PROJECT GUTENBERG EBOOK TEST ***\n"
            "Real story content.\n"
            "*** END OF THIS PROJECT GUTENBERG EBOOK TEST ***\n"
            "Footer boilerplate"
        )
        parser = TextParser()
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].text == "Real story content."

    def test_only_start_marker(self) -> None:
        text = (
            "Header boilerplate\n"
            "*** START OF THIS PROJECT GUTENBERG EBOOK TEST ***\n"
            "Real story content."
        )
        parser = TextParser()
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].text == "Real story content."

    def test_only_end_marker(self) -> None:
        text = (
            "Real story content.\n"
            "*** END OF THIS PROJECT GUTENBERG EBOOK TEST ***\n"
            "Footer boilerplate"
        )
        parser = TextParser()
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].text == "Real story content."

    def test_neither_marker(self) -> None:
        text = "Real story content without any markers."
        parser = TextParser()
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].text == "Real story content without any markers."
