"""Parser sub-package.

Public surface::

    from audiobard.parser import BookParser, TextParser, EpubParser, ParserStats
"""

from __future__ import annotations

from audiobard.parser.base import BookParser, ParserStats
from audiobard.parser.epub_parser import EpubParser
from audiobard.parser.text_parser import TextParser

__all__ = ["BookParser", "EpubParser", "ParserStats", "TextParser"]
