"""Downloads each manifest source into data/raw/ and records what was downloaded.

A file that is already on disk is not downloaded again. data/raw/fetch_log.json keeps, per source: the URL, the local
file, its size, its SHA-256 checksum and the date, so the library can be traced and rebuilt exactly.
"""
import hashlib
import json
import time
from pathlib import Path

import httpx

from app.types import Source

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
LOG_PATH = RAW_DIR / "fetch_log.json"
# A plain browser user agent: some government servers refuse requests without one.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AarogyaSathi-ingest"}
TIMEOUT_S = 120


def local_path(source: Source, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"{source.id}.{source.type}"


def download(source: Source, raw_dir: Path = RAW_DIR) -> dict:
    """Download one source if it is not on disk yet. Returns a log record; never raises for network errors."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = local_path(source, raw_dir)
    record = {"id": source.id, "url": source.url, "file": path.name}
    if path.exists() and path.stat().st_size > 0:
        data = path.read_bytes()
        return {**record, "status": "cached", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        resp = httpx.get(source.url, headers=HEADERS, timeout=TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        data = resp.content
        if source.type == "pdf" and not data.startswith(b"%PDF"):
            raise ValueError(f"not a PDF (content-type {resp.headers.get('content-type')})")
        path.write_bytes(data)
    except Exception as exc:
        return {**record, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}
    return {
        **record,
        "status": "downloaded",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "fetched_at": time.strftime("%Y-%m-%d"),
    }


def fetch_all(sources: list[Source], raw_dir: Path = RAW_DIR) -> list[dict]:
    """Download every source and write data/raw/fetch_log.json."""
    log = [download(source, raw_dir) for source in sources]
    (raw_dir / "fetch_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log


if __name__ == "__main__":
    from ingest.manifest import load_manifest

    for row in fetch_all(load_manifest()):
        size = f"{row['bytes'] / 1e6:.1f} MB" if "bytes" in row else row.get("error", "")
        print(f"{row['status']:10} {row['id']:34} {size}")
