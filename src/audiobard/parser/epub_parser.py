"""EPUB parser using ebooklib with regex-based HTML stripping.

- Extracts chapters via spine metadata (preserves reading order).
- Skips common frontmatter / backmatter (cover, title, toc, index, …).
- Strips HTML tags and normalises whitespace.
- Marks ``is_dialog`` using the same heuristic as :class:`TextParser`.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

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

# <script>/<style> blocks whose *contents* (CSS rules, JS) must not survive as narrated text.
_SCRIPT_STYLE_BLOCKS = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def _html_to_text(raw_html: str) -> str:
    """Very lightweight HTML → plaintext: replace block tags with newlines, strip the rest."""
    # Drop script/style blocks (and their contents) before any tag stripping, so CSS
    # rules and JS aren't left behind as plain text once their tags are gone.
    text = _SCRIPT_STYLE_BLOCKS.sub("", raw_html)
    text = _BLOCK_TAGS.sub("\n\n", text)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", "", text)
    # Decode all named, numeric, and hex HTML entities.
    return html.unescape(text)


def _first_metadata_value(book: object, name: str) -> str | None:
    """Return the first Dublin Core *name* value from an EPUB package, if any."""
    getter = getattr(book, "get_metadata", None)
    if not callable(getter):
        return None
    try:
        entries = getter("DC", name)
    except Exception:  # pragma: no cover - defensive: unusual ebooklib versions
        return None
    for entry in entries or []:
        value = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        text = str(value).strip()
        if text:
            return text
    return None


def _cover_item_from_meta(book: object) -> object | None:
    """Resolve the manifest item named by the OPF cover meta tag, if present."""
    getter = getattr(book, "get_metadata", None)
    lookup = getattr(book, "get_item_with_id", None)
    if not callable(getter) or not callable(lookup):
        return None
    try:
        entries = getter(None, "meta")
    except Exception:  # pragma: no cover - defensive: unusual ebooklib versions
        return None
    for entry in entries or []:
        attrs = entry[1] if isinstance(entry, (tuple, list)) and len(entry) > 1 else None
        if not isinstance(attrs, dict):
            continue
        if str(attrs.get("name", "")).lower() != "cover":
            continue
        cover_id = str(attrs.get("content", "")).strip()
        if cover_id:
            item = lookup(cover_id)
            if item is not None:
                return cast(object, item)
    return None


def _cover_item_from_items(book: object, ebooklib_module: object) -> object | None:
    """Find a cover image by ebooklib type, then by an id/file-name heuristic."""
    get_items = getattr(book, "get_items", None)
    items = list(get_items() or []) if callable(get_items) else []
    item_cover = getattr(ebooklib_module, "ITEM_COVER", None)
    for item in items:
        get_type = getattr(item, "get_type", None)
        if item_cover is not None and callable(get_type) and get_type() == item_cover:
            return cast(object, item)
    for item in items:
        media_getter = getattr(item, "get_media_type", None)
        media_type = str(media_getter() or "") if callable(media_getter) else ""
        item_id = str(getattr(item, "get_id", lambda: "")())
        item_name = str(getattr(item, "get_name", lambda: "")())
        if media_type.startswith("image/") and "cover" in f"{item_id} {item_name}".lower():
            return cast(object, item)
    return None


def _cover_item_from_html(book: object) -> object | None:
    """Resolve the image referenced by a cover page such as cover.xhtml."""
    get_items = getattr(book, "get_items", None)
    items = list(get_items() or []) if callable(get_items) else []
    for item in items:
        name = str(getattr(item, "get_name", lambda: "")() or "").replace("\\", "/")
        lowered = name.lower()
        if "cover" not in lowered or not lowered.endswith((".xhtml", ".html", ".htm")):
            continue
        content = getattr(item, "get_content", lambda: b"")()
        text = (
            content.decode("utf-8", errors="replace")
            if isinstance(content, bytes)
            else str(content)
        )
        match = re.search(r"""<img[^>]+src=["']([^"']+)["']""", text, re.IGNORECASE)
        if not match:
            continue
        target = match.group(1).replace("\\", "/").split("/")[-1].lower()
        for candidate in items:
            candidate_name = (
                str(getattr(candidate, "get_name", lambda: "")() or "").replace("\\", "/").lower()
            )
            if candidate_name.endswith(target):
                return cast(object, candidate)
    return None


def _extract_cover(book: object, ebooklib_module: object) -> tuple[bytes | None, str | None]:
    """Return ``(bytes, media_type)`` for the EPUB cover image, if there is one."""
    item = (
        _cover_item_from_meta(book)
        or _cover_item_from_items(book, ebooklib_module)
        or _cover_item_from_html(book)
    )
    if item is None:
        return None, None
    content = getattr(item, "get_content", lambda: b"")()
    if not content:
        return None, None
    media_getter = getattr(item, "get_media_type", None)
    mime = str(media_getter() or "").strip() if callable(media_getter) else ""
    data = content if isinstance(content, bytes) else bytes(content)
    return data, (mime or None)


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

        self._extract_metadata(book, ebooklib)

        paragraphs: list[Paragraph] = []
        chapter_idx = 0
        global_index = 0

        items = []
        spine = getattr(book, "spine", None)
        if spine:
            for entry in spine:
                entry_id = entry[0] if isinstance(entry, (tuple, list)) else entry
                if hasattr(entry_id, "get_id"):
                    item = entry_id
                elif hasattr(book, "get_item_with_id"):
                    item = book.get_item_with_id(entry_id)
                else:
                    item = None

                if not item:
                    continue
                if hasattr(item, "get_type") and item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue
                items.append(item)
        else:
            items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

        for item in items:
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

    def _extract_metadata(self, book: object, ebooklib_module: object) -> None:
        """Populate title/author/cover from the package Dublin Core metadata."""
        self.title = _first_metadata_value(book, "title")
        self.author = _first_metadata_value(book, "creator")
        cover_bytes, cover_mime = _extract_cover(book, ebooklib_module)
        self.cover_bytes = cover_bytes
        self.cover_mime = cover_mime
