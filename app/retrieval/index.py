"""Builds the search index: every chunk's e5 vector plus its text and citation, stored in Qdrant.

Run once after `python -m ingest.build_chunks` (on the laptop, which has a GPU; about 1 minute):

    python -m app.retrieval.index

Qdrant runs in "local mode": no database server, just a folder (data/index/qdrant, about 25 MB) that the app
opens at startup. The folder is copied to the server with the app; it is not in git.

Each point in the collection is one chunk:
    vector  = e5 embedding of "title. section\\n text" (768 numbers)
    payload = the chunk's fields (id, text, title, publisher, url, page, section, language, layer, contains_dose)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
INDEX_DIR = ROOT / "data" / "index" / "qdrant"
COLLECTION = "library"


def build(chunks_path: Path = CHUNKS, index_dir: Path = INDEX_DIR, embedder=None) -> int:
    from qdrant_client import QdrantClient, models

    from app.retrieval.embedders import E5Embedder, passage_text

    chunks = [json.loads(line) for line in chunks_path.open(encoding="utf-8")]
    embedder = embedder or E5Embedder()
    vectors = embedder.embed_documents([passage_text(c) for c in chunks])

    index_dir.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(index_dir))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=vectors.shape[1],
                                                                            distance=models.Distance.COSINE))
    client.upload_points(COLLECTION, [models.PointStruct(id=i, vector=vectors[i].tolist(), payload=chunk)
                                      for i, chunk in enumerate(chunks)])
    count = client.count(COLLECTION).count
    client.close()
    return count


if __name__ == "__main__":
    print(f"Indexed {build()} chunks in {INDEX_DIR}")
