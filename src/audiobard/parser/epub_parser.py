"""EPUB parser using ebooklib + BeautifulSoup4.

- Extracts chapters via spine metadata (preserves reading order).
- Skips common frontmatter / backmatter (cover, title, toc, index, …).
- Strips HTML tags and normalises whitespace.
- Marks ``is_dialog`` using the same heuristic as :class:`TextParser`.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import TYPE_CHECKING

from audiobard.models import Paragraph
from audiobard.parser.base import BookParser
from audiobard.parser.text_parser import _is_dialog, _split_paragraphs

if TYPE_CHECKING:
    pass

# Spine items whose ``idref`` or file name suggests they are not body chapters.
# Note: Calibre splits chapters into "index_split_XXX.html", so we use negative lookahead
# to ensure we don't accidentally skip actual book content!
_SKIP_ID_PATTERNS = re.compile(
    r"(cover|title|toc|nav|index(?!_split)|coloph|copyright|dedic|epigraph|preface|about)",
    re.IGNORECASE,
)

# HTML tags we want to convert to newlines before stripping (block-level breaks).
_BLOCK_TAGS = re.compile(r"</?(?:p|div|h[1-6]|li|tr)[^>]*>|<br\s*/?>", re.IGNORECASE)


def _html_to_text(raw_html: str) -> str:
    """Very lightweight HTML → plaintext: replace block tags with newlines, strip the rest."""
    text = _BLOCK_TAGS.sub("\n\n", raw_html)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", "", text)
    # Decode all named, numeric, and hex HTML entities.
    return html.unescape(text)


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
