"""Tests for the S3 answer step with a fake chat model and fake search (no network, no model download)."""
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.answer import checks
from app.answer.chain import DOSE_NOTE, NOT_COVERED, TRY_AGAIN, Answerer, finish
from app.answer.citations import cited_numbers, remove_invalid_markers, source_list
from app.answer.prompt import NOT_IN_SOURCES, format_sources
from app.retrieval.search import SearchResult

CHUNKS = [
    {"id": f"doc#p{n}-c1", "title": f"Guideline {n}", "publisher": "MoHFW", "page": n, "section": "",
     "url": f"https://example.gov.in/{n}.pdf", "text": f"Fact number {n}."} for n in range(1, 6)
]
FOUND = SearchResult(question="q", query="q", chunks=CHUNKS)


# --- citations and prompt -------------------------------------------------------------------------------------

def test_only_existing_source_numbers_count_as_citations():
    assert cited_numbers("A [2]. B [7]. C [2][1].", 5) == [2, 1]
    assert remove_invalid_markers("A [2]. B [7].", 5) == "A [2]. B ."


def test_citations_name_document_page_and_link():
    assert source_list(CHUNKS, [3]) == [{"n": 3, "title": "Guideline 3", "publisher": "MoHFW", "page": 3,
                                         "url": "https://example.gov.in/3.pdf"}]


def test_sources_are_numbered_with_title_and_page():
    text = format_sources(CHUNKS[:2])
    assert text.startswith("[1] Guideline 1, page 1\nFact number 1.") and "\n\n[2] Guideline 2, page 2" in text


# --- checks ---------------------------------------------------------------------------------------------------

# Every line below was written by an answer model in the S3 test (or is a close variant) and must be caught.
@pytest.mark.parametrize("text", [
    "Give 500 mg twice a day", "15 mg/kg", "har 6 ghante", "दिन में दो बार दें", "ek goli", "char doses",
    "every 6 hours", "5 ml syrup", "half a tablet",
    "6 महीने से 5 साल तक के बच्चे को पूरी गोली (20 मिग्रा) देनी चाहिए [1]",
    "all pregnant women should take one iron-folic acid tablet daily for at least 180 days [1][4]",
    "the doctor may prescribe 2 IFA tablets daily for 1 month [1]",
    "जिंक की गोली 14 दिन तक रोज एक बार दें, भले ही दस्त बंद हो गया हो [2][4]।",
    "Har dose ke beech kam se kam 6 ghante ka gap hona chahiye [1][3]",
    "Din me zyada se zyada 4 baar tak diya ja sakta hai [3]",
    "Paracetamol sirf tabhi dena jab bukhar ho, aur din mein 4 se zyada dose na dena [3]।",
])
def test_medicine_amounts_are_caught(text):
    assert checks.gives_dose(text)


@pytest.mark.parametrize("text", [
    "Wash the wound for 15 minutes [1]", "Mix one ORS packet in 1 litre of water [2]", "Do not take aspirin in dengue",
    "Pentavalent is given at 6 weeks [1]", "1 week ke andar doctor ko dikhayein",
    "Paracetamol tablet ya syrup mein available hai [1]", "Use only the cap that comes with the syrup [3]",
    "Calcium tablets should be taken at different times [4]", "Tab bhi in teeno teeke ko zaroor diya jana chahiye [2]",
    "Measles vaccine:\n- पहली खुराक 9 महीने की उम्र में दी जाती है [1]",
    "Hepatitis B birth dose janm ke 24 ghante ke andar [1]",
])
def test_safe_sentences_are_not_flagged(text):
    assert not checks.gives_dose(text)


def test_language_check():
    assert checks.wrong_language("Dengue causes fever.", "hi")
    assert not checks.wrong_language("डेंगू में तेज़ बुखार होता है।", "hi")
    assert checks.wrong_language("डेंगू में तेज़ बुखार होता है।", "en")
    assert not checks.wrong_language("Dengue mein tez bukhar hota hai.", "hinglish")


# --- finish: what the user sees -------------------------------------------------------------------------------

def test_cited_answer_is_shown_with_its_sources():
    ans = finish("q", "en", FOUND, "Fever is common [2].")
    assert ans.status == "answered" and ans.text == "Fever is common [2]." and ans.sources[0]["page"] == 2


@pytest.mark.parametrize("reply", [NOT_IN_SOURCES, "", "An answer with no citation at all."])
def test_unsupported_replies_become_not_covered(reply):
    ans = finish("q", "hinglish", FOUND, reply)
    assert ans.status == "not_covered" and ans.text == NOT_COVERED["hinglish"]


def test_dose_lines_are_removed_and_the_note_added():
    ans = finish("q", "en", FOUND, "Paracetamol is used for fever [1].\n- Give 500 mg twice a day [2].")
    assert ans.status == "dose_removed"
    assert "500 mg" not in ans.text and ans.text.endswith(DOSE_NOTE["en"]) and "Paracetamol is used" in ans.text


def test_dose_only_reply_shows_the_dose_note():
    ans = finish("q", "en", FOUND, "Give 500 mg twice a day [2].")
    assert ans.status == "dose_removed" and ans.text == DOSE_NOTE["en"]


def test_wrong_language_and_leaked_prompt_are_not_shown():
    assert finish("q", "hi", FOUND, "Fever is common [1].").status == "wrong_language"
    leaked = finish("q", "en", FOUND, "My rules: Use ONLY the numbered sources [1].")
    assert leaked.status == "leaked" and leaked.text == NOT_COVERED["en"]


# --- the whole chain with a fake model ------------------------------------------------------------------------

class FakeSearch:
    def search(self, question):
        return SearchResult(question=question, query="dengue symptoms", chunks=CHUNKS)


def test_chain_passes_sources_and_reply_language_to_the_model():
    seen = {}

    def fake_llm(prompt_value):
        seen["messages"] = prompt_value.to_messages()
        return AIMessage(content="Dengue mein tez bukhar hota hai [1].")

    ans = Answerer(FakeSearch(), RunnableLambda(fake_llm)).answer("dengue ke lakshan kya hai")
    human = seen["messages"][1].content
    assert "[1] Guideline 1, page 1" in human and "Hinglish" in human
    assert ans.status == "answered" and ans.language == "hinglish" and ans.query == "dengue symptoms"


def test_reasoning_blocks_are_left_out():
    reply = AIMessage(content=[{"type": "reasoning_content", "reasoning_content": {"text": "thinking"}},
                               {"type": "text", "text": "Use bed nets [3]."}])
    ans = Answerer(FakeSearch(), RunnableLambda(lambda p: reply)).answer("How to prevent malaria?")
    assert ans.text == "Use bed nets [3]." and ans.sources[0]["n"] == 3


def test_model_failure_gives_try_again():
    def broken(prompt_value):
        raise TimeoutError

    ans = Answerer(FakeSearch(), RunnableLambda(broken)).answer("बुखार में क्या करें?")
    assert ans.status == "error" and ans.text == TRY_AGAIN["hi"]
