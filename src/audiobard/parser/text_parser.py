"""Plain-text book parser with Project Gutenberg support.

Handles:
- UTF-8 encoding
- Project Gutenberg header / footer stripping
- Chapter boundary detection (CHAPTER I / Chapter 1 / Roman numerals)
- ``is_dialog`` heuristic (curly/straight quotes, em-dash, en-dash lines)
- Paragraph normalisation (collapse blank lines, strip trailing spaces)
"""

from __future__ import annotations

import re
from pathlib import Path

from audiobard.models import Paragraph
from audiobard.parser.base import BookParser

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# Project Gutenberg delimiters — everything outside is stripped.
_PG_START = re.compile(
    r"^\*{3}\s*START OF (THE|THIS) PROJECT GUTENBERG.*$",
    re.IGNORECASE | re.MULTILINE,
)
_PG_END = re.compile(
    r"^\*{3}\s*END OF (THE|THIS) PROJECT GUTENBERG.*$",
    re.IGNORECASE | re.MULTILINE,
)

# Chapter headings — treated as section breaks (not emitted as paragraphs).
_CHAPTER_HEAD = re.compile(
    r"""
    ^                                      # start of line
    (?:
        chapter\s+                         # "Chapter "
        (?:[IVXLCDM]+|\d+|[a-z]+)         # Roman, Arabic, or word numeral
        |
        CHAPTER\s+
        (?:[IVXLCDM]+|\d+|[A-Z]+)
        |
        part\s+(?:[IVXLCDM]+|\d+|[a-z]+)  # "Part "
        |
        PART\s+(?:[IVXLCDM]+|\d+|[A-Z]+)
    )
    [.:\s—–-]*                             # optional punctuation
    .*$                                    # rest of heading (subtitle etc.)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Dialog heuristics — a paragraph is considered dialog if it starts with or
# contains one of these patterns.
_DIALOG_OPEN = re.compile(
    r"""
    (?:
        ^[\u201c"«]           |   # curly/guillemet open quote at start
        ^["']                 |   # straight quote at start
        ^[—–]\s              |   # em/en-dash speech line
        \s[\u201c"«]          |   # curly quote mid-paragraph
        ["'][^"']{1,200}["']  |   # matched straight quotes (short enough)
        \u201c[^\u201c\u201d]{1,200}\u201d # matched curly quotes (short enough)
    )
    """,
    re.VERBOSE,
)


def _is_dialog(text: str) -> bool:
    return bool(_DIALOG_OPEN.search(text))


def _strip_pg_boilerplate(text: str) -> str:
    """Return the text between PG start/end markers, or the full text."""
    start_m = _PG_START.search(text)
    if start_m:
        text = text[start_m.end():]
    end_m = _PG_END.search(text)
    if end_m:
        text = text[: end_m.start()]
    return text


def _split_paragraphs(text: str) -> list[str]:
    """Split on one or more blank lines; return non-empty stripped paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", normalized)
    result: list[str] = []
    for block in blocks:
        cleaned = " ".join(block.split())  # collapse internal whitespace
        if cleaned:
            result.append(cleaned)
    return result


class TextParser(BookParser):
    """Parse a plain-text book (UTF-8) into :class:`~audiobard.models.Paragraph` objects."""

    def parse(self, source: str | bytes | Path) -> list[Paragraph]:
        """Parse *source* (path, string content, or bytes).

        Returns
        -------
        list[Paragraph]
            Ordered list of paragraphs with chapter and index metadata.
        """
        if isinstance(source, Path):
            raw = source.read_text(encoding="utf-8-sig", errors="replace")
        elif isinstance(source, bytes):
            raw = source.decode("utf-8-sig", errors="replace")
        else:
            raw = str(source).lstrip("\ufeff")  # already a string

        raw = _strip_pg_boilerplate(raw)
        blocks = _split_paragraphs(raw)

        paragraphs: list[Paragraph] = []
        chapter = 0
        index = 0

        for block in blocks:
            if _CHAPTER_HEAD.match(block):
                chapter += 1
                continue  # chapter headings are not emitted as paragraphs

            p = Paragraph(
                text=block,
                chapter=chapter,
                index=index,
                is_dialog=_is_dialog(block),
            )
            paragraphs.append(p)
            index += 1

        self._paragraphs = paragraphs
        return paragraphs
