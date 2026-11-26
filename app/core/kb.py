"""Fixed texts: curated health myths (data/kb/myths.json) and the bot's messages (data/kb/messages.json: emergency
and helpline replies, refusals, greetings, in several Indian languages). The disease, vaccine and FAQ cards of the
first version were removed in S6; answers now come from the document library (app/retrieval, app/answer)."""
import json

from app.config import KB_DIR, LANG_NAMES

_DB = None


def load():
    global _DB
    if _DB is not None:
        return _DB
    _DB = {}
    for name in ["myths", "messages"]:
        with open(KB_DIR / f"{name}.json", encoding="utf-8") as f:
            _DB[name] = json.load(f)
    return _DB


def myths():
    return load()["myths"]["myths"]


def messages():
    return load()["messages"]


def myth_meta():
    return load()["myths"]["meta"]


def msg(lang, key):
    table = messages()
    if lang in table and key in table[lang]:
        return table[lang][key]
    return table["en"].get(key, "")


def pick_lang(preferred, available):
    if preferred in available:
        return preferred
    if "hi" in available:
        return "hi"
    return "en"


def language_name(code):
    return LANG_NAMES.get(code, code)
