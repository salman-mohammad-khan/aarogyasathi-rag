"""Regression tests: medicine dose questions get a fixed "ask a pharmacist or doctor" reply.

Bug: "Can I take paracetamol 5 times a day?" was routed as a symptom report, and the model invented a fever and
named typhoid, tuberculosis and rabies. The bot must not advise on doses and must not invent symptoms.
Ordinary symptom messages and plain medicine mentions must keep their existing behaviour.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import entities, generator, intent, kb
from app.core import router
from app.core import session as session_store

kb.load()
intent.load()
generator._availability = False  # templates only, no LLM

INVENTED = ("typhoid", "tuberculosis", "rabies", "dengue", "malaria")


def _ask(text, name="dose-test"):
    s = session_store.get_session(name)
    s.clear()
    return router._process_message_core(text, s)


@pytest.mark.parametrize("text", [
    "Can I take paracetamol 5 times a day?",
    "How many tablets of ibuprofen can I take?",
    "What is the dose of crocin for adults?",
    "paracetamol kitni baar le sakte hain",
    "dolo 650 kitni baar din mein leni chahiye",
    "पैरासिटामोल दिन में कितनी बार लें",
    "मुझे कितनी गोली लेनी चाहिए",
])
def test_dose_questions_get_the_fixed_reply(text):
    result = _ask(text)
    assert result["meta"]["intent"] == "dose_question"
    assert result["meta"].get("flow") is None
    reply = result["text"].lower()
    assert "pharmacist" in reply or "फ़ार्मासिस्ट" in result["text"]
    assert not any(word in reply for word in INVENTED)


def test_dose_question_does_not_start_a_symptom_flow():
    s = session_store.get_session("dose-flow")
    s.clear()
    router._process_message_core("Can I take paracetamol 5 times a day?", s)
    assert s.get("symptom_flow") is None


@pytest.mark.parametrize("text", [
    "I have fever and headache",
    "mujhe bukhar hai aur jodon mein dard hai",
    "Tell me about dengue",
    "Is paracetamol used for dengue fever?",
    "How to prevent malaria",
    "Vaccines for 6 week baby",
])
def test_normal_questions_are_not_dose_questions(text):
    assert not entities.is_dose_question(text)
    assert _ask(text)["meta"]["intent"] != "dose_question"


def test_symptom_chat_still_starts_the_symptom_flow():
    result = _ask("I have fever and headache")
    assert result["meta"]["intent"] == "symptom_check"
    assert result["meta"]["flow"] == "symptom_probe"


def test_emergency_still_wins_over_a_dose_question():
    result = _ask("my father has chest pain, how many aspirin tablets should he take")
    assert result["meta"]["intent"] == "emergency"
