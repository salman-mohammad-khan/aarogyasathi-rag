"""Shared data types for the v2 document pipeline.

Every step passes these small objects to the next one, so each step can be read and tested on its own:

    Source (one entry in sources/manifest.yaml)
      -> Page   (text of one PDF page or one web page)
      -> Chunk  (a piece of a page, about 300 tokens, with everything needed to cite it)
"""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Source:
    """One document in the library, exactly as listed in sources/manifest.yaml."""

    id: str
    title: str
    publisher: str
    url: str
    type: str  # "pdf" or "html"
    language: str  # "en" or "hi"
    layer: str  # "A" community, "B" national guideline, "C" WHO fact sheet
    licence: str
    topics: tuple[str, ...] = ()
    exclude: str = ""  # reason the source is listed but not used, "" when it is used


@dataclass
class Page:
    """The text of one page. Web pages have a single page with number 1."""

    source_id: str
    number: int
    text: str


@dataclass
class Chunk:
    """A piece of a document small enough to search and quote, with its citation details."""

    id: str  # "<source id>#p<page>-c<n>", stable across rebuilds
    source_id: str
    title: str
    publisher: str
    url: str
    page: int
    section: str  # nearest heading above the chunk on its page, "" if none
    language: str  # "en" or "hi", detected from the chunk's own text
    layer: str
    text: str
    contains_dose: bool = False  # medicine doses found: never quoted in public answers
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
