"""Decides whether the best retrieval result really answers the question.

Embeddings alone cannot do this: LaBSE scored "thyroid ke lakshan" closest to the cholera card (0.69) and "early signs of
autism" closest to pregnancy signs (0.86). The check here asks a second, plain question: do the question's own key words
(after dropping filler like "what", "kya", "symptoms") appear in the entry? A match needs a fair similarity and the key
words present; a result whose entry never mentions what was asked about is refused, so the bot says it has no verified
information instead of answering from the wrong card.
"""
import re

from app.core import kb

SIM_MIN = 0.55  # below this the entry is too far from the question to answer it
ANCHOR_MIN_RATIO = 0.34  # at least this share of the key words must appear in the entry

_FOLD = {
    "lehsun": "lahsun", "theek": "thik", "thek": "thik", "tike": "teeka", "tika": "teeka",
    "bachche": "bachcha", "bacche": "bachcha", "bache": "bachcha", "baccha": "bachcha", "bacha": "bachcha",
    "machhar": "machchar", "machar": "machchar", "paani": "pani", "khaane": "khana", "khane": "khana",
    "dawai": "dawa", "dawaai": "dawa", "peeliya": "peliya", "jaanch": "jaach", "ilaj": "ilaaj",
    "diarrhea": "diarrhoea", "anemia": "anaemia", "hemoglobin": "haemoglobin",
}

_STOP = set(
    """a an the of in on at to for from with and or but is are was were be been being do does did can could should would will
    shall may might must i me my we our you your he she it they them his her their this that these those there here what which
    who whom whose when where why how if then than so too very just also about into over under up down out off not no yes get
    got give gives take takes make makes use used using have has had having need needs want wants know like want please tell
    ka ke ki ko me mein se hai hain hota hote hoti ho hoga hogi hona kya kaise kab kaun kitna kitne kitni kyun kyu kyon par
    pe aur ya to bhi nahi nahin mat koi kuch sab apne mera meri mere mujhe hum hume tum aap woh wo ye yeh iska uska ise use
    wala wali wale raha rahi rahe karna karein kare karen kar karo kiya gaya gayi chahiye chahie sakta sakti sakte liye lie
    tak jab tab agar toh bahut zyada kam bohot kaafi thoda
    का के की को में से है हैं होता होते होती हो होगा क्या कैसे कब कौन कितना कितने कितनी क्यों पर और या तो भी नहीं कोई कुछ सब
    अपने मेरा मेरी मेरे मुझे हम तुम आप वह यह इसका उसका वाला वाली वाले रहा रही रहे करना करें करे कर किया गया चाहिए सकता सकती सकते
    लिए तक जब तब अगर बहुत ज़्यादा कम
    """.split()
)

# Words that appear in almost every health question and say nothing about the topic.
_GENERIC = set(
    """symptom symptoms sign signs treatment treat cure cured prevent prevention preventing care help remedy remedies home tips
    tip way ways method best good bad safe safely avoid early first main common basic basics important importance effect
    effects cause causes reason reasons risk health healthy medicine medical disease infection problem condition issue
    manage management control relief improve better lakshan lakshano ilaaj upay upaay bachav tarika tareeka kaaran bimari
    bimaari dawa swasthya sehat rog kya hota hote
    लक्षण इलाज उपाय बचाव तरीका कारण बीमारी दवा स्वास्थ्य रोग सेहत
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9ऀ-ॿ]+")
_entry_cache = {}


def _stem(w):
    for suffix in ("ing", "es", "ed", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _tokens(text):
    out = set()
    for w in _TOKEN.findall((text or "").lower()):
        w = _FOLD.get(w, w)
        out.add(_stem(w))
    return out


def anchors(question):
    """The key words of the question: everything except filler and generic health words."""
    result = set()
    for w in _TOKEN.findall((question or "").lower()):
        w = _FOLD.get(w, w)
        if w in _STOP or w in _GENERIC or len(w) < 3 and w.isascii():
            continue
        s = _stem(w)
        if s in _STOP or s in _GENERIC:
            continue
        result.add(s)
    return result


def _flatten(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _flatten(v)


def _entry_tokens(top):
    key = (top["type"], top["id"])
    if key in _entry_cache:
        return _entry_cache[key]
    toks = set()
    if top["type"] == "disease":
        for d in kb.diseases():
            if d["id"] == top["id"]:
                for part in ("names", "summary", "symptoms", "prevention", "first_aid", "when_to_seek", "hinglish"):
                    for text in _flatten(d.get(part, "")):
                        toks |= _tokens(text)
    elif top["type"] == "faq":
        for f in kb.faqs():
            if f["id"] == top["id"]:
                for part in ("q", "a", "topics"):
                    for text in _flatten(f.get(part, "")):
                        toks |= _tokens(text)
    _entry_cache[key] = toks
    return toks


def accept(question, top, legacy_ok=False):
    """True when the retrieval result `top` (a dict with type, id, similarity) answers `question`.

    legacy_ok is the old lexical-overlap verdict; it can still accept a close match, but it can no longer rescue a result
    whose entry does not mention what the question is about.
    """
    key_words = anchors(question)
    entry = _entry_tokens(top)
    if not key_words:
        return legacy_ok
    matched = sum(1 for w in key_words if w in entry)
    if matched == 0:
        return False
    if len(key_words) >= 2 and matched / len(key_words) < ANCHOR_MIN_RATIO:
        return False
    return legacy_ok or top.get("similarity", 0.0) >= SIM_MIN
