"""Splits clean pages into chunks: the pieces that are searched, given to the model and cited.

Size: about 1,200 characters (roughly 300 English tokens) with 180 characters of overlap (15%). Small enough that the
search can point at one topic and the model gets five chunks in its prompt; large enough to hold a full answer such as
a symptom list. The overlap keeps a sentence that crosses a boundary readable in both chunks.

How: LangChain's RecursiveCharacterTextSplitter tries to cut at paragraph breaks first, then line breaks, then
sentence ends (English "." and Hindi "।"), and only then inside a sentence. Each page is split separately, so every
chunk belongs to exactly one page and its citation can name that page.
"""
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.types import Chunk, Page, Source

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180
MIN_CHUNK_CHARS = 80  # shorter leftovers (a lone heading, a table fragment) are not worth searching

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_CHARS,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", "। ", ". ", "? ", "! ", "; ", ", ", " ", ""],
    keep_separator="end",
)

_DEVANAGARI = re.compile("[ऀ-ॿ]")
_LETTER = re.compile(r"[^\W\d_]")
# Medicine doses: "500 mg", "10 mg/kg", "2 tablets twice a day", "IU", "ml per kg"...
_DOSE = re.compile(
    r"\b\d+(\.\d+)?\s*(mg|mcg|µg|g|ml|iu|units?)\b(\s*/\s*kg)?"
    r"|\b(mg|ml)\s*/\s*kg\b"
    r"|\b\d+\s*(tablets?|tabs?|capsules?|drops?)\b.{0,30}\b(daily|a day|per day|times|twice|thrice|od|bd|tds)\b",
    re.IGNORECASE,
)
# A heading line: numbered ("3.2 Clinical features"), or short and in capitals ("CLINICAL FEATURES").
_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+){0,3}\.?\s+[A-Za-zऀ-ॿ][^.]{2,80}$")


def detect_language(text: str) -> str:
    """'hi' when at least 30% of the letters are Devanagari, otherwise 'en'."""
    letters = _LETTER.findall(text)
    if not letters:
        return "en"
    return "hi" if len(_DEVANAGARI.findall(text)) / len(letters) >= 0.3 else "en"


def contains_dose(text: str) -> bool:
    return bool(_DOSE.search(text))


def is_heading(line: str) -> bool:
    line = line.strip()
    if not 3 <= len(line) <= 90:
        return False
    if _NUMBERED_HEADING.match(line):
        return True
    letters = [c for c in line if c.isalpha() and c.isascii()]
    return len(letters) >= 4 and all(c.isupper() for c in letters) and not line.endswith(".")


def headings_by_offset(text: str) -> list[tuple[int, str]]:
    """(character offset, heading text) for every heading line on a page, in order."""
    found, offset = [], 0
    for line in text.splitlines(keepends=True):
        if is_heading(line):
            found.append((offset, line.strip()))
        offset += len(line)
    return found


def make_chunks(pages: list[Page], source: Source) -> list[Chunk]:
    """Split every page of one source into chunks that carry the source's citation details."""
    chunks: list[Chunk] = []
    section = ""
    for page in pages:
        headings = headings_by_offset(page.text)
        search_from = 0
        for n, piece in enumerate(_SPLITTER.split_text(page.text), 1):
            piece = piece.strip()
            if len(piece) < MIN_CHUNK_CHARS:
                continue
            start = page.text.find(piece[:60], search_from)
            if start >= 0:
                search_from = start + 1
                before = [h for off, h in headings if off <= start]
                if before:
                    section = before[-1]
            chunks.append(Chunk(
                id=f"{source.id}#p{page.number}-c{n}",
                source_id=source.id,
                title=source.title,
                publisher=source.publisher,
                url=source.url,
                page=page.number,
                section=section,
                language=detect_language(piece),
                layer=source.layer,
                text=piece,
                contains_dose=contains_dose(piece),
                topics=list(source.topics),
            ))
    return chunks
