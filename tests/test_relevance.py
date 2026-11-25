"""The relevance gate refuses a retrieval result whose entry never mentions what was asked about."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import generator, intent, kb, relevance, retriever
from app.core import session as session_store
from app.core.router import process_message

kb.load()
intent.load()
generator._availability = False


def ask(text):
    s = session_store.get_session("relevance_test")
    s.clear()
    return process_message(text, session=s)


@pytest.mark.parametrize(
    "question",
    [
        "thyroid ke lakshan kya hote hain",
        "What are early signs of autism in toddlers?",
        "kidney kharab hone ke lakshan kya hain",
        "How are gallstones treated?",
        "What is the treatment for psoriasis?",
    ],
)
def test_topics_the_kb_does_not_cover_are_not_answered_from_a_wrong_card(question):
    r = ask(question)
    assert r["meta"]["intent"] not in ("retrieval", "disease_info"), (question, r["meta"])


@pytest.mark.parametrize(
    "question,entry",
    [
        ("How to stop mosquitoes from breeding in coolers and tyres?", "mosquito_control"),
        ("What can I do to avoid getting diabetes?", "diabetes_basics"),
        ("Why is chewing tobacco dangerous?", "tobacco_harm"),
        ("In which situations is wearing a mask recommended?", "mask_hygiene"),
        ("How can asthma attacks be controlled?", "asthma_basics"),
    ],
)
def test_close_paraphrases_of_a_faq_are_accepted(question, entry):
    results = retriever.retrieve(question)
    assert results, question
    top = results[0]
    assert top["id"] == entry, (question, top)
    assert relevance.accept(question, top, legacy_ok=False), (question, relevance.anchors(question))


def test_anchors_drop_filler_and_generic_words():
    assert relevance.anchors("What are the symptoms of dengue?") == {"dengue"}
    assert "thyroid" in relevance.anchors("thyroid ke lakshan kya hote hain")
    assert relevance.anchors("kya hota hai") == set()
