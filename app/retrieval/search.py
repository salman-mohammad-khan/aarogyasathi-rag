"""Search: a user's question in, the 5 best chunks (with citations) out.

    question ──► rewrite.to_english ──► e5 query vector ──► Qdrant (meaning) ─┐
                                    └──────────────────────► BM25 (exact words) ─┴─► RRF ──► top 5 chunks

    searcher = Searcher()                       # opens data/index/qdrant, loads e5 (once, at startup)
    result = searcher.search("dengue ke lakshan kya hai")
    result.query          # "What are the symptoms of dengue?" (what was actually searched)
    result.chunks         # list of chunk dicts: text, title, page, url, section, contains_dose ...

`allow_dose=False` leaves out chunks that mention medicine doses (S3 decides when to use it).
"""
from dataclasses import dataclass, field

import numpy as np

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.index import COLLECTION, INDEX_DIR
from app.retrieval.keyword import KeywordIndex
from app.retrieval.rewrite import to_english

TOP_K = 5
CANDIDATES = 50  # how many results each method passes to the fusion step


@dataclass
class SearchResult:
    question: str  # as the user typed it
    query: str  # what was searched (English rewrite, or the question itself)
    chunks: list[dict] = field(default_factory=list)


class Searcher:
    def __init__(self, index_dir=INDEX_DIR, embedder=None, use_bm25: bool = True, rewrite=to_english):
        from qdrant_client import QdrantClient

        from app.retrieval.embedders import E5Embedder

        self.client = QdrantClient(path=str(index_dir))
        self.embedder = embedder or E5Embedder()
        self.rewrite = rewrite
        self.use_bm25 = use_bm25
        # All chunks in point-id order, for BM25 and for the dose filter on BM25 results.
        points, offset = [], None
        while True:
            batch, offset = self.client.scroll(COLLECTION, limit=1000, offset=offset, with_payload=True)
            points.extend(batch)
            if offset is None:
                break
        points.sort(key=lambda p: p.id)
        self.chunks = [p.payload for p in points]
        self.keyword = KeywordIndex([f"{c['title']}. {c.get('section', '')}\n{c['text']}" for c in self.chunks])

    def _dense(self, query: str, allow_dose: bool) -> list[int]:
        from qdrant_client import models

        no_dose = None if allow_dose else models.Filter(
            must_not=[models.FieldCondition(key="contains_dose", match=models.MatchValue(value=True))])
        hits = self.client.query_points(COLLECTION, query=self.embedder.embed_query(query).tolist(),
                                        query_filter=no_dose, limit=CANDIDATES).points
        return [h.id for h in hits]

    def _keyword(self, query: str, allow_dose: bool) -> list[int]:
        order = np.argsort(-self.keyword.scores(query))
        keep = (int(i) for i in order if allow_dose or not self.chunks[i]["contains_dose"])
        return [i for _, i in zip(range(CANDIDATES), keep)]

    def search(self, question: str, k: int = TOP_K, allow_dose: bool = True) -> SearchResult:
        query = self.rewrite(question)
        ranked = self._dense(query, allow_dose)
        if self.use_bm25:
            ranked = reciprocal_rank_fusion([ranked, self._keyword(query, allow_dose)])
        return SearchResult(question=question, query=query, chunks=[self.chunks[i] for i in ranked[:k]])

    def close(self):
        self.client.close()
