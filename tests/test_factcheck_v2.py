"""Tests for the v2 fact-checker (S5) with fake search, fake models and a fake curated match (no network)."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.answer import factcheck as fc_module
from app.answer.factcheck import FactChecker, FactResult
from app.factcheck import verifier

CHUNK = {"title": "IDCF Guidelines 2017", "publisher": "NHM", "page": 12, "url": "https://nhm.gov.in/idcf.pdf",
         "text": "If the child vomits, wait 10 minutes and give ORS more slowly. Do not stop ORS."}


def searcher(chunks):
    return SimpleNamespace(search=lambda q: SimpleNamespace(query=q, chunks=chunks))


def llm(reply):
    return RunnableLambda(lambda p: AIMessage(content=reply))


def checker(lib_chunks=(), web_chunks=(), reply="", risk="LOW", web=True):
    fc = FactChecker.__new__(FactChecker)  # skip __init__: it would load the myth index with e5
    fc.searcher, fc.web = searcher(list(lib_chunks)), (searcher(list(web_chunks)) if web else None)
    fc.llm, fc.ask_risk = llm(reply), (lambda prompt: risk)
    return fc


@pytest.fixture(autouse=True)
def no_curated(monkeypatch):
    monkeypatch.setattr(verifier, "verify_claim", lambda *a, **k: {"verdict": "UNVERIFIABLE", "claim": a[0]})


def test_curated_myth_is_used_first(monkeypatch):
    monkeypatch.setattr(verifier, "verify_claim", lambda *a, **k: {
        "verdict": "VERIFIED", "claim": "dengue spreads by aedes", "explanation": {"en": "Aedes mosquitoes spread it."},
        "sources": [{"name": "WHO Dengue Factsheet", "tier": 1}]})
    r = checker(reply="unused").check("fact check: dengue spreads by aedes", "en")
    assert r.verdict == "TRUE" and r.basis == "curated" and "VERIFIED" in r.text() and "WHO Dengue" in r.text()


def test_library_verdict_with_citation():
    r = checker([CHUNK], reply="VERDICT: MYTH\nEXPLANATION: Do not stop ORS when a child vomits [1].").check(
        "fact check: ORS should be stopped if the child vomits", "en")
    assert r.verdict == "MYTH" and r.basis == "library" and r.sources[0]["page"] == 12
    assert "Based on 1 official document" in r.text()


def test_verdict_without_citation_is_not_shown():
    r = checker([CHUNK], reply="VERDICT: MYTH\nEXPLANATION: Do not stop ORS.", risk="HIGH").check("claim x y z", "en")
    assert r.basis == "none" and r.verdict == "NOT_ENOUGH_EVIDENCE"


def test_trusted_website_when_the_library_has_nothing():
    web_chunk = {**CHUNK, "publisher": "NHS (UK)", "page": None, "url": "https://www.nhs.uk/x"}

    class Judge:
        calls = 0

        def __call__(self, prompt):
            Judge.calls += 1
            return AIMessage(content="VERDICT: NOT_ENOUGH_EVIDENCE\nEXPLANATION: -" if Judge.calls == 1 else
                             "VERDICT: MYTH\nEXPLANATION: The NHS says this is not true [1].")

    fc = checker([CHUNK], [web_chunk])
    fc.llm = RunnableLambda(Judge())
    r = fc.check("fact check: something the library does not cover", "en")
    assert r.basis == "trusted_web" and r.sources[0]["url"] == "https://www.nhs.uk/x"


def test_model_view_only_says_likely_myth_and_is_labelled():
    r = checker(reply="VERDICT: LIKELY_MYTH\nEXPLANATION: There is no good evidence for this; see a doctor.",
                web=False).check("fact check: lemon water burns belly fat", "en")
    assert r.verdict == "LIKELY_MYTH" and r.basis == "general" and "not from a verified source" in r.text()


def test_model_view_may_never_say_true():
    r = checker(reply="VERDICT: TRUE\nEXPLANATION: It works.", web=False).check("fact check: lemon water x", "en")
    assert r.verdict == "NOT_ENOUGH_EVIDENCE" and r.basis == "none"


def test_no_model_view_for_high_risk_claims():
    r = checker(reply="VERDICT: LIKELY_MYTH\nEXPLANATION: no.", risk="HIGH", web=False).check(
        "fact check: cow urine cures cancer", "en")
    assert r.basis == "none" and "ask a doctor" in r.text()


def test_medicine_amounts_are_removed_from_explanations():
    r = checker([CHUNK], reply="VERDICT: MYTH\nEXPLANATION: Keep giving ORS [1].\nGive 500 mg paracetamol twice a day [1]."
                ).check("fact check: stop ORS when vomiting", "en")
    assert "500 mg" not in r.text() and r.basis == "library"


def test_no_confidence_percentage_in_the_api():
    api = FactResult("c", "en", "MYTH", "library", "x [1]", sources=[{**CHUNK, "n": 1}]).api()
    assert api["confidence"] is None and api["basis"] == "library" and api["verdict"] == "MYTH"


def test_labels_exist_in_every_language():
    for lang in ("en", "hi", "hinglish"):
        assert set(fc_module.LABELS[lang]) == set(fc_module.LABELS["en"])
        assert all(lang in v for v in fc_module.BASIS.values())


def test_pipeline_sends_fact_check_requests_to_the_v2_checker(monkeypatch):
    from app import pipeline
    from app.core import kb, safety_llm
    from app.core.session import Session

    kb.load()
    monkeypatch.setattr(safety_llm, "start", lambda text: None)

    class FakeChecker:
        def check(self, text, lang):
            return FactResult("papaya cures dengue", lang, "MYTH", "library", "No [1].", sources=[{**CHUNK, "n": 1}])

        def curated(self, text, lang, plain=False):
            return None

    reply = pipeline.process_message("fact check: papaya leaf cures dengue", Session("f"), None, None, FakeChecker())
    assert reply["meta"]["intent"] == "fact_check" and reply["meta"]["factcheck"]["basis"] == "library"
    assert reply["meta"]["sources"][0]["page"] == 12


def test_one_paragraph_explanations_lose_only_the_dose_sentence():
    from app.answer.checks import remove_dose_sentences

    text = ("Zinc is given for 14 days [1]. It is for children aged 2 months to 5 years [5]. The dose is half tablet "
            "for 2-6 months and full tablet after that [3].")
    assert remove_dose_sentences(text) == "Zinc is given for 14 days [1]. It is for children aged 2 months to 5 years [5]."
