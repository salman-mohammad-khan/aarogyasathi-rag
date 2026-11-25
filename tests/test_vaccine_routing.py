"""Vaccine questions: right card, exact-age windows, and no vaccine card for non-vaccine questions."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import entities, generator, intent, kb
from app.core import session as session_store
from app.core.router import _age_gap, _age_to_milestones, process_message

kb.load()
intent.load()
generator._availability = False


def ask(text):
    s = session_store.get_session("vaccine_test")
    s.clear()
    return process_message(text, session=s)


@pytest.mark.parametrize(
    "text,marker",
    [
        ("When is the DPT booster due?", "DPT BOOSTER"),
        ("DPT booster dose kitni umar me lagti hai", ("DPT BOOSTER", "डीपीटी")),
        ("How many doses of the COVID vaccine are needed?", "COVID VACCINE"),
        ("corona ka tika kitne dose lagte hain", ("COVID VACCINE", "कोविड")),
        ("hepatitis b ka tika janm ke baad kab lagta hai", ("HEPATITIS B", "हेपेटाइटिस")),
        ("Why is an injectable polio vaccine given besides drops?", "IPV"),
        ("At what age is the BCG vaccine given?", "BCG"),
    ],
)
def test_right_vaccine_card(text, marker):
    r = ask(text)
    assert r["meta"]["intent"] == "vaccination", (text, r["meta"])
    markers = marker if isinstance(marker, tuple) else (marker,)
    assert any(m.lower() in r["text"].lower() for m in markers), (text, r["text"][:300])


@pytest.mark.parametrize(
    "text",
    [
        "What are the first symptoms when a woman becomes pregnant?",
        "pregnancy ka pata kaise chalta hai",
        "my baby is 3 months old and has fever and cough",
        "mere bachche ko 2 saal se khansi hai",
    ],
)
def test_non_vaccine_questions_do_not_get_a_vaccine_card(text):
    r = ask(text)
    assert r["meta"]["intent"] != "vaccination", (text, r["meta"])


def test_pregnancy_tetanus_is_a_vaccine_question():
    assert _age_to_milestones("which tetanus injection should a pregnant woman take") == "pregnancy"
    assert _age_to_milestones("pregnancy me kaun sa tika lagta hai") == "pregnancy"
    assert _age_to_milestones("early signs of pregnancy") is None


@pytest.mark.parametrize(
    "text,milestone",
    [
        ("my baby is 6 weeks old which vaccines are due", "6_weeks"),
        ("mera baccha 6 hafte ka hai kaun se tike lagenge", "6_weeks"),
        ("baby is 10 weeks vaccines", "10_weeks"),
        ("my baby is 3 months old which vaccine is due", "14_weeks"),
        ("child is 10 months old vaccine", "9_12_months"),
        ("child is 18 months old vaccines due", "16_24_months"),
        ("my child is 5 years old which vaccine", "5_6_years"),
        ("my son is 10 years old vaccine", "10_years"),
    ],
)
def test_exact_age_windows(text, milestone):
    assert _age_to_milestones(text) == milestone, text


@pytest.mark.parametrize(
    "text",
    [
        "my baby is 5 months old which vaccine is due",
        "my child is 3 years old which vaccine is due",
        "bacche ki umar 3 saal hai kaun sa tika lagwana hai",
    ],
)
def test_gap_ages_say_nothing_is_due_instead_of_a_wrong_card(text):
    assert _age_to_milestones(text) is None
    assert _age_gap(text)
    r = ask(text)
    assert r["meta"]["intent"] == "vaccination"
    assert "no vaccine due" in r["text"] or "कोई टीका तय नहीं" in r["text"], r["text"][:300]


def test_longest_alias_wins():
    assert entities.find_vaccine("when is the dpt booster given") == "dpt_booster"
    assert entities.find_vaccine("pentavalent or dpt vaccine") == "pentavalent"
