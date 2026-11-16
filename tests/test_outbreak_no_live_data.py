"""The bot has no live outbreak feed, so it must not show area alerts or invented advisories.

The old pincode lookup answered from a hand-written sample file and could present
"Chikungunya cases reported" for a state as if it were current. These tests pin the replacement:
an outbreak question gets an honest "no live data" reply that points to official sources.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import generator, intent, kb
from app.core import router
from app.core import session as session_store

kb.load()
intent.load()
generator._availability = False  # templates only, no LLM

QUESTIONS = [
    ("any outbreak near 110001", "110001"),
    ("Any dengue alert near me?", "110001"),
    ("Any dengue alert near me?", None),
    ("mere ilake mein koi bimari ka alert hai?", None),
]


def _reply(text, pincode=None, tag="x"):
    s = session_store.get_session("nolive_" + tag)
    return router.process_message(text, pincode=pincode, session=s)["text"]


@pytest.mark.parametrize("text,pincode", QUESTIONS)
def test_outbreak_question_gets_a_no_live_data_reply(text, pincode):
    reply = _reply(text, pincode, tag=text[:12])
    assert "live outbreak" in reply or "लाइव डेटा" in reply
    assert "NCDC" in reply
    # nothing from the old sample advisories or the news lookup
    for old in ("[ADVISORY]", "sample data", "Latest news", "Send your 6-digit pincode", "cases reported"):
        assert old not in reply


def test_pincode_is_not_used_to_pick_an_advisory():
    with_pin = _reply("any outbreak near 110001", "110001", tag="a")
    without_pin = _reply("any outbreak near 110001", None, tag="b")
    assert with_pin == without_pin


def test_outbreak_reply_keeps_the_disclaimer():
    assert kb.msg("en", "disclaimer").strip().splitlines()[0] in _reply("any outbreak near 110001", tag="c")


def test_greeting_and_help_no_longer_promise_area_alerts():
    for lang in kb.messages():
        for key in ("greeting", "help"):
            text = kb.msg(lang, key)
            assert "pincode" not in text.lower()
            assert "alert" not in text.lower()
    assert "पिनकोड" not in kb.msg("hi", "greeting")


def test_sample_advisory_data_is_gone():
    kb_dir = Path(__file__).resolve().parent.parent / "data" / "kb"
    for name in ("outbreaks.json", "pincodes.json", "alerts.json"):
        assert not (kb_dir / name).exists()
