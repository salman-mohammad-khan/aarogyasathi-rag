"""Answers beyond the library (S4b): tier 2 trusted website, then tier 3 labelled general information.

    library says "not covered"
      -> tier 2: WebSearcher + the same answer chain (prompt allows a partial answer from the page)
      -> tier 3: only if both risk gates say LOW: short general answer + fixed "not from a verified source" note
      -> otherwise the "not covered, ask your ASHA worker or doctor" reply stands
"""
from dataclasses import replace

from app.answer import general
from app.answer.chain import NOT_COVERED, Answer, Answerer, default_llm
from app.answer.prompt import WEB_ANSWER_PROMPT
from app.answer.trusted_web import WebSearcher

RISK_MODEL_ID = "google.gemma-3-27b-it"


def _gemma_ask():
    from botocore.config import Config
    from langchain_aws import ChatBedrockConverse

    llm = ChatBedrockConverse(model=RISK_MODEL_ID, region_name="ap-south-1", temperature=0, max_tokens=8,
                              config=Config(read_timeout=6, connect_timeout=3, retries={"max_attempts": 1}))
    return lambda prompt: llm.invoke(prompt).text


class OutsideLibrary:
    def __init__(self, web_answerer=None, general_llm=None, ask_risk=None):
        self.web = web_answerer or Answerer(WebSearcher(), prompt=WEB_ANSWER_PROMPT)
        self.general_llm = general_llm or default_llm()
        self.ask_risk = ask_risk or _gemma_ask()

    def answer(self, question: str, lang: str, english: str, library: Answer) -> Answer:
        """Called only when the library answer is "not covered"; returns the best labelled answer, or `library`."""
        if general.asks_which_medicine(question) or general.asks_which_medicine(english):
            # "Which antibiotic is best?": choosing a medicine is a doctor's job (middle rule), so no website or general
            # answer is searched for it.
            return replace(library, text=general.CHOOSE_MEDICINE[lang], status="not_covered", tier="none")
        label = general.risk_label(question, english, self.ask_risk)  # one short Gemma call, ~0.5 s
        if label == "NOT_HEALTH":  # "write a poem", "capital of India": no web search, no general answer
            return replace(library, text=NOT_COVERED[lang], status="not_covered", tier="none")
        web = self.web.answer(question, lang=lang)
        if web.status in ("answered", "dose_removed") and web.sources:
            return replace(web, tier="trusted_web", seconds=library.seconds + web.seconds)
        if label == "LOW":
            text = general.general_answer(question, lang, self.general_llm)
            if text:
                return replace(library, text=text, status="general", tier="general", sources=[])
        return replace(library, text=NOT_COVERED[lang], status="not_covered", tier="none")
