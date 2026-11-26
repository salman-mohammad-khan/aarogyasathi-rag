import json
import re

import numpy as np

from app.config import KB_DIR
from app.core import kb

_CLAIM_PREFIX = re.compile(
    r"^(fact\s*check\s*:?\s*|verify\s*(this\s*)?(message\s*)?:?\s*|check\s*this\s*:?\s*|kya\s+ye\s+sach\s+hai\s*:?\s*|फैक्ट\s*चेक\s*:?\s*|क्या\s*यह\s*सच\s*है\s*:?\s*|फैक्ट चेक\s*:?\s*)",
    re.IGNORECASE,
)
_FORWARD_PREFIX = re.compile(r"^(forwarded|forwarded message|फॉरवर्डेड)\s*:?\s*", re.IGNORECASE)

_index = None

# Which embedding model matches claims to the curated myths: e5, already loaded for search (set by
# app/answer/factcheck.py with use_embedder). Each model has its own similarity scale, so thresholds are per model
# (e5's were tuned on the claim tests, docs/v2/BUILD_LOG.md S5). LaBSE, used until S5, was removed in S6.
_embed_texts = None  # a function: list of texts -> L2-normalised vectors
_embed_name = None
MATCH_THRESHOLDS = {
    # (similarity, overlap) pairs: a match needs one pair satisfied; "plain" is the extra bar for claims typed
    # without "fact check"; below "remedy_sure", a different remedy in the matched myth blocks the match.
    "e5": {"pairs": ((0.885, 0.25), (0.94, 0.0)), "plain": (0.885, 0.10), "remedy_sure": 0.97},
}


def use_embedder(name, embed_texts):
    """Match claims with another embedding model (v2: e5). Rebuilds the myth index on next use."""
    global _embed_texts, _embed_name, _index
    _embed_texts, _embed_name, _index = embed_texts, name, None


def _vectors(texts, cache_name=None):
    if _embed_texts is None:
        raise RuntimeError("call verifier.use_embedder(...) first (app/answer/factcheck.py does it at startup)")
    return np.asarray(_embed_texts(texts), dtype=np.float32)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "can", "cure", "cures", "cure", "cured",
    "prevents", "prevent", "preventing", "of", "to", "and", "or", "for", "with", "by", "does",
    "do", "help", "good", "bad", "you", "i", "it", "in", "on", "that", "this", "your", "my",
    "what", "how", "why", "when", "where", "which", "who", "whom", "its", "treatment", "treat",
    "treats", "treated", "symptoms", "symptom", "cause", "causes", "caused", "prevention",
    "manage", "managing", "management", "tell", "about", "please", "know", "want", "need",
    "explain", "give", "some", "any", "me",
    "कर", "करता", "करती", "करते", "है", "हैं", "का", "के", "की", "को", "और", "यह", "वह",
    "में", "पर", "नहीं", "होता", "होती", "होते", "जाता", "जाती", "जाते", "देता", "देती",
    "से", "सब", "लिए", "क्या", "कि",
}

DISEASE_CANONICAL = {
    "covid": "covid",
    "corona": "covid",
    "coronavirus": "covid",
    "covid19": "covid",
    "covid-19": "covid",
    "कोविड": "covid",
    "कोरोना": "covid",
    "tb": "tb",
    "tuberculosis": "tb",
    "टीबी": "tb",
    "क्षय": "tb",
    "tapedik": "tb",
    "dengue": "dengue",
    "डेंगू": "dengue",
    "malaria": "malaria",
    "मलेरिया": "malaria",
    "typhoid": "typhoid",
    "टाइफाइड": "typhoid",
    "cholera": "cholera",
    "हैज़ा": "cholera",
    "हैजा": "cholera",
    "cancer": "cancer",
    "कैंसर": "cancer",
    "tumour": "cancer",
    "tumor": "cancer",
    "diabetes": "diabetes",
    "मधुमेह": "diabetes",
    "sugar": "diabetes",
    "rabies": "rabies",
    "रेबीज़": "rabies",
    "aids": "hiv",
    "hiv": "hiv",
    "एचआईवी": "hiv",
    "एड्स": "hiv",
    "hepatitis": "hepatitis",
    "jaundice": "hepatitis",
    "पीलिया": "hepatitis",
    "हेपेटाइटिस": "hepatitis",
    "polio": "polio",
    "पोलियो": "polio",
    "pneumonia": "pneumonia",
    "निमोनिया": "pneumonia",
    "measles": "measles",
    "खसरा": "measles",
    "heart attack": "cardiac",
    "stroke": "cardiac",
    "लकवा": "cardiac",
    # Added in S5: without these, "Neem leaves cure diabetes" matched the curated "neem cures chickenpox" myth,
    # because the chickenpox entry had no disease word for the conflict check to compare.
    "chickenpox": "chickenpox",
    "chicken pox": "chickenpox",
    "chhoti mata": "chickenpox",
    "छोटी माता": "chickenpox",
    "arthritis": "arthritis",
    "gathiya": "arthritis",
    "गठिया": "arthritis",
    "asthma": "asthma",
    "dama": "asthma",
    "दमा": "asthma",
    "thyroid": "thyroid",
    "थायरॉइड": "thyroid",
    # Live S5 check: "मलेरिया की दवा बुखार उतरते ही बंद कर देनी चाहिए" matched the curated "stop BP medicine once
    # normal" myth and showed its BP explanation, because BP had no disease word for the conflict check.
    "bp": "bp",
    "blood pressure": "bp",
    "hypertension": "bp",
    "बीपी": "bp",
    "रक्तचाप": "bp",
    "kidney stone": "kidney_stone",
    "pathri": "kidney_stone",
    "पथरी": "kidney_stone",
}

