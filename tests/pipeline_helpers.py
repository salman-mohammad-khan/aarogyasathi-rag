"""Shared helpers for tests that send messages through the v2 pipeline without network or models.

`ask(text, session)` runs app.pipeline.process_message with a fake library answerer and a fake fact-checker, so the
safety rules, guard and routing are tested exactly as they run in production, while the library and fact-check steps
only record that they were called.
"""
from app import pipeline
from app.answer.chain import Answer
from app.answer.factcheck import FactResult
from app.core import kb
from app.core import session as session_store

kb.load()


class FakeAnswerer:
    def __init__(self):
        self.calls = []

    def answer(self, question, lang=None):
        self.calls.append(question)
        return Answer(question=question, language=lang or "en", text="Library answer [1].", status="answered",
                      query=question, sources=[{"n": 1, "title": "Guideline", "publisher": "MoHFW", "page": 1,
                                                "url": "https://example.gov.in/g.pdf"}])


class FakeFactChecker:
    def __init__(self):
        self.calls = []

    def check(self, text, lang):
        self.calls.append(text)
        return FactResult(text, lang, "MYTH", "library", "Not true [1].",
                          sources=[{"n": 1, "title": "Guideline", "publisher": "MoHFW", "page": 1,
                                    "url": "https://example.gov.in/g.pdf"}])

    def curated(self, text, lang, plain=False):
        return None


answerer = FakeAnswerer()
fact_checker = FakeFactChecker()


def session(name):
    s = session_store.get_session(name)
    s.clear()
    return s


def ask(text, s=None):
    return pipeline.process_message(text, s or session("helper"), answerer, None, fact_checker)
