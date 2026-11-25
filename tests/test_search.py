"""Tests for the English rewrite and the Qdrant search, with a fake embedding model (no download, no network)."""
import json
import re
import zlib

import numpy as np
import pytest

from app.retrieval.rewrite import needs_rewrite, to_english


# --- rewrite --------------------------------------------------------------------------------------------------

def test_english_questions_are_not_sent_to_the_model():
    def ask(prompt):
        raise AssertionError("English must not call the model")

    assert to_english("What are the symptoms of dengue?", ask=ask) == "What are the symptoms of dengue?"


def test_hindi_and_hinglish_are_detected():
    assert needs_rewrite("डेंगू के लक्षण क्या हैं?")
    assert needs_rewrite("dengue ke lakshan kya hote hain")
    assert not needs_rewrite("Is ORS safe for a baby?")


def test_rewrite_uses_the_glossary_prompt_and_cleans_the_reply():
    seen = {}

    def ask(prompt):
        seen["prompt"] = prompt
        return '"What are the **symptoms** of heat stroke?"\nExtra line'

    assert to_english("loo lagne ke lakshan kya hai", ask=ask) == "What are the symptoms of heat stroke?"
    assert "loo / लू = heat stroke" in seen["prompt"] and seen["prompt"].endswith("loo lagne ke lakshan kya hai")


@pytest.mark.parametrize("reply", [None, "", "Dengue ke lakshan kya hote hain?", "x" * 400])
def test_unusable_rewrites_fall_back_to_the_question(reply):
    assert to_english("dengue ke lakshan kya hote hain", ask=lambda p: reply) == "dengue ke lakshan kya hote hain"


def test_model_errors_fall_back_to_the_question():
    def ask(prompt):
        raise TimeoutError

    assert to_english("बुखार में क्या करें?", ask=ask) == "बुखार में क्या करें?"


# --- index and search -----------------------------------------------------------------------------------------

class FakeEmbedder:
    """Bag of words hashed into 64 numbers: texts that share words get similar vectors."""

    name = "fake"

    def _vec(self, text):
        v = np.zeros(64, dtype=np.float32)
        for w in re.findall(r"[a-z]+", text.lower()):
            v[zlib.crc32(w.encode()) % 64] += 1
        return v / (np.linalg.norm(v) or 1)

    def embed_documents(self, texts):
        return np.array([self._vec(t) for t in texts])

    def embed_query(self, text):
        return self._vec(text)


CHUNKS = [
    {"id": "rabies#p1-c1", "text": "Wash a dog bite wound with soap and running water for 15 minutes.", "title": "Rabies"},
    {"id": "rabies#p2-c1", "text": "Rabies vaccine dose 0.1 ml intradermal on day 0, 3 and 7 after a dog bite.",
     "title": "Rabies", "contains_dose": True},
    {"id": "dengue#p1-c1", "text": "Dengue causes high fever, headache and pain behind the eyes.", "title": "Dengue"},
    {"id": "ors#p1-c1", "text": "Mix one ORS packet in one litre of clean drinking water.", "title": "Diarrhoea"},
]


@pytest.fixture()
def searcher(tmp_path):
    from app.retrieval.index import build
    from app.retrieval.search import Searcher

    chunks_file = tmp_path / "chunks.jsonl"
    rows = [{"source_id": c["id"].split("#")[0], "publisher": "WHO", "url": "https://example.org", "page": 1,
             "section": "", "language": "en", "layer": "C", "contains_dose": False, "topics": [], **c} for c in CHUNKS]
    chunks_file.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert build(chunks_file, tmp_path / "qdrant", embedder=FakeEmbedder()) == 4
    s = Searcher(tmp_path / "qdrant", embedder=FakeEmbedder(), rewrite=lambda q: q.replace("kutta kaate", "dog bite"))
    yield s
    s.close()


def test_search_returns_the_matching_chunk_first_with_its_citation(searcher):
    result = searcher.search("what to do after a dog bite wound", k=2)
    assert result.chunks[0]["id"] == "rabies#p1-c1"
    assert result.chunks[0]["url"] == "https://example.org" and result.chunks[0]["page"] == 1


def test_search_records_the_rewritten_query(searcher):
    result = searcher.search("kutta kaate to kya kare")
    assert result.question == "kutta kaate to kya kare" and result.query == "dog bite to kya kare"


def test_dose_chunks_can_be_left_out(searcher):
    ids = [c["id"] for c in searcher.search("rabies vaccine dose after dog bite", k=4, allow_dose=False).chunks]
    assert "rabies#p2-c1" not in ids and ids
    assert "rabies#p2-c1" in [c["id"] for c in searcher.search("rabies vaccine dose after dog bite", k=4).chunks]


def test_dense_only_mode_works(searcher):
    searcher.use_bm25 = False
    assert searcher.search("dengue fever headache", k=1).chunks[0]["id"] == "dengue#p1-c1"