SEVERE_DISEASES = {"cancer", "tb", "rabies", "hiv", "cholera", "pneumonia", "polio", "cardiac"}

CURE_TERMS = [
    "cure", "cures", "curing", "cured", "treat", "treats", "treatment",
    "heal", "heals", "healing", "eradicate", "kill", "kills", "killing",
    "theek", "thik", "khatam", "khatm", "ilaj", "ilaaj", "jad se", "jar se", "dawa", "dawai",
    "इलाज", "ठीक", "जड़ से", "खत्म", "दवा"
]


def _disease_keys(s):
    s_lower = s.lower()
    keys = set()
    for alias, canonical in DISEASE_CANONICAL.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", s_lower) or (len(alias) >= 4 and alias in s_lower):
            keys.add(canonical)
    return keys


def _stem_token(w):
    w = w.lower()
    for suffix in ("ing", "es", "ed", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


# Romanised Hindi has no fixed spelling. Common variants are folded together so that "lehsun" and "lahsun", or "theek"
# and "thik", count as the same word when claims are compared.
_HINGLISH_NORM = {
    "lehsun": "lahsun", "lasun": "lahsun", "lahasun": "lahsun",
    "theek": "thik", "thek": "thik", "tik": "thik",
    "tike": "teeka", "tika": "teeka", "teeka": "teeka",
    "bachche": "bachcha", "bacche": "bachcha", "bache": "bachcha", "baccha": "bachcha", "bacha": "bachcha",
    "machhar": "machchar", "machar": "machchar", "macchar": "machchar",
    "paani": "pani", "khaane": "khana", "khane": "khana", "kaatta": "katta", "kaatne": "katne",
    "jaata": "jata", "jaati": "jati", "hoti": "hota", "hote": "hota",
    "dawai": "dawa", "dawaai": "dawa", "peeliya": "peliya",
}


def _content_overlap(claim, ref):
    def tokens(s):
        raw = re.findall(r"[a-z0-9\u0900-\u097F]+", s.lower())
        raw = [_HINGLISH_NORM.get(w, w) for w in raw]
        return {_stem_token(w) for w in raw if w not in _STOPWORDS}
    a = tokens(claim)
    b = tokens(ref)
    if not a or not b:
        return 0.0
    common = len(a & b)
    dice = (2.0 * common) / (len(a) + len(b))
    query_cov = common / len(a)
    return min(dice, query_cov)


_REMEDY_KEYWORDS = [
    "kadha", "giloy", "tulsi", "haldi", "turmeric", "ginger", "adrak", "honey", "lemon",
    "garlic", "lahsun", "neem", "chyawanprash", "jeera", "ajwain", "saunf", "herbal",
    "natural remedy", "immunity", "immune", "boost", "remedy", "gharelu", "nuskha",
    "काढ़ा", "गिलोय", "तुलसी", "हल्दी", "अदरक", "लहसुन", "नीम", "च्यवनप्राश", "आयुर्वेदिक",
]


def _check_dangerous_first_aid(claim):
    c_lower = claim.lower()
    # Toothpaste / butter / ghee on burns
    if any(b in c_lower for b in ["burn", "burns", "जले", "जलना", "घाव"]) and any(
        t in c_lower for t in ["toothpaste", "butter", "oil", "ghee", "टूथपेस्ट", "मक्खन", "घी"]
    ):
        return {
            "verdict": "MYTH",
            "claim": claim,
            "confidence": 95.0,
            "explanation": {
                "en": "Toothpaste, butter, oil, or turmeric should NEVER be applied to burns. They trap heat inside the skin tissue, increase the risk of severe bacterial infection, and complicate clinical care. Correct immediate first aid: cool the burn under clean, running tap water for 15-20 minutes and seek medical care for deep or blistered burns.",
                "hi": "जले हुए हिस्से पर टूथपेस्ट, मक्खन, तेल या हल्दी कभी नहीं लगाना चाहिए। ये त्वचा में गर्मी को रोक लेते हैं, संक्रमण का गंभीर खतरा बढ़ाते हैं और घाव को बिगाड़ते हैं। सही प्राथमिक उपचार: जले हिस्से को 15-20 मिनट तक नल के साफ बहते पानी से ठंडा करें और गंभीर जलने पर तुरंत डॉक्टर को दिखाएं।",
            },
            "sources": [{"name": "WHO Burns Care", "tier": 1}, {"name": "MoHFW Burns Guidelines", "tier": 1}],
            "tags": ["first_aid", "dangerous"],
            "fear_mongering": False,
        }
    # Sucking / cutting snakebite
    if any(s in c_lower for s in ["snake", "snakebite", "साँप", "सर्प"]) and any(
        a in c_lower for a in ["suck", "mouth", "cut", "blade", "tourniquet", "चूस", "चीरा"]
    ):
        return {
            "verdict": "MYTH",
            "claim": claim,
            "confidence": 98.0,
            "explanation": {
                "en": "Never cut, suck venom with your mouth, or tie tight tourniquets on a snakebite. Sucking venom introduces mouth bacteria, cutting damages nerves/arteries, and tourniquets can cause tissue gangrene. Correct first aid: keep the victim calm and still, immobilize the limb with a loose splint, and rush to a hospital immediately for Anti-Snake Venom (ASV).",
                "hi": "सांप के काटे स्थान को कभी चीरा न लगाएं, मुंह से जहर न चूसें और न ही कसकर पट्टी बांधें। ऐसा करने से नसें कटने और गैंग्रीन का खतरा होता है। सही तरीका: मरीज को शांत रखें, काटे गए अंग को स्थिर रखें और तुरंत एंटी-स्नेक वेनम (ASV) के लिए नजदीकी सरकारी अस्पताल ले जाएं।",
            },
            "sources": [{"name": "WHO Snakebite Envenoming Guidelines", "tier": 1}, {"name": "National Health Portal", "tier": 1}],
            "tags": ["first_aid", "emergency", "dangerous"],
            "fear_mongering": False,
        }
    # Chilli / mud on dog bites
    if any(d in c_lower for d in ["dog", "kutta", "कुत्ता", "rabies", "रेबीज"]) and any(
        c in c_lower for c in ["chilli", "chili", "mirch", "mud", "cow dung", "मिर्च", "गोबर", "मिट्टी"]
    ):
        return {
            "verdict": "MYTH",
            "claim": claim,
            "confidence": 98.0,
            "explanation": {
                "en": "Applying red chilli powder, mud, or cow dung on animal bites is dangerous and does NOT prevent rabies. Rabies is 100% fatal once symptoms start. Immediate correct action: wash the bite thoroughly with soap and running water for at least 15 minutes, and visit a health center immediately for Anti-Rabies Vaccine (ARV) and rabies immunoglobulin if indicated.",
                "hi": "कुत्ते या जानवर के काटने पर लाल मिर्च, गोबर या मिट्टी लगाना बेहद खतरनाक है। लक्षण शुरू होने पर रेबीज 100% जानलेवा है। सही तरीका: घाव को तुरंत साबुन और बहते पानी से कम से कम 15 मिनट तक अच्छी तरह धोएं और तुरंत अस्पताल जाकर एंटी-रेबीज वैक्सीन (ARV) लगवाएं।",
            },
            "sources": [{"name": "National Rabies Control Programme (NRCP)", "tier": 1}, {"name": "WHO Rabies Guidelines", "tier": 1}],
            "tags": ["rabies", "first_aid", "dangerous"],
            "fear_mongering": False,
        }
    return None


def clean_claim(text):
    text = _FORWARD_PREFIX.sub("", text.strip())
    text = _CLAIM_PREFIX.sub("", text.strip())
    return text.strip()


REMEDY_CANON = {
    "garlic": "garlic", "lahsun": "garlic", "lehsun": "garlic", "lasun": "garlic", "लहसुन": "garlic",
    "haldi": "turmeric", "turmeric": "turmeric", "हल्दी": "turmeric",
    "giloy": "giloy", "guduchi": "giloy", "गिलोय": "giloy",
    "tulsi": "tulsi", "तुलसी": "tulsi",
    "neem": "neem", "नीम": "neem",
    "karela": "karela", "karele": "karela", "bitter gourd": "karela", "करेला": "karela",
    "papaya": "papaya", "papita": "papaya", "papite": "papaya", "पपीता": "papaya", "पपीते": "papaya",
    "ginger": "ginger", "adrak": "ginger", "अदरक": "ginger",
    "honey": "honey", "shahad": "honey", "शहद": "honey",
    "lemon": "lemon", "nimbu": "lemon", "नींबू": "lemon",
    "kadha": "kadha", "काढ़ा": "kadha",
    "chyawanprash": "chyawanprash", "च्यवनप्राश": "chyawanprash",
    "jeera": "jeera", "cumin": "jeera", "जीरा": "jeera",
    "saunf": "saunf", "fennel": "saunf", "सौंफ": "saunf",
    "coconut": "coconut", "nariyal": "coconut", "नारियल": "coconut",
    "cow urine": "cow_urine", "gaumutra": "cow_urine", "गौमूत्र": "cow_urine",
    "toothpaste": "toothpaste", "ghee": "ghee", "jaggery": "jaggery", "gud": "jaggery", "गुड़": "jaggery",
    "chilli": "chilli", "mirch": "chilli", "mirchi": "chilli", "मिर्च": "chilli",
    "alcohol": "alcohol", "sharab": "alcohol", "शराब": "alcohol",
    "spoon": "spoon", "chamach": "spoon", "चम्मच": "spoon",
    "hot water": "hot_water", "warm water": "hot_water", "garam paani": "hot_water", "गर्म पानी": "hot_water",
    "hanuman phal": "graviola", "graviola": "graviola", "soursop": "graviola",
    "vitamin c": "vitamin_c", "aspirin": "aspirin",
}


def _remedy_keys(s):
    """Canonical names of the home remedies or ingredients a claim mentions (garlic, lahsun and लहसुन are one)."""
    s_lower = s.lower()
    keys = set()
    for alias, canonical in REMEDY_CANON.items():
        if alias.isascii():
            if re.search(r"\b" + re.escape(alias) + r"\b", s_lower):
                keys.add(canonical)
        elif alias in s_lower:
            keys.add(canonical)
    return keys


def _entry_remedy_keys(entry, row_text=""):
    claim = entry.get("claim", {})
    return _remedy_keys(claim.get("en", "")) | _remedy_keys(claim.get("hi", "")) | _remedy_keys(row_text)


_QUESTION_WORDS = re.compile(
    r"\b(what|how long|how many|how much|how do|how can|how to|why|when|where|which|who|whom|kaise|kab|kaun|kitna|kitne|kitni|kyun|kyu|kyon)\b|"
    r"(क्या\s+क्या|कैसे|कब|कौन|कितना|कितने|कितनी|क्यों)",
    re.IGNORECASE,
)
_INFO_WORDS = re.compile(
    r"\b(lakshan|ilaaj|ilaj|upay|bachav|tarika|symptoms?|treatment|prevention|signs? of|causes of|dose|doses|test|jaanch)\b|"
    r"(लक्षण|इलाज|उपाय|बचाव|तरीका|जाँच)",
    re.IGNORECASE,
)
_FIRST_PERSON_START = re.compile(r"^\s*(i |i'm |i am |my |mera |meri |mere |mujhe |main |मेरा |मेरी |मेरे |मुझे |मैं )", re.IGNORECASE)


def looks_like_claim(text):
    """A statement, or a yes/no question, that could be a health claim (garlic cures dengue, kya lehsun se dengue
    theek hota hai). Open questions (what, how many, kitne din) and first-person reports are not claims. Whether it
    really is a known claim is decided by the curated myth match, which must be found before anything is answered."""
    t = (text or "").strip()
    words = t.split()
    if len(words) < 4 or len(words) > 45:
        return False
    if _FIRST_PERSON_START.match(t) or _QUESTION_WORDS.search(t) or _INFO_WORDS.search(t):
        return False
    return True


def _load_hinglish():
    path = KB_DIR / "myths_hinglish.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}


def _ensure_index():
    global _index
    if _index is not None:
        return _index
    claims = []
    entries = []
    for m in kb.myths():
        for lang in ["en", "hi"]:
            if lang in m.get("claim", {}):
                claims.append(m["claim"][lang])
                entries.append(m)
    by_id = {m["id"]: m for m in kb.myths()}
    for myth_id, variants in _load_hinglish().items():
        entry = by_id.get(myth_id)
        if not entry:
            continue
        for variant in variants:
            claims.append(variant)
            entries.append(entry)
    matrix = _vectors(claims, "myth_claims")
    _index = {"claims": claims, "entries": entries, "matrix": matrix}
    return _index


def verify_claim(text, lang="en", strict_remedy=False, allow_live=False, plain=False):
    """Match a claim to the curated myths (and the dangerous first-aid rules). `allow_live` is kept for callers;
    the live web lookup of v1 was removed in S6 (fact-checks beyond the myths are in app/answer/factcheck.py)."""
    index = _ensure_index()
    claim = clean_claim(text)
    if len(claim.split()) < 3:
        return {"verdict": "INVALID", "claim": text, "message_key": "factcheck_no_claim"}

    # 1. Fast safety check for critical harmful first-aid myths
    dangerous_fa = _check_dangerous_first_aid(claim)
    if dangerous_fa:
        return dangerous_fa

    qv = _vectors([claim])[0]
    sims = index["matrix"] @ qv  # both sides are L2-normalised, so this is cosine similarity

    # 2. Disease- and remedy-aware re-ranking
    ck = _disease_keys(claim)
    rk = _remedy_keys(claim)
    scores = np.copy(sims)
    for i, entry in enumerate(index["entries"]):
        row = index["claims"][i]
        if ck:
            ek = _disease_keys(entry["claim"].get("en", "")) | _disease_keys(entry["claim"].get("hi", "")) | _disease_keys(row)
            if ek:
                if ck & ek:
                    scores[i] += 0.15  # same disease boost
                else:
                    scores[i] -= 0.30  # conflicting disease penalty
        if rk:
            er = _entry_remedy_keys(entry, row)
            if er:
                if rk & er:
                    scores[i] += 0.12  # same remedy: garlic matches the garlic myth
                else:
                    scores[i] -= 0.12  # a different remedy: garlic must not match the giloy myth

    # Re-rank top candidates by combining semantic similarity and lexical overlap
    top_candidates = np.argsort(scores)[::-1][:8]
    best_idx = int(top_candidates[0])
    best_combined = -1.0
    for idx in top_candidates:
        entry_cand = index["entries"][idx]
        row_cand = index["claims"][idx]
        ol = max(
            _content_overlap(claim, entry_cand["claim"].get("en", "")),
            _content_overlap(claim, entry_cand["claim"].get("hi", "")),
            _content_overlap(claim, row_cand),
        )
        combined = float(scores[idx]) * (1.0 + 0.6 * ol)
        if combined > best_combined:
            best_combined = combined
            best_idx = int(idx)

    best_sim = float(sims[best_idx])
    entry = index["entries"][best_idx]
    row_text = index["claims"][best_idx]

    overlap = max(
        _content_overlap(claim, entry["claim"].get("en", "")),
        _content_overlap(claim, entry["claim"].get("hi", "")),
        _content_overlap(claim, row_text),
    )
    ek = _disease_keys(entry["claim"].get("en", "")) | _disease_keys(entry["claim"].get("hi", "")) | _disease_keys(row_text)
    disease_conflict = bool(ck) and bool(ek) and not (ck & ek)
    er_best = _entry_remedy_keys(entry, row_text)
    th = MATCH_THRESHOLDS[_embed_name]
    remedy_conflict = bool(er_best) and not (rk & er_best) and (strict_remedy or best_sim < th["remedy_sure"])

    use_curated = (any(best_sim >= s and overlap >= o for s, o in th["pairs"]) and not disease_conflict
                   and not remedy_conflict)
    if plain:
        # A plain message was not marked as a claim by the user, so only a close match may answer it.
        use_curated = use_curated and best_sim >= th["plain"][0] and overlap >= th["plain"][1]

    if not use_curated:
        return {"verdict": "UNVERIFIABLE", "claim": claim}

    return {
        "verdict": entry["verdict"],
        "claim": claim,
        "similarity": best_sim,
        "explanation": entry["explanation"],
        "sources": entry["sources"],
        "tags": entry.get("tags", []),
        "fear_mongering": entry.get("fear_mongering", False),
        "matched_claim": entry["claim"],
    }
