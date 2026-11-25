"""Tests for the S2 search pieces that need no model download or network: keywords, fusion, answer key."""
import numpy as np

from app.retrieval.embedders import passage_text
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword import KeywordIndex, tokenize
from eval.retrieval_bakeoff import is_relevant


def test_tokenize_drops_filler_words_and_keeps_hindi():
    assert tokenize("Dengue ke lakshan kya hote hain?") == ["dengue", "lakshan"]
    assert tokenize("डेंगू के लक्षण") == ["डेंगू", "के", "लक्षण"]


def test_keyword_index_ranks_the_matching_text_first():
    index = KeywordIndex(["Wash a dog bite with soap and water.", "Use bed nets against malaria.",
                          "ORS for diarrhoea."])
    assert int(np.argmax(index.scores("what to do after a dog bite"))) == 0


def test_rrf_rewards_chunks_found_by_both_methods():
    dense = [1, 2, 3]
    keyword = [3, 1, 4]
    # 1: 1/61 + 1/62, 3: 1/63 + 1/61, 2: 1/62, 4: 1/63
    assert reciprocal_rank_fusion([dense, keyword]) == [1, 3, 2, 4]


def test_passage_text_puts_title_and_section_first():
    chunk = {"title": "IDCF Guidelines", "section": "Diarrhoea", "text": "Give ORS after every loose stool."}
    assert passage_text(chunk).startswith("IDCF Guidelines. Diarrhoea\n")
    assert passage_text({**chunk, "section": ""}).startswith("IDCF Guidelines\n")


def test_answer_key_needs_source_and_phrases():
    topic = {"sources": ["who-rabies"], "any": ["soap", "wash"], "all": ["bite"]}
    assert is_relevant(topic, {"source_id": "who-rabies", "text": "Wash the bite wound for 15 minutes."})
    assert not is_relevant(topic, {"source_id": "who-dengue", "text": "Wash the bite wound."})
    assert not is_relevant(topic, {"source_id": "who-rabies", "text": "Wash hands often."})
