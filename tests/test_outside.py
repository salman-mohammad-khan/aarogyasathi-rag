"""Tests for S4b: trusted-website tier and labelled general information, with fakes (no network, no model)."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.answer import general
from app.answer.chain import NOT_COVERED, Answer, Answerer
from app.answer.outside import OutsideLibrary
from app.answer.prompt import WEB_ANSWER_PROMPT, format_sources
from app.answer.trusted_web import WebSearcher, publisher, search_trusted

TIPS = ["Wash the affected area with a mild soap and lukewarm water.", "Do not wash more than needed, it can irritate.",
        "Do not squeeze spots, as this can leave scars.", "Remove make-up before going to bed.",
        "Use water-based products that do not block pores.", "Keep hair clean and away from the face.",
        "Most people with acne see it improve with simple care over a few months.",
        "See a pharmacist or doctor if the spots are painful, widespread or leave marks."]
PAGE = ("<html><head><title>Acne - NHS</title></head><body><article>"
        + "".join(f"<p>{t}</p>" for t in TIPS) + "</article></body></html>")


def fake_get(url):
    return SimpleNamespace(status_code=200, headers={"content-type": "text/html"}, content=PAGE.encode(), text=PAGE,
                           url=url)


def fake_search(results):
    def search(query, backend):
        if isinstance(results, Exception):
            raise results
        return [{"href": h} for h in results]
    return search


# --- trusted sites ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url, name", [
    ("https://www.nhs.uk/conditions/acne/", "NHS (UK)"), ("https://medlineplus.gov/acne.html", "MedlinePlus (US NLM)"),
    ("https://www.who.int/news-room/fact-sheets/detail/malaria", "WHO"), ("https://www.mayoclinic.org/acne", None),
    ("https://nhs.uk.evil.example/acne", None), ("https://fakenhs.uk/acne", None),
])
def test_only_allowlisted_sites_count(url, name):
    assert publisher(url) == name


def test_search_keeps_only_trusted_links_and_tries_the_next_engine():
    calls = []

    def search(query, backend):
        calls.append(backend)
        if backend == "auto":
            raise RuntimeError("No results found.")
        return [{"href": "https://www.webmd.com/acne"}, {"href": "https://www.nhs.uk/conditions/acne/"}]

    assert search_trusted("acne", search) == ["https://www.nhs.uk/conditions/acne/"]
    assert calls[:2] == ["auto", "bing"]


def test_web_searcher_returns_page_chunks_with_link_and_publisher():
    ws = WebSearcher(rewrite=lambda q: q, search=fake_search(["https://www.nhs.uk/conditions/acne/"]), get=fake_get)
    result = ws.search("how to wash face with acne")
    assert result.chunks and result.chunks[0]["url"] == "https://www.nhs.uk/conditions/acne/"
    assert result.chunks[0]["publisher"] == "NHS (UK)" and result.chunks[0]["page"] is None
    assert format_sources(result.chunks).startswith("[1] Acne, NHS (UK)\n")  # trafilatura drops " - NHS"


def test_nothing_found_gives_no_chunks():
    ws = WebSearcher(rewrite=lambda q: q, search=fake_search(RuntimeError("No results found.")), get=fake_get)
    assert ws.search("anything").chunks == []


def test_web_prompt_allows_a_partial_answer():
    text = WEB_ANSWER_PROMPT.format_messages(sources="[1] x", question="q", language="English")[1].content
    assert "even if it answers only part of it" in text


# --- general information ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "which tablet for headache", "pregnancy mein kya khaye", "my baby has rashes", "bachche ko neend nahi aati",
    "I feel depressed all the time", "blood in urine", "do I have diabetes?", "seene mein dard", "गर्भ में बच्चा",
])
def test_high_risk_questions_never_reach_the_model(question):
    def ask(prompt):
        raise AssertionError("the model must not be asked")

    assert not general.is_low_risk(question, question, ask)


def test_low_risk_needs_the_model_to_say_low():
    assert general.is_low_risk("how to reduce dandruff", "how to reduce dandruff", lambda p: "LOW")
    assert not general.is_low_risk("how to reduce dandruff", "how to reduce dandruff", lambda p: "HIGH")
    assert not general.is_low_risk("write a poem about rain", "write a poem about rain", lambda p: "NOT_HEALTH")
    assert not general.is_low_risk("how to reduce dandruff", "how to reduce dandruff", lambda p: (_ for _ in ()).throw(TimeoutError()))


def test_general_answer_is_labelled_and_checked():
    ok = RunnableLambda(lambda p: AIMessage(content="Wash your hair gently with a mild shampoo."))
    assert general.general_answer("dandruff", "en", ok).endswith(general.GENERAL_NOTE["en"])
    dose = RunnableLambda(lambda p: AIMessage(content="Take 500 mg twice a day."))
    assert general.general_answer("dandruff", "en", dose) is None
    wrong_lang = RunnableLambda(lambda p: AIMessage(content="Wash your hair gently."))
    assert general.general_answer("dandruff", "hi", wrong_lang) is None


# --- the tier order -----------------------------------------------------------------------------------------------

LIBRARY_MISS = Answer(question="q", language="en", text=NOT_COVERED["en"], status="not_covered", query="q")


class FakeWebAnswerer:
    def __init__(self, answer):
        self.result = answer

    def answer(self, question, lang=None):
        return self.result


def test_trusted_website_comes_first():
    web = Answer(question="q", language="en", text="Wash twice a day [1].", status="answered", tier="library",
                 sources=[{"n": 1, "title": "Acne", "publisher": "NHS (UK)", "page": None, "url": "https://www.nhs.uk/x"}])
    out = OutsideLibrary(FakeWebAnswerer(web), general_llm=None, ask_risk=lambda p: "LOW")
    result = out.answer("acne tips", "en", "acne tips", LIBRARY_MISS)
    assert result.tier == "trusted_web" and result.sources


def test_general_answer_only_for_low_risk_when_the_web_has_nothing():
    llm = RunnableLambda(lambda p: AIMessage(content="Keep your scalp clean and dry."))
    out = OutsideLibrary(FakeWebAnswerer(LIBRARY_MISS), general_llm=llm, ask_risk=lambda p: "LOW")
    result = out.answer("how to reduce dandruff", "en", "how to reduce dandruff", LIBRARY_MISS)
    assert result.tier == "general" and result.text.endswith(general.GENERAL_NOTE["en"])
    risky = out.answer("dandruff during pregnancy", "en", "dandruff during pregnancy", LIBRARY_MISS)
    assert risky.tier == "none" and risky.text == NOT_COVERED["en"]


def test_pages_for_health_professionals_are_not_used():
    assert publisher("https://www.cdc.gov/group-a-strep/hcp/clinical-guidance/strep-throat.html") is None
    assert publisher("https://www.cdc.gov/group-a-strep/about/strep-throat.html") == "CDC (US)"


@pytest.mark.parametrize("question", ["Which antibiotic is best for a throat infection?", "kaunsi dawai lu bukhar ke liye",
                                      "सर दर्द के लिए कौन सी दवा लें?", "best tablet for headache"])
def test_choosing_a_medicine_is_never_answered_outside_the_library(question):
    class NoWeb:
        def answer(self, question, lang=None):
            raise AssertionError("no web search when a medicine is to be chosen")

    out = OutsideLibrary(NoWeb(), general_llm=None, ask_risk=lambda p: "LOW")
    lang = "hi" if "दवा" in question else ("hinglish" if "dawai" in question else "en")
    result = out.answer(question, lang, question, LIBRARY_MISS)
    assert result.tier == "none" and result.text == general.CHOOSE_MEDICINE[lang]


def test_side_effect_questions_are_not_medicine_choices():
    assert not general.asks_which_medicine("what are the side effects of iron tablets")


def test_non_health_questions_skip_the_web_search():
    class NoWeb:
        def answer(self, question, lang=None):
            raise AssertionError("no web search for a non-health question")

    out = OutsideLibrary(NoWeb(), general_llm=None, ask_risk=lambda p: "NOT_HEALTH")
    assert out.answer("write a poem", "en", "write a poem", LIBRARY_MISS).tier == "none"


def test_pipeline_asks_outside_only_when_the_library_has_no_answer(monkeypatch):
    from app import pipeline
    from app.core import kb, safety_llm
    from app.core.session import Session

    kb.load()
    monkeypatch.setattr(safety_llm, "start", lambda text: None)
    asked = []

    class Outside:
        def answer(self, question, lang, english, library):
            asked.append(question)
            return Answer(question=question, language=lang, text="General tip.", status="general", tier="general")

    hit = Answerer(SimpleNamespace(search=lambda q: SimpleNamespace(query=q, chunks=[
        {"title": "T", "page": 1, "url": "https://x.gov.in", "text": "t"}])),
        RunnableLambda(lambda p: AIMessage(content="From the library [1].")))
    reply = pipeline.process_message("how to prevent malaria", Session("a"), hit, Outside())
    assert reply["meta"]["tier"] == "library" and asked == []
    miss = Answerer(SimpleNamespace(search=lambda q: SimpleNamespace(query=q, chunks=[])),
                    RunnableLambda(lambda p: AIMessage(content="unused")))
    reply = pipeline.process_message("how to reduce dandruff", Session("b"), miss, Outside())
    assert reply["meta"]["tier"] == "general" and asked == ["how to reduce dandruff"]
