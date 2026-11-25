"""Cleans extracted page text before it is chunked.

PDF text comes with noise that would otherwise end up in search results and answers:
  * running headers and footers repeated on most pages ("Module for ASHA | 23"),
  * lines that are only a page number,
  * words split across lines with a hyphen ("treat-\\nment"),
  * odd spacing and different Unicode forms of the same Hindi characters.
"""
import re
import unicodedata
from collections import Counter

from app.types import Page

# A line that appears on at least this share of a document's pages (and on at least 3 pages) is a header or footer.
REPEATED_LINE_SHARE = 0.4
EDGE_LINES = 3  # headers and footers are looked for only in the first and last lines of each page
MIN_PAGE_CHARS = 40  # pages with less text than this (covers, blank pages) are dropped

_PAGE_NUMBER = re.compile(r"^\s*(page\s*)?[\divxlc]{1,5}(\s*(of|/)\s*\d+)?\s*$", re.IGNORECASE)
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _normalise(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def repeated_edge_lines(pages: list[Page]) -> set[str]:
    """Header/footer lines: the same line (numbers ignored) at the top or bottom of many pages."""
    counts = Counter()
    for page in pages:
        lines = [l for l in page.text.splitlines() if l.strip()]
        edges = {_normalise(l) for l in lines[:EDGE_LINES] + lines[-EDGE_LINES:]}
        counts.update(edges)
    limit = max(3, int(len(pages) * REPEATED_LINE_SHARE))
    return {line for line, count in counts.items() if count >= limit and line}


def clean_text(text: str, drop: set[str] = frozenset()) -> str:
    """Clean one page: drop header/footer and page-number lines, rejoin hyphenated words, tidy spacing."""
    text = unicodedata.normalize("NFC", text).replace("\r", "")
    kept = [l for l in text.splitlines() if not _PAGE_NUMBER.match(l) and _normalise(l) not in drop]
    text = "\n".join(kept)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", text).strip()


def clean_pages(pages: list[Page]) -> list[Page]:
    """Clean every page of one document and drop pages that are (nearly) empty."""
    drop = repeated_edge_lines(pages) if len(pages) >= 3 else set()
    cleaned = [Page(p.source_id, p.number, clean_text(p.text, drop)) for p in pages]
    return [p for p in cleaned if len(p.text) >= MIN_PAGE_CHARS]
