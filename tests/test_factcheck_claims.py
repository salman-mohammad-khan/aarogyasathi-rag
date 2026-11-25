"""Fact-check: the right myth for remedy claims, Hinglish claims, and plain claims without the prefix."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import generator, intent, kb
from app.core import session as session_store
from app.core.router import process_message
from app.factcheck import verifier

kb.load()
intent.load()
generator._availability = False
verifier._live_lookup = lambda claim, lang=None: None  # no network in tests


def ask(text):
    s = session_store.get_session("claim_test")
    s.clear()
    return process_message(text, session=s)


@pytest.mark.parametrize(
    "claim,verdict,fragment",
    [
        ("Garlic can cure dengue fever", "MYTH", "garlic"),
        ("Giloy juice cures dengue", "PARTLY_TRUE", "giloy"),
        ("Papaya leaf juice raises platelet count in dengue", "PARTLY_TRUE", "papaya"),
        ("lehsun khane se dengue theek ho jata hai", "MYTH", "garlic"),
        ("kutte ke kaatne par mirchi lagane se rabies nahi hota", "MYTH", "chilli"),
        ("garam paani peene se corona khatam ho jata hai", "MYTH", "hot"),
        ("BP normal aa jaye to dawai band kar sakte hain", "MYTH", "bp"),
    ],
)
def test_right_myth_matched(claim, verdict, fragment):
    r = verifier.verify_claim(claim)
    assert r["verdict"] == verdict, (claim, r["verdict"], (r.get("matched_claim") or {}).get("en"))


@pytest.mark.parametrize(
    "claim,fragment",
    [
        ("Garlic can cure dengue fever", "garlic"),
        ("Giloy juice cures dengue", "giloy"),
        ("lehsun khane se dengue theek ho jata hai", "garlic"),
    ],
)
def test_remedy_decides_the_matched_myth(claim, fragment):
    r = verifier.verify_claim(claim)
    assert fragment in (r.get("matched_claim") or {}).get("en", "").lower(), (claim, (r.get("matched_claim") or {}).get("en"))


@pytest.mark.parametrize(
    "claim",
    [
        "Garlic can cure dengue fever",
        "lehsun khane se dengue theek ho jata hai",
        "Dengue mosquitoes bite only at night",
        "Haldi can completely cure cancer",
        "kya lehsun se dengue theek hota hai",
        "Polio drops can make children infertile later in life",
    ],
)
def test_plain_claim_without_prefix_reaches_fact_check(claim):
    r = ask(claim)
    assert r["meta"]["intent"] == "fact_check", (claim, r["meta"])
    assert r["meta"].get("route") == "claim_detect"


@pytest.mark.parametrize(
    "text",
    [
        "What are the symptoms of dengue?",
        "How does malaria spread and how can it be prevented?",
        "dengue ke lakshan kya hain",
        "Can dengue be treated at home?",
        "My child has loose motions, what should I do at home?",
        "When should I take the second dose of the vaccine?",
        "I have fever and headache",
    ],
)
def test_information_questions_are_not_claims(text):
    r = ask(text)
    assert r["meta"].get("route") != "claim_detect", (text, r["meta"])


def test_unknown_plain_claim_is_not_judged():
    r = ask("Wearing a copper bracelet cures arthritis")
    assert r["meta"].get("route") != "claim_detect"


def test_prefixed_unknown_claim_is_still_unverifiable():
    r = verifier.verify_claim("Wearing a copper bracelet cures arthritis")
    assert r["verdict"] in ("UNVERIFIABLE", "PARTLY_TRUE", "MYTH")
