"""Reads sources/manifest.yaml, the list of official documents in the library.

Why a manifest: the documents themselves stay out of git (their licences differ and they are large), but the list of
what is in the library, where it came from and under which licence is reviewable code. Anyone can rebuild the same
library from it.
"""
from pathlib import Path

import yaml

from app.types import Source

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "sources" / "manifest.yaml"
REQUIRED = ("id", "title", "publisher", "url", "type", "language", "layer", "licence")


def load_manifest(path: Path = MANIFEST_PATH) -> list[Source]:
    """Return every source in the manifest, after checking that each entry is complete and ids are unique."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    sources, seen = [], set()
    for entry in entries:
        missing = [key for key in REQUIRED if not entry.get(key)]
        if missing:
            raise ValueError(f"manifest entry {entry.get('id', '?')} is missing {missing}")
        if entry["id"] in seen:
            raise ValueError(f"duplicate manifest id {entry['id']}")
        if entry["type"] not in ("pdf", "html"):
            raise ValueError(f"{entry['id']}: type must be pdf or html")
        if not entry["url"].startswith("https://"):
            raise ValueError(f"{entry['id']}: url must be https")
        seen.add(entry["id"])
        sources.append(Source(**{**entry, "topics": tuple(entry.get("topics") or ())}))
    return sources
