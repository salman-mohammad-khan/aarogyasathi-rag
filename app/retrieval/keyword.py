"""Keyword search with BM25 (rank-bm25 library).

BM25 scores a chunk higher when it contains the question's words, especially rare words ("chikungunya",
"tourniquet"), and does not reward long chunks just for being long. It finds exact names and terms that
embedding models can miss, and costs nothing to run.
"""
import re

from rank_bm25 import BM25Okapi

# Letters and digits in Latin or Devanagari script; everything else (including the danda "।") separates words.
_WORD = re.compile(r"[a-z0-9ऀ-ॣ०-ॿ]+")

# Very common English and Hinglish words that say nothing about the topic.
STOPWORDS = frozenset("""
a an the is are was were be been of to in on at for and or with by from as it this that what which how why
when who do does did can could should would i my me we our you your he she they them his her their
not no if so than then there here into about over after before
kya hai hain hota hote hoti ka ki ke ko se me mein par aur ya to bhi jo kaise kab kyu kyun kitne kaun
""".split())


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


class KeywordIndex:
    def __init__(self, texts: list[str]):
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])

    def scores(self, query: str):
        """One BM25 score per indexed text (0 when no word matches)."""
        return self.bm25.get_scores(tokenize(query))
