"""Builds the chunk file for the whole library: manifest -> fetch -> load -> clean -> chunk.

Run:  python -m ingest.build_chunks

Writes:
  data/chunks/chunks.jsonl     one chunk per line (the input of the search index in S2)
  data/chunks/stats.json       per source: pages, empty pages, chunks, Hindi chunks, chunks with doses
  data/chunks/spot_check.md    20 random chunks with their citations, for checking by hand
"""
import json
import random
from pathlib import Path

from ingest.chunk import make_chunks
from ingest.clean import clean_pages
from ingest.fetch import fetch_all, local_path
from ingest.load import load_pages
from ingest.manifest import load_manifest

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "chunks"
SPOT_CHECK_SIZE = 20
SPOT_CHECK_SEED = 7  # fixed, so the same 20 chunks come back on every rebuild


def build(out_dir: Path = OUT_DIR) -> dict:
    sources = load_manifest()
    fetched = {row["id"]: row for row in fetch_all(sources)}
    out_dir.mkdir(parents=True, exist_ok=True)
    all_chunks, stats = [], []
    for source in sources:
        row = fetched[source.id]
        if row["status"] == "failed":
            stats.append({"id": source.id, "status": "download failed", "error": row["error"]})
            continue
        if source.exclude:
            stats.append({"id": source.id, "status": "excluded", "reason": source.exclude})
            continue
        raw_pages = load_pages(source, local_path(source))
        pages = clean_pages(raw_pages)
        chunks = make_chunks(pages, source)
        all_chunks.extend(chunks)
        stats.append({
            "id": source.id,
            "status": "ok" if chunks else "no text (scanned PDF?)",
            "pages": len(raw_pages),
            "pages_with_text": len(pages),
            "chunks": len(chunks),
            "hindi_chunks": sum(c.language == "hi" for c in chunks),
            "dose_chunks": sum(c.contains_dose for c in chunks),
        })
    with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    summary = {
        "sources": len(sources),
        "sources_with_chunks": sum(1 for s in stats if s.get("chunks")),
        "chunks": len(all_chunks),
        "hindi_chunks": sum(c.language == "hi" for c in all_chunks),
        "dose_chunks": sum(c.contains_dose for c in all_chunks),
        "per_source": stats,
    }
    (out_dir / "stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sample = random.Random(SPOT_CHECK_SEED).sample(all_chunks, min(SPOT_CHECK_SIZE, len(all_chunks)))
    lines = ["# Spot check: 20 random chunks", ""]
    for c in sample:
        lines += [f"## {c.id}", f"{c.title}, page {c.page} | section: {c.section or '-'} | {c.language}"
                  f" | dose: {c.contains_dose}", "", "```", c.text, "```", ""]
    (out_dir / "spot_check.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = build()
    for s in result["per_source"]:
        print(f"{s['id']:34} {s['status']:24} pages={s.get('pages', '-'):>4} chunks={s.get('chunks', '-'):>5}"
              f" hi={s.get('hindi_chunks', '-'):>4} dose={s.get('dose_chunks', '-'):>4}")
    print(f"\nTOTAL sources={result['sources']} with_chunks={result['sources_with_chunks']} "
          f"chunks={result['chunks']} hindi={result['hindi_chunks']} dose={result['dose_chunks']}")
