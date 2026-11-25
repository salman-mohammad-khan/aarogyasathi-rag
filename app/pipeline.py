"""The v2 message pipeline: what happens to one chat message, in order.

    1. empty message                 -> short help text
    2. emergency or self-harm words  -> emergency / helpline reply (rules; no model, no search)
    3. instruction override          -> fixed refusal (rules; no model sees the text)
    4. fact-check request or a known myth -> v1 fact-check (moves onto the library in S5)
    5. greeting                      -> greeting
    6. everything else               -> v2: follow-up joining -> search (S2) -> cited answer (S3)
    In parallel with 6, the model safety check (Gemma) looks for emergencies the word rules missed; if it finds
    one, its emergency reply replaces the answer.

Steps 2-5 reuse the tested v1 safety code (app/core/safety.py, guard.py, safety_llm.py, factcheck/). Only step 6 is
new. Which pipeline runs is set by PIPELINE in .env ("v2" default, "v1" = the old router, kept until S6 so a bad
deploy can be undone by changing one line).
"""
import re
import time

from app.core import entities, guard, kb, language, safety, safety_llm
from app.core.router import FACT_TRIGGERS, _model_safety_result
from app.factcheck import verifier
from app.retrieval.rewrite import question_language

GREETINGS = {"hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "नमस्कार", "हैलो", "हाय"}

# Emergencies where first aid matters while help is on the way: the emergency reply stays on top and the cited
# first-aid answer from the library is added below it. (Snake bite already has first aid in the v1 reply.)
# "heat stroke" is matched by the v1 "stroke" rule, so it is recognised here by its own words.
FIRST_AID_FLAGS = {"rabid_animal"}
_HEAT_STROKE = re.compile(r"heat\s*stroke|heatstroke|sun\s*stroke|\bloo\b|लू", re.IGNORECASE)


def needs_first_aid(text: str, red_flags: list[str]) -> bool:
    if red_flags and set(red_flags) <= FIRST_AID_FLAGS:
        return True
    return red_flags == ["stroke"] and bool(_HEAT_STROKE.search(text))

# --- follow-up questions ------------------------------------------------------------------------------------------
FOLLOW_UP_MAX_WORDS = 7
FOLLOW_UP_WINDOW_S = 600  # a follow-up must come within 10 minutes of the question it continues
_FOLLOW_UP_START = re.compile(
    r"^(and|also|what about|how about|or|but|aur|ya|lekin|phir|to|toh|isme|ismein|iske|iska|uske|uska|usme|"
    r"और|या|लेकिन|फिर|तो|इसमें|इसके|इसका|उसके|उसका|उसमें)\b", re.IGNORECASE)
_FOLLOW_UP_WORDS = re.compile(
    r"\b(it|this|that|they|them|these|those|iska|iski|iske|uska|uski|uske|isme|usme|ye|yeh|wo|woh)\b|"
    r"इसका|इसकी|इसके|उसका|उसकी|उसके|इसमें|उसमें|यह|ये|वह|वो", re.IGNORECASE)


def is_follow_up(text: str) -> bool:
    """A short message that only makes sense with the previous question: "aur bachchon mein?", "what about it?"."""
    if len(text.split()) > FOLLOW_UP_MAX_WORDS:
        return False
    if _FOLLOW_UP_START.search(text.strip()):
        return True
    # "is it contagious?" continues the last question; "what is this rash?" names its own topic and does not.
    names_topic = entities.find_disease(text) is not None or bool(entities.find_symptoms(text))
    return bool(_FOLLOW_UP_WORDS.search(text)) and not names_topic


def with_context(text: str, session) -> str:
    """Join a follow-up to the previous question so search and the answer model see the whole question."""
    last = session.get("last_question")
    asked_at = session.get("last_question_at") or 0
    if last and time.time() - asked_at < FOLLOW_UP_WINDOW_S and is_follow_up(text):
        return f"{last.rstrip(' ?।')}? {text}"
    return text


# --- the pipeline -------------------------------------------------------------------------------------------------

def _v1_lang(text: str) -> str:
    """The language code the v1 safety and fact-check replies use ("hi" also for Hinglish)."""
    lang = language.detect_language(text)
    return "hi" if lang == "en" and language.transliterate_hint(text) else lang


def _reply(text, intent, lang, **meta):
    return {"text": text, "meta": {"intent": intent, "lang": lang, **meta}}


def _rules_first(text: str, session) -> dict | None:
    """Steps 2-5. Returns a reply, or None when the message should be answered from the library."""
    lang = _v1_lang(text)
    lower = text.lower()
    red_flags = safety.check_red_flags(text)
    if red_flags:
        session.clear()
        lang = safety.emergency_language(text, lang)
        if safety.is_self_harm(red_flags):
            return _reply(safety.self_harm_response(lang), "emergency", lang, red_flags=red_flags)
        reply = safety.emergency_response(lang, red_flags)
        if any(t in lower for t in FACT_TRIGGERS):
            reply += "\n\n" + safety.fact_check_note(lang)
        return _reply(reply, "emergency", lang, red_flags=red_flags, first_aid=needs_first_aid(text, red_flags))
    if guard.is_injection(text):
        session.clear()
        return _reply(kb.msg(lang, "guard_refusal"), "guard", lang, route="rule")
    if any(t in lower for t in FACT_TRIGGERS):
        session.clear()
        result = verifier.verify_claim(text, lang)
        return _reply(verifier.format_verdict(result, lang), "fact_check", lang, verdict=result["verdict"],
                      factcheck=result)
    if verifier.looks_like_claim(text):
        result = verifier.verify_claim(text, lang, strict_remedy=True, allow_live=False, plain=True)
        if result.get("verdict") not in ("UNVERIFIABLE", "INVALID", None):
            session.clear()
            return _reply(verifier.format_verdict(result, lang), "fact_check", lang, verdict=result["verdict"],
                          factcheck=result, route="claim_detect")
    if lower.strip(" !.?") in GREETINGS:
        return _reply(kb.msg(lang, "greeting"), "greeting", lang)
    return None


def process_message(text: str, session, answerer) -> dict:
    """One chat message in, {"text", "meta"} out (same shape as the v1 router, plus meta["sources"])."""
    text = (text or "").strip()
    if not text:
        return _reply(kb.msg("en", "help"), "help", "en")
    safety_check = safety_llm.start(text)  # runs in the background while the reply is prepared
    reply = _rules_first(text, session)
    if reply is not None and reply["meta"]["intent"] == "emergency":
        # The word rules fired; the model check is not needed and never overrides them.
        if reply["meta"].get("first_aid"):
            answer = answerer.answer(text, lang=question_language(text))
            if answer.sources:  # only a cited library answer is added; otherwise the emergency reply stands alone
                reply["text"] += "\n\n" + answer.text
                reply["meta"].update(flow="emergency_first_aid", sources=answer.sources, query=answer.query)
        return reply
    if reply is None:
        question = with_context(text, session)
        answer = answerer.answer(question, lang=question_language(text))
        session.set("last_question", question[:300])
        session.set("last_question_at", time.time())
        reply = _reply(answer.text, "library_answer", answer.language, flow=answer.status, generator="v2",
                       sources=answer.sources, query=answer.query, follow_up=question != text)
    label = safety_llm.result(safety_check)
    if label in ("EMERGENCY", "SELF_HARM"):
        session.clear()
        return _model_safety_result(text, _v1_lang(text), label)
    return reply
