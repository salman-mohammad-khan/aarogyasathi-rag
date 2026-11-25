"""Reciprocal Rank Fusion (RRF): merge several ranked lists into one.

Each list gives every chunk a rank (1 = best). A chunk's fused score is the sum of 1 / (k + rank) over the
lists. Only the ranks are used, not the raw scores, so a BM25 score (0 to ~30) and a cosine similarity
(0 to 1) can be combined without any scaling. k = 60 is the value from the original paper
(Cormack, Clarke and Buettcher, SIGIR 2009); it stops one list's first place from dominating.
"""
from collections import defaultdict

RRF_K = 60


def reciprocal_rank_fusion(ranked_lists: list[list[int]], k: int = RRF_K, depth: int = 50) -> list[int]:
    """ranked_lists: chunk positions, best first, one list per search method. Returns the fused order."""
    scores = defaultdict(float)
    for ranking in ranked_lists:
        for rank, chunk in enumerate(ranking[:depth], start=1):
            scores[chunk] += 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
