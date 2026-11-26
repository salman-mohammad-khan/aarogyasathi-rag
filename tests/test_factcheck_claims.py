"""Fact-check: the right curated myth for remedy claims, Hinglish claims, and plain claims without the prefix.

Uses the real e5 model (downloaded by scripts/setup.py, as in CI) because these tests are about the matching itself;
the library, website and model steps are not used (no network)."""
import pytest

from app import pipeline
from app.answer.factcheck import FactChecker
from app.core import kb, safety_llm
from app.factcheck import verifier
from app.retrieval.embedders import E5Embedder
from tests.pipeline_helpers import FakeAnswerer, session

kb.load()
_e5 = E5Embedder()
verifier.use_embedder("e5", _e5.embed_queries)


class CuratedOnly:
    """The real curated-myth step of the v2 fact-checker, without the library, websites or models."""

    def __init__(self):
        self.checker = FactChecker.__new__(FactChecker)

    def curated(self, text, lang, plain=False):
        return FactChecker.curated(self.checker, text, lang, plain)

    def check(self, text, lang):
        return self.curated(text, lang)


@pytest.fixture(autouse=True)
def no_model_check(monkeypatch):
    monkeypatch.setattr(safety_llm, "start", lambda text: None)


def ask(text):
    return pipeline.process_message(text, session("claim_test"), FakeAnswerer(), None, CuratedOnly())


@pytest.mark.parametrize(
    "claim,verdict",
    [
        ("Garlic can cure dengue fever", "MYTH"),
        ("Giloy juice cures dengue", "PARTLY_TRUE"),
        ("Papaya leaf juice raises platelet count in dengue", "PARTLY_TRUE"),
        ("lehsun khane se dengue theek ho jata hai", "MYTH"),
        ("kutte ke kaatne par mirchi lagane se rabies nahi hota", "MYTH"),
        ("garam paani peene se corona khatam ho jata hai", "MYTH"),
        ("BP normal aa jaye to dawai band kar sakte hain", "MYTH"),
    ],
)
def test_right_myth_matched(claim, verdict):
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


@pytest.mark.parametrize("claim", ["Wearing a copper bracelet cures arthritis", "Onion in socks cures fever",
                                   "Neem leaves cure diabetes completely"])
def test_unknown_plain_claims_are_not_judged(claim):
    assert ask(claim)["meta"].get("route") != "claim_detect"


@pytest.mark.parametrize("claim", ["मलेरिया की दवा बुखार उतरते ही बंद कर देनी चाहिए",
                                   "malaria ki dawai bukhar utarte hi band kar do"])
def test_a_malaria_claim_does_not_get_the_bp_myth(claim):
    assert verifier.verify_claim(claim)["verdict"] == "UNVERIFIABLE"


@pytest.mark.parametrize("claim", ["dengue ek insaan se dusre insaan ko chhoone se failta hai",
                                   "TB spreads through the air when a patient coughs"])
def test_a_different_spread_route_does_not_take_the_curated_verdict(claim):
    # S6 final evaluation: "dengue spreads by touch" got VERIFIED from the "Aedes mosquitoes transmit dengue" entry,
    # and "TB spreads through the air" got MYTH from the "TB spreads by touch" myth. They now go to the library judge.
    assert verifier.verify_claim(claim)["verdict"] == "UNVERIFIABLE"


def test_the_same_route_still_matches():
    assert verifier.verify_claim("TB chhoone se ya bartan share karne se failta hai")["verdict"] == "MYTH"
