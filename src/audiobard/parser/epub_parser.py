"""EPUB parser using ebooklib + BeautifulSoup4.

- Extracts chapters via spine metadata (preserves reading order).
- Skips common frontmatter / backmatter (cover, title, toc, index, …).
- Strips HTML tags and normalises whitespace.
- Marks ``is_dialog`` using the same heuristic as :class:`TextParser`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from audiobard.models import Paragraph
from audiobard.parser.base import BookParser
from audiobard.parser.text_parser import _is_dialog, _split_paragraphs

if TYPE_CHECKING:
    pass

# Spine items whose ``idref`` or file name suggests they are not body chapters.
_SKIP_ID_PATTERNS = re.compile(
    r"(cover|title|toc|nav|index|coloph|copyright|dedic|epigraph|preface|about)",
    re.IGNORECASE,
)

# HTML tags we want to convert to newlines before stripping (block-level breaks).
_BLOCK_TAGS = re.compile(r"<(?:p|br|div|h[1-6]|li|tr)[^>]*>", re.IGNORECASE)


def _html_to_text(html: str) -> str:
    """Very lightweight HTML → plaintext: replace block tags with newlines, strip the rest."""
    text = _BLOCK_TAGS.sub("\n", html)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities.
    for entity, char in (
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
        ("&mdash;", "—"),
        ("&ndash;", "–"),
        ("&ldquo;", "\u201c"),
        ("&rdquo;", "\u201d"),
        ("&lsquo;", "\u2018"),
        ("&rsquo;", "\u2019"),
    ):
        text = text.replace(entity, char)
    return text


class EpubParser(BookParser):
    """Parse an EPUB file into :class:`~audiobard.models.Paragraph` objects."""

    def parse(self, source: str | bytes | Path) -> list[Paragraph]:
        """Parse *source* (file path or raw EPUB bytes).

        Returns
        -------
        list[Paragraph]
            Paragraphs ordered by spine position with chapter indices.
        """
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "ebooklib is required for EPUB parsing: pip install ebooklib"
            ) from exc

        if isinstance(source, (str, Path)):
            book = epub.read_epub(str(source))
        else:
            import io
            book = epub.read_epub(io.BytesIO(source))

        paragraphs: list[Paragraph] = []
        chapter_idx = 0
        global_index = 0

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            # Skip known non-body items.
            item_id: str = item.get_id() or ""
            file_name: str = item.get_name() or ""
            if _SKIP_ID_PATTERNS.search(item_id) or _SKIP_ID_PATTERNS.search(file_name):
                continue

            html = item.get_content().decode("utf-8", errors="replace")
            plain = _html_to_text(html)
            blocks = _split_paragraphs(plain)

            if not blocks:
                continue  # empty spine item

            for block in blocks:
                p = Paragraph(
                    text=block,
                    chapter=chapter_idx,
                    index=global_index,
                    is_dialog=_is_dialog(block),
                )
                paragraphs.append(p)
                global_index += 1

            chapter_idx += 1

        self._paragraphs = paragraphs
        return paragraphs
