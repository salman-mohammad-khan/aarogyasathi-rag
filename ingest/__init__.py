"""Offline document pipeline: manifest -> fetch -> load -> clean -> chunk.

Run `python -m ingest.build_chunks` to download the documents in sources/manifest.yaml and write
data/chunks/chunks.jsonl. Nothing here runs inside the web app.
"""
