import re

from app import config
from app.config import INTENT_CONFIDENCE_THRESHOLD
from app.core import embeddings, entities, generator, guard, intent, kb, language, relevance, retriever, safety, safety_llm, websearch
from app.core import session as session_store
from app.factcheck import verifier

FACT_TRIGGERS = [
    "fact check", "fact-check", "verify", "is this true", "ye sach hai kya", "kya ye sach",
    "सच है क्या", "जाँच करो", "फैक्ट चेक", "check this", "sahi hai ya galat", "सही है या गलत",
    "myth or truth", "sach ya jhooth", "real or fake",
]

AGE_PATTERN = re.compile(r"(\d{1,2})\s*(week|weeks|hafte|hafta|month|months|mahine|mahina|year|years|saal|sal|month|सप्ताह|हफ्ते|हफ़्ते|महीने|महीना|साल|वर्ष)")
PREGNANCY_WORDS = ["pregnant", "pregnancy", "garbhavati", "गर्भवती", "गर्भावस्था", "garbh"]

_disease_symptom_map = None


def _build_disease_symptom_map():
    global _disease_symptom_map
    if _disease_symptom_map is not None:
        return _disease_symptom_map
    mapping = {}
    for d in kb.diseases():
        ids = set()
        for lang in ["en", "hi"]:
            for symptom_text in d.get("symptoms", {}).get(lang, []):
                for sid, aliases in entities.SYMPTOM_LEXICON.items():
                    if any(a in symptom_text.lower() for a in aliases):
                        ids.add(sid)
        mapping[d["id"]] = ids
    _disease_symptom_map = mapping
    return mapping


# A number plus a time unit is only treated as a vaccination age when the message is about vaccines, a baby or a
# child, and the number is not a duration ("cough for 2 years").
AGE_CONTEXT = re.compile(
    r"\b(vaccin\w*|immuni[sz]\w*|tika\w*|teeka\w*|tike|baby|babies|child\w*|kid|kids|infant|newborn|toddler|"
    r"bachch\w*|bachh\w*|bacch\w*|bacha|bache|bachon|shishu|son|daughter|beta|beti|bete|old)\b"
)
AGE_CONTEXT_DEVANAGARI = ("टीका", "टीके", "टीकाकरण", "बच्च", "शिशु")
DURATION_CUE = re.compile(r"(?:\bfor|\bsince|\blast|\bpast|\bpichle|\bpichhle|से)\s*$")


def _age_in_weeks(text):
    """The child's age in weeks when the message states one for a vaccination question, else None."""
    lower = text.lower()
    if not (AGE_CONTEXT.search(lower) or any(w in lower for w in AGE_CONTEXT_DEVANAGARI)):
        return None
    for candidate in AGE_PATTERN.finditer(lower):
        if DURATION_CUE.search(lower[max(0, candidate.start() - 12):candidate.start()]):
            continue
        n = int(candidate.group(1))
        unit = candidate.group(2)
        if unit in ("week", "weeks", "hafte", "hafta", "सप्ताह", "हफ्ते", "हफ़्ते"):
            return float(n)
        if unit in ("month", "months", "mahine", "mahina", "महीने", "महीना"):
            return n * 4.345
        if unit in ("year", "years", "saal", "sal", "साल", "वर्ष"):
            return n * 52.18
    return None


# UIP windows in weeks. Between two windows no routine vaccine is due (a gap).
_AGE_WINDOWS = [
    (0, 4.5, "birth"),
    (4.5, 9, "6_weeks"),
    (9, 13, "10_weeks"),
    (13, 17, "14_weeks"),
    (17, 39, None),
    (39, 65, "9_12_months"),
    (65, 111, "16_24_months"),
    (111, 260, None),
    (260, 365, "5_6_years"),
    (365, 520, None),
    (520, 690, "10_years"),
    (690, 830, None),
    (830, 945, "16_years"),
]


def _age_window(text):
    """(milestone or None, is_gap) for the age in the message; (None, False) when there is no usable age."""
    weeks = _age_in_weeks(text)
    if weeks is None:
        return None, False
    for lo, hi, name in _AGE_WINDOWS:
        if lo <= weeks < hi:
            return name, name is None
    return None, False


def _age_to_milestones(text):
    lower = text.lower()
    if any(w in lower for w in PREGNANCY_WORDS):
        # Pregnancy is a vaccine topic only when the message is about a vaccine or tetanus.
        if entities.has_vaccine_word(lower) or "tetanus" in lower or "टिटनेस" in lower or re.search(r"(tt|td)", lower):
            return "pregnancy"
        return None
    milestone, _ = _age_window(text)
    return milestone


def _age_gap(text):
    return _age_window(text)[1]


AGE_GAP_NOTE = {
    "en": "The routine UIP schedule has no vaccine due at this age (between 14 weeks and 9 months, between about 2 and 5 years, and at some other ages). If a dose was missed, ask your ANM, ASHA or nearest health centre what can still be given.",
    "hi": "इस उम्र पर नियमित टीकाकरण कार्यक्रम (UIP) में कोई टीका तय नहीं है (14 सप्ताह से 9 महीने के बीच, लगभग 2 से 5 साल के बीच, और कुछ दूसरी उम्र पर)। अगर कोई खुराक छूट गई है तो अपनी ANM, आशा या नज़दीकी स्वास्थ्य केंद्र से पूछें कि कौन सा टीका अब भी लग सकता है।",
}


AGE_VACCINE_MAP = {
    "birth": ["bcg", "hepb", "opv"],
    "6_weeks": ["pentavalent", "opv", "rotavirus", "ipv", "pcv", "hepb"],
    "10_weeks": ["pentavalent", "opv", "rotavirus"],
    "14_weeks": ["pentavalent", "opv", "rotavirus", "ipv", "pcv", "hepb"],
    "9_12_months": ["mr", "je", "pcv"],
    "16_24_months": ["mr", "je", "dpt_booster", "opv"],
    "5_6_years": ["dpt_booster"],
    "10_years": ["td"],
    "16_years": ["td"],
    "pregnancy": ["td"],
}

AGE_LABELS = {
    "birth": {"en": "At birth", "hi": "जन्म पर"},
    "6_weeks": {"en": "At 6 weeks", "hi": "6 सप्ताह पर"},
    "10_weeks": {"en": "At 10 weeks", "hi": "10 सप्ताह पर"},
    "14_weeks": {"en": "At 14 weeks", "hi": "14 सप्ताह पर"},
    "9_12_months": {"en": "At 9-12 months", "hi": "9-12 महीने पर"},
    "16_24_months": {"en": "At 16-24 months", "hi": "16-24 महीने पर"},
    "5_6_years": {"en": "At 5-6 years", "hi": "5-6 वर्ष पर"},
    "10_years": {"en": "At 10 years", "hi": "10 वर्ष पर"},
    "16_years": {"en": "At 16 years", "hi": "16 वर्ष पर"},
    "pregnancy": {"en": "During pregnancy", "hi": "गर्भावस्था में"},
}


def _fmt_lang(obj, lang, key):
    if isinstance(obj, dict):
        return obj.get(lang) or obj.get("hi") or obj.get("en", "")
    return obj


def _llm_wrap(context, question, lang, fallback_text, source_names=None):
    reply = generator.grounded_answer(context, question, lang)
    if reply and generator.leaks_prompt(reply):
        reply = None
    if reply:
        parts = [reply]
        if source_names:
            parts.append(f"Sources: {source_names}")
        parts.append(safety.disclaimer(lang))
        return "\n".join(parts), "llm"
    return fallback_text, "template"


HARD_INTERRUPT_INTENTS = {
    "fact_check",
    "emergency",
    "disease_info",
    "vaccination",
    "outbreak",
    "greeting",
    "smalltalk",
    "help",
    "language_switch",
    "thanks",
}

CAPABILITIES_TEXT = {
    "en": (
        "Capabilities: 1) Disease information (symptoms, prevention, first aid) "
        "2) Symptom guidance 3) Prevention and hygiene tips 4) Vaccination schedules (UIP) "
        "5) Fact-checking forwarded health messages with verdicts "
        "VERIFIED / MYTH / PARTLY TRUE / UNVERIFIABLE. "
        "Grounded in WHO and MoHFW content. Not a doctor, never diagnoses."
    ),
    "hi": (
        "क्षमताएँ: 1) बीमारियों की जानकारी (लक्षण, बचाव, प्राथमिक उपचार) "
        "2) लक्षणों पर मार्गदर्शन 3) बचाव और स्वच्छता सुझाव 4) टीकाकरण कार्यक्रम (UIP) "
        "5) फॉरवर्ड किए स्वास्थ्य संदेशों की सच्चाई जाँच - "
        "सत्य / भ्रांति / आंशिक सत्य / पुष्टि असंभव। "
        "WHO और MoHFW की जानकारी पर आधारित। डॉक्टर नहीं है, निदान कभी नहीं करता।"
    ),
}


def _chatty_answer(kind, lang, question):
    fallback_key = {"greeting": "greeting", "help": "help", "smalltalk": "smalltalk_fallback", "thanks": "thanks"}.get(kind)
    fallback = kb.msg(lang, fallback_key) if fallback_key else ""
    contexts = {
        "greeting": (
            f"You are AarogyaSathi, an AI public-health awareness assistant for rural India. {CAPABILITIES_TEXT.get(lang, CAPABILITIES_TEXT['en'])} "
            "Greet the user warmly and briefly say what you can help with."
        ),
        "help": (
            f"You are AarogyaSathi, an AI public-health awareness assistant. {CAPABILITIES_TEXT.get(lang, CAPABILITIES_TEXT['en'])} "
            "List these capabilities briefly with one example each."
        ),
        "smalltalk": (
            f"You are AarogyaSathi, an AI public-health awareness assistant for rural India, built as a student project "
            f"based on Smart India Hackathon problem SIH-25049. {CAPABILITIES_TEXT.get(lang, CAPABILITIES_TEXT['en'])} "
            "Answer the personal question briefly and honestly. You are an AI assistant, not a human, not a doctor."
        ),
        "thanks": (
            "The user thanked you. Reply warmly in one short line."
        ),
    }
    reply = generator.grounded_answer(contexts[kind], question, lang)
    if reply:
        return reply, "llm"
    return fallback or kb.msg(lang, "unknown"), "template"


def _generic_pain_advice(symptoms, lang):
    if lang == "hi":
        if "neck_pain" in symptoms:
            text = (
                "गर्दन का दर्द अक्सर मांसपेशियों में खिंचाव, खराब मुद्रा या गलत सोने की स्थिति से होता है। "
                "हल्की हरकत और गर्म सेंक से राहत मिल सकती है। इन स्थितियों में जल्दी डॉक्टर को दिखाएँ: "
                "बुखार के साथ गर्दन अकड़न, ठुड्डी छाती से न लग पाना, हाथों में सुन्नता/कमज़ोरी, चोट के बाद तेज़ दर्द, "
                "या दर्द एक सप्ताह से अधिक रहना।"
            )
        elif "back_pain" in symptoms:
            text = (
                "कमर दर्द अक्सर मांसपेशियों में खिंचाव या गलत मुद्रा से होता है। हल्की सक्रियता और गर्म सेंक से राहत मिलती है। "
                "डॉक्टर को जल्दी दिखाएँ यदि: दर्द पैर में फैले, सुन्नता/कमज़ोरी हो, पेशाब या मल पर नियंत्रण न रहे, "
                "या दर्द एक सप्ताह से अधिक रहे।"
            )
        else:
            text = (
                "यह दर्द अक्सर मांसपेशियों या हल्की चोट से हो सकता है। आराम, सेंक और हल्की हरकत से राहत मिल सकती है। "
                "अगर दर्द गंभीर हो, बुखार/सूजन/लालिमा हो, या कुछ दिनों में न सुधरे तो डॉक्टर को दिखाएँ।"
            )
    else:
        if "neck_pain" in symptoms:
            text = (
                "Neck pain for a few days is usually from muscle strain, poor posture or a bad sleeping position. "
                "Gentle movement and a warm compress can help. See a doctor soon if: the neck is stiff together with fever, "
                "you cannot touch your chin to your chest, pain spreads to the arms with numbness or weakness, "
                "the pain follows an injury, or it lasts more than a week."
            )
        elif "back_pain" in symptoms:
            text = (
                "Back pain is commonly from muscle strain or poor posture. Gentle activity and heat usually help. "
                "See a doctor soon if: pain spreads down a leg, you have numbness or weakness, you lose control of "
                "urine or stool, or the pain lasts more than a week."
            )
        else:
            text = (
                "This kind of pain is often muscular or from a minor strain. Rest, gentle movement and heat/cold "
                "compresses usually help. See a doctor if the pain is severe, comes with fever, swelling or redness, "
                "or does not improve in a few days."
            )
    return f"{text}\n{safety.disclaimer(lang)}"


def _symptom_final_answer(symptoms, extra_text, lang, question):
    mapping = _build_disease_symptom_map()
    scored = []
    for disease_id, disease_syms in mapping.items():
        overlap = set(symptoms) & disease_syms
        if overlap:
            scored.append((len(overlap), disease_id))
    scored.sort(reverse=True)
    context_lines = [f"The user reports these symptoms: {', '.join(symptoms)}"]
    if extra_text:
        context_lines.append(f"User's additional details: {extra_text}")
    context_lines.append(
        "Based on the verified knowledge base, these conditions can cause similar symptoms "
        "(awareness information, NOT a diagnosis):"
    )
    fallback_lines = [kb.msg(lang, "symptom_advice_prefix")]
    if not scored:
        return _generic_pain_advice(symptoms, lang), "template"
    for _, disease_id in scored[:3]:
        d = next(x for x in kb.diseases() if x["id"] == disease_id)
        name = (d["names"].get(lang) or d["names"]["en"])[0]
        seek = d.get("when_to_seek", {}).get(lang) or d.get("when_to_seek", {}).get("en", "")
        context_lines.append(f"{name}: {seek[:200]}")
        fallback_lines.append(f"- {name}: {seek[:160]}")
    context_lines.append(
        "Advice to include: if symptoms are severe, persistent or worsening, consult a qualified doctor."
    )
    fallback_lines.append(kb.msg(lang, "symptom_see_doctor"))
    fallback_lines.append(safety.disclaimer(lang))
    fallback = "\n".join(fallback_lines)
    analysis = generator.analyze_symptoms("\n".join(context_lines), lang, question)
    if analysis:
        return f"{analysis}\n{safety.disclaimer(lang)}", "llm"
    return fallback, "template"


def _disease_context(d, lang, focus=None):
    name = d["names"].get(lang) or d["names"].get("hi") or d["names"]["en"]
    name = name[0] if name else d["id"]
    lines = [f"Disease: {name}"]
    if focus != "prevention":
        lines.append(f"Summary: {_fmt_lang(d['summary'], lang, 'summary')}")
        sym = d.get("symptoms", {}).get(lang) or d.get("symptoms", {}).get("hi") or d.get("symptoms", {}).get("en", [])
        lines.append("Symptoms: " + "; ".join(sym))
    if focus != "info":
        prev = d.get("prevention", {}).get(lang) or d.get("prevention", {}).get("hi") or d.get("prevention", {}).get("en", [])
        lines.append("Prevention: " + "; ".join(prev))
    if focus is None:
        if d.get("first_aid"):
            lines.append(f"First aid / care: {_fmt_lang(d['first_aid'], lang, 'first_aid')}")
    if d.get("when_to_seek"):
        lines.append(f"When to see a doctor: {_fmt_lang(d['when_to_seek'], lang, 'when_to_seek')}")
    return "\n".join(lines)


def _disease_card(disease_id, lang):
    for d in kb.diseases():
        if d["id"] == disease_id:
            name = d["names"].get(lang) or d["names"].get("hi") or d["names"]["en"]
            name = name[0] if name else d["id"]
            lines = [f"[{name.upper()}]", _disease_context(d, lang)]
            sources = ", ".join(s["name"] for s in d.get("sources", []))
            lines.append(f"Sources: {sources}")
            lines.append(safety.disclaimer(lang))
            return "\n".join(lines)
    return None


def _symptom_probe(symptoms, lang, question):
    if lang != "en":
        return kb.msg(lang, "probe_question"), "template"
    context = f"The user reported these symptoms: {', '.join(symptoms)}."
    task = (
        "Ask ONE short, empathetic follow-up question: since how many days they have these "
        "symptoms, and whether they also have fever, vomiting or loose motions."
    )
    reply = generator.ask_followup(context, task, lang)
    if reply:
        return reply, "llm"
    return kb.msg(lang, "probe_question"), "template"


def _vaccine_response(text, lang):
    vaccine_id = entities.find_vaccine(text)
    if vaccine_id:
        for v in kb.vaccines():
            if v["id"] == vaccine_id:
                name = (v["names"].get(lang) or v["names"].get("en"))[0]
                context = (
                    f"Vaccine: {name}. Protects against: {_fmt_lang(v['protects'], lang, 'protects')}. "
                    f"Schedule: {_fmt_lang(v['schedule'], lang, 'schedule')}."
                )
                if v.get("note"):
                    context += f" Note: {_fmt_lang(v['note'], lang, 'note')}"
                lines = [f"[{name.upper()}]"]
                lines.append(f"Protects against: {_fmt_lang(v['protects'], lang, 'protects')}")
                lines.append(f"Schedule: {_fmt_lang(v['schedule'], lang, 'schedule')}")
                if v.get("note"):
                    lines.append(f"Note: {_fmt_lang(v['note'], lang, 'note')}")
                lines.append(f"Source: {v['sources'][0]['name']}")
                lines.append(safety.disclaimer(lang))
                return context, "\n".join(lines), v["sources"][0]["name"]
    milestone = _age_to_milestones(text)
    if milestone and milestone in AGE_VACCINE_MAP:
        ids = AGE_VACCINE_MAP[milestone]
        vmap = {v["id"]: v for v in kb.vaccines()}
        label = AGE_LABELS[milestone].get(lang, AGE_LABELS[milestone]["en"])
        lines = [f"Vaccines {label}:"]
        context_lines = [f"Vaccination schedule {label}:"]
        for vid in ids:
            v = vmap.get(vid)
            if not v:
                continue
            name = (v["names"].get(lang) or v["names"].get("en"))[0]
            protects = _fmt_lang(v["protects"], lang, "protects")
            lines.append(f"- {name}: {protects}")
            context_lines.append(f"{name}: {protects}")
        lines.append(safety.disclaimer(lang))
        return "\n".join(context_lines), "\n".join(lines), "UIP, MoHFW"
    summary = kb.vaccine_summary()
    lines = [f"National Immunization Schedule (UIP):\n{summary.get(lang, summary['en'])}"]
    if _age_gap(text):
        # An age was given but no routine vaccine is due at it. Say so, then show the schedule.
        gap = AGE_GAP_NOTE.get(lang, AGE_GAP_NOTE["en"])
        lines.insert(0, gap)
        lines.append(safety.disclaimer(lang))
        return gap + " " + summary.get(lang, summary["en"]), "\n".join(lines), "UIP, MoHFW"
    lines.append("Ask me about any specific vaccine, e.g. 'MR vaccine' or 'vaccines at 6 weeks'.")
    lines.append(safety.disclaimer(lang))
    return summary.get(lang, summary["en"]), "\n".join(lines), "UIP, MoHFW"


def _faq_answer(faq_id, lang):
    for f in kb.faqs():
        if f["id"] == faq_id:
            answer = f["a"].get(lang) or f["a"].get("hi") or f["a"].get("en", "")
            question = f["q"].get(lang) or f["q"].get("hi") or f["q"].get("en", "")
            sources = ", ".join(s["name"] for s in f.get("sources", []))
            context = f"Topic: {question}. {answer}"
            fallback = f"{answer}\nSources: {sources}\n{safety.disclaimer(lang)}"
            return context, fallback, sources
    return None, None, None


def _disease_answer(disease_id, lang, question, focus=None):
    for d in kb.diseases():
        if d["id"] == disease_id:
            card = _disease_card(disease_id, lang)
            context = _disease_context(d, lang, focus)
            sources = ", ".join(s["name"] for s in d.get("sources", []))
            text, gen = _llm_wrap(context, question, lang, card, sources)
            return text, gen
    return None, None


def _outbreak_response(lang):
    # The bot has no live outbreak feed, so it says so and points to the official sources
    # instead of showing advisories it cannot stand behind.
    return kb.msg(lang, "outbreak_no_data") + "\n" + safety.disclaimer(lang)


def _route_by_understanding(u, text, lang, session):
    intent_type = (u.get("intent") or "").lower()
    symptoms = u.get("symptoms") or []
    disease = u.get("disease")

    if intent_type == "greeting":
        return {"text": kb.msg(lang, "greeting"), "meta": {"intent": "greeting", "lang": lang}}
    if intent_type == "help":
        return {"text": kb.msg(lang, "help"), "meta": {"intent": "help", "lang": lang}}
    if intent_type == "smalltalk":
        answer, gen = _chatty_answer("smalltalk", lang, text)
        return {"text": answer, "meta": {"intent": "smalltalk", "lang": lang, "generator": gen}}
    if intent_type == "thanks":
        answer, gen = _chatty_answer("thanks", lang, text)
        return {"text": answer, "meta": {"intent": "thanks", "lang": lang, "generator": gen}}
    if intent_type == "fact_check":
        return None
    if intent_type == "vaccination":
        context, fallback, sources = _vaccine_response(text, lang)
        answer, gen = _llm_wrap(context, text, lang, fallback, sources)
        return {"text": answer, "meta": {"intent": "vaccination", "lang": lang, "generator": gen}}
    if intent_type == "outbreak":
        return {"text": _outbreak_response(lang), "meta": {"intent": "outbreak", "lang": lang}}
    if intent_type in ("disease_info", "prevention"):
        disease_id = disease or entities.find_disease(text)
        if disease_id:
            focus = "info" if intent_type == "disease_info" else "prevention"
            answer, gen = _disease_answer(disease_id, lang, text, focus=focus)
            if answer:
                return {
                    "text": answer,
                    "meta": {"intent": intent_type, "disease": disease_id, "lang": lang, "generator": gen},
                }
        return None
    if intent_type == "symptom":
        if symptoms:
            session.set("symptom_flow", {"turn": 1, "symptoms": symptoms, "analysis": u})
            probe, gen = _symptom_probe(symptoms, lang, text)
            return {
                "text": probe,
                "meta": {
                    "intent": "symptom_check",
                    "flow": "symptom_probe",
                    "symptoms": symptoms,
                    "lang": lang,
                    "generator": gen,
                },
            }
        return None
    if intent_type == "unclear":
        q = generator.ask_followup(
            "The user's message is unclear.",
            "Ask ONE short, friendly question to understand what health problem the user needs help with.",
            lang,
        )
        return {
            "text": q or kb.msg(lang, "unknown"),
            "meta": {"intent": "unclear", "lang": lang, "generator": "llm" if q else "template"},
        }
    return None


def _try_fast_path(text, lang, session):
    """
    Sub-5ms fast path using local TF-IDF intent prediction and regex entity matching.
    Bypasses LLM Call #1 (understand_message) when confident, cutting latency from ~8s to ~3s.
    If confidence is low and no entity matches, returns None to fall back to legacy LLM understanding.
    """
    if not getattr(config, "ENABLE_FAST_PATH", True):
        return None

    intent_name, confidence = intent.predict_intent(text, INTENT_CONFIDENCE_THRESHOLD)
    disease_id = entities.find_disease(text)
    symptoms = entities.find_symptoms(text) if not _is_info_question(text) else []
    vaccine_id = entities.find_vaccine(text)
    milestone = _age_to_milestones(text)

    # 1. High-priority safety / emergency
    if intent_name == "emergency":
        session.clear()
        lang = safety.emergency_language(text, lang)
        return {
            "text": safety.emergency_response(lang),
            "meta": {"intent": "emergency", "lang": lang, "route": "fast_path"},
        }

    # 2. Fact-check triggered or predicted
    if intent_name == "fact_check":
        session.clear()
        result = verifier.verify_claim(text, lang)
        return {
            "text": verifier.format_verdict(result, lang),
            "meta": {"intent": "fact_check", "verdict": result["verdict"], "lang": lang, "factcheck": result, "route": "fast_path"},
        }

    # 3. Conversational intents
    if intent_name == "greeting":
        return {"text": kb.msg(lang, "greeting"), "meta": {"intent": "greeting", "lang": lang, "route": "fast_path"}}

    if intent_name == "help":
        answer, gen = _chatty_answer("help", lang, text)
        return {"text": answer, "meta": {"intent": "help", "lang": lang, "generator": gen, "route": "fast_path"}}

    if intent_name == "smalltalk":
        answer, gen = _chatty_answer("smalltalk", lang, text)
        return {"text": answer, "meta": {"intent": "smalltalk", "lang": lang, "generator": gen, "route": "fast_path"}}

    if intent_name == "thanks":
        answer, gen = _chatty_answer("thanks", lang, text)
        return {"text": answer, "meta": {"intent": "thanks", "lang": lang, "generator": gen, "route": "fast_path"}}

    if intent_name == "language_switch":
        return {"text": kb.msg(lang, "language_switch"), "meta": {"intent": "language_switch", "lang": lang, "route": "fast_path"}}

    # 3b. Outbreak / alert questions. This comes before the disease card, otherwise
    # "any dengue alert near me?" would be answered as plain dengue information.
    if intent_name == "outbreak":
        return {"text": _outbreak_response(lang), "meta": {"intent": "outbreak", "lang": lang, "route": "fast_path"}}

    # 3c. A question that is clearly about a vaccine comes before the disease card: "hepatitis b ka tika" and
    # "corona ka tika kitne dose" are vaccine questions, not hepatitis or COVID information.
    if entities.has_vaccine_word(text) and (vaccine_id or milestone or _age_gap(text)):
        context, fallback, sources = _vaccine_response(text, lang)
        answer, gen = _llm_wrap(context, text, lang, fallback, sources)
        return {"text": answer, "meta": {"intent": "vaccination", "lang": lang, "generator": gen, "route": "fast_path"}}

    # 4. Disease info & prevention
    if disease_id or intent_name in ("disease_info", "prevention"):
        d_id = disease_id or entities.find_disease(text)
        if d_id:
            focus = "info" if intent_name == "disease_info" else ("prevention" if intent_name == "prevention" else None)
            answer, gen = _disease_answer(d_id, lang, text, focus=focus)
            if answer:
                return {
                    "text": answer,
                    "meta": {"intent": intent_name or "disease_info", "disease": d_id, "lang": lang, "generator": gen, "route": "fast_path"},
                }

    # 5. Symptom check
    if symptoms or (intent_name == "symptom_check" and not _is_info_question(text)):
        syms = symptoms or (entities.find_symptoms(text) if not _is_info_question(text) else [])
        if syms:
            session.set("symptom_flow", {"turn": 1, "symptoms": syms})
            probe, gen = _symptom_probe(syms, lang, text)
            return {
                "text": probe,
                "meta": {
                    "intent": "symptom_check",
                    "flow": "symptom_probe",
                    "symptoms": syms,
                    "lang": lang,
                    "generator": gen,
                    "route": "fast_path",
                },
            }

    # 6. Vaccination
    if (vaccine_id and not disease_id) or (milestone and entities.has_vaccine_word(text)) or intent_name == "vaccination":
        context, fallback, sources = _vaccine_response(text, lang)
        answer, gen = _llm_wrap(context, text, lang, fallback, sources)
        return {"text": answer, "meta": {"intent": "vaccination", "lang": lang, "generator": gen, "route": "fast_path"}}

    return None


def _fallback_answer(text, lang, session):
    summary = session.get("summary")
    history = session.get("history") or []
    recent = history[-4:]
    extra_ctx = ""
    if summary:
        extra_ctx += f"Conversation summary: {summary}\n"
    if recent:
        lines = "\n".join(f"{h['role']}: {h['text']}" for h in recent)
        extra_ctx += f"Recent messages:\n{lines}\n"
    if extra_ctx:
        extra_ctx += "\n"
    reply = generator.general_answer(text, lang, extra_ctx=extra_ctx)
    if reply:
        warn = kb.msg(lang, "warn_llm") or kb.msg("en", "warn_llm")
        return f"{reply}\n\n{warn}", "llm_general"
    if not websearch.is_health_query(text):
        return kb.msg(lang, "dont_know") or kb.msg("en", "dont_know"), "none"
    result = websearch.search_health(text)
    if result:
        warn = kb.msg(lang, "warn_net") or kb.msg("en", "warn_net")
        return f"{result['answer']}\n\nSource: {result['url']} ({result['source']})\n{warn}", "internet"
    return kb.msg(lang, "unknown"), "none"


def _entry_keywords(top):
    if top["type"] == "disease":
        for d in kb.diseases():
            if d["id"] == top["id"]:
                names = " ".join(n for names in d["names"].values() for n in names)
                return names + " " + d.get("summary", {}).get("en", "")[:200]
    if top["type"] == "faq":
        for f in kb.faqs():
            if f["id"] == top["id"]:
                parts = []
                for lang in ("en", "hi", "hinglish"):
                    if lang in f.get("q", {}):
                        parts.append(f["q"][lang])
                parts.extend(f.get("topics", []))
                return " ".join(parts)
    return ""


def _retrieval_relevant(question, top):
    keywords = _entry_keywords(top)
    if not keywords:
        return True
    return verifier._content_overlap(question, keywords) >= 0.2


QUESTION_STARTS = ("what", "how", "why", "where", "when", "which", "is", "does", "can", "should", "kya", "kaise", "क्या", "कैसे")


def _is_info_question(text):
    t = text.lower().strip()
    if not t.startswith(QUESTION_STARTS):
        return False
    return entities.find_disease(text) is not None or any(
        v in t for v in ["symptom", "symptoms", "treatment", "cause", "causes", "prevent", "vaccine", "test"]
    )


def _model_safety_result(text, lang, label):
    """The same emergency or helpline reply the rules give, raised by the model check instead."""
    lang = safety.emergency_language(text, lang)
    reply = safety.self_harm_response(lang) if label == "SELF_HARM" else safety.emergency_response(lang, [])
    return {
        "text": reply,
        "meta": {"intent": "emergency", "flow": "llm_safety", "red_flags": [], "lang": lang, "model_label": label},
    }


def process_message(text, pincode=None, session=None):
    text = (text or "").strip()
    if not text:
        return {"text": kb.msg("en", "help"), "meta": {}}
    if session is None:
        session = session_store.get_session(None)
    lang = language.detect_language(text)
    if lang == "en" and language.transliterate_hint(text):
        lang = "hi"

    welcomed = session.get("welcomed_langs") or []
    # The second safety check runs in the background while the normal reply is prepared.
    safety_check = safety_llm.start(text)
    result = _process_message_core(text, session)
    session.set("welcomed_langs", welcomed)

    intent = result["meta"].get("intent")
    if intent == "emergency":
        return result  # the word rules already fired; the model is never consulted and never overrides them
    label = safety_llm.result(safety_check)
    if label in ("EMERGENCY", "SELF_HARM"):
        session.clear()
        session.set("welcomed_langs", welcomed)
        return _model_safety_result(text, lang, label)
    if lang not in welcomed:
        if intent not in ("greeting", "language_switch"):
            welcome = kb.msg(lang, "greeting")
            if welcome:
                result["text"] = welcome + "\n\n" + result["text"]
        welcomed.append(lang)
        session.set("welcomed_langs", welcomed[-6:])
    return result


def _process_message_core(text, session=None):
    text = (text or "").strip()
    if not text:
        return {"text": kb.msg("en", "help"), "meta": {}}
    if session is None:
        session = session_store.get_session(None)

    lang = language.detect_language(text)
    if lang == "en" and language.transliterate_hint(text):
        lang = "hi"

    lower = text.lower()

    # Safety first: an emergency or self-harm message is answered before anything else, including fact-check
    # triggers. If the message also asks for a fact-check, the reply tells the user how to resend the claim.
    red_flags = safety.check_red_flags(text)
    if red_flags:
        session.clear()
        lang = safety.emergency_language(text, lang)
        if safety.is_self_harm(red_flags):
            reply = safety.self_harm_response(lang)
        else:
            reply = safety.emergency_response(lang, red_flags)
            if any(t in lower for t in FACT_TRIGGERS):
                reply += "\n\n" + safety.fact_check_note(lang)
        return {
            "text": reply,
            "meta": {"intent": "emergency", "red_flags": red_flags, "lang": lang},
        }

    # Instruction-override wordings get a fixed reply; no model sees them (see app/core/guard.py).
    if guard.is_injection(text):
        session.clear()
        return {
            "text": kb.msg(lang, "guard_refusal"),
            "meta": {"intent": "guard", "lang": lang, "route": "rule"},
        }

    if any(t in lower for t in FACT_TRIGGERS):
        session.clear()
        result = verifier.verify_claim(text, lang)
        return {
            "text": verifier.format_verdict(result, lang),
            "meta": {"intent": "fact_check", "verdict": result["verdict"], "lang": lang, "factcheck": result},
        }

    if text.strip().lower() in ("hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "नमस्कार", "हैलो", "हाय"):
        return {"text": kb.msg(lang, "greeting"), "meta": {"intent": "greeting", "lang": lang}}

    # Medicine dose questions get a fixed reply. The bot never advises on doses, and without this rule the
    # question was read as a symptom report and the model invented symptoms and diseases.
    if entities.is_dose_question(text):
        session.clear()
        return {
            "text": kb.msg(lang, "dose_question") + "\n" + safety.disclaimer(lang),
            "meta": {"intent": "dose_question", "lang": lang, "route": "rule"},
        }

    active_flow = session.get("symptom_flow")
    if active_flow is not None:
        flow_intent, _ = intent.predict_intent(text, INTENT_CONFIDENCE_THRESHOLD)
        if flow_intent in HARD_INTERRUPT_INTENTS:
            session.clear()
        else:
            new_symptoms = entities.find_symptoms(text)
            symptoms = list(dict.fromkeys(active_flow["symptoms"] + new_symptoms))
            extra = text
            session.clear()
            answer, gen = _symptom_final_answer(symptoms, extra, lang, text)
            return {
                "text": answer,
                "meta": {
                    "intent": "symptom_check",
                    "flow": "symptom_final",
                    "symptoms": symptoms,
                    "lang": lang,
                    "generator": gen,
                },
            }

    # A plain health claim without the "fact check:" prefix ("lehsun khane se dengue theek ho jata hai") is checked
    # against the curated myths. Only a curated verdict answers it; anything else continues through the normal routes.
    if verifier.looks_like_claim(text):
        claim_result = verifier.verify_claim(text, lang, strict_remedy=True, allow_live=False, plain=True)
        if claim_result.get("verdict") not in ("UNVERIFIABLE", "INVALID", None):
            session.clear()
            return {
                "text": verifier.format_verdict(claim_result, lang),
                "meta": {"intent": "fact_check", "verdict": claim_result["verdict"], "lang": lang, "factcheck": claim_result, "route": "claim_detect"},
            }

    # --- FAST PATH (Sub-5ms TF-IDF & Entity Routing) ---
    fast_result = _try_fast_path(text, lang, session)
    if fast_result is not None:
        return fast_result

    # --- LEGACY DOUBLE-LLM FALLBACK (LLM Call #1: understand_message) ---
    summary = session.get("summary")
    extra_ctx = f"Conversation summary: {summary}\n" if summary else ""
    u = generator.understand_message(text, lang, extra_ctx=extra_ctx)
    if u is not None:
        handled = _route_by_understanding(u, text, lang, session)
        if handled is not None:
            return handled

    intent_name, confidence = intent.predict_intent(text, INTENT_CONFIDENCE_THRESHOLD)

    if intent_name == "emergency":
        session.clear()
        lang = safety.emergency_language(text, lang)
        return {
            "text": safety.emergency_response(lang),
            "meta": {"intent": "emergency", "lang": lang},
        }

    if intent_name == "fact_check":
        session.clear()
        result = verifier.verify_claim(text, lang)
        return {
            "text": verifier.format_verdict(result, lang),
            "meta": {"intent": "fact_check", "verdict": result["verdict"], "lang": lang, "factcheck": result},
        }

    if intent_name == "greeting":
        return {"text": kb.msg(lang, "greeting"), "meta": {"intent": "greeting", "lang": lang}}

    if intent_name == "help":
        answer, gen = _chatty_answer("help", lang, text)
        return {"text": answer, "meta": {"intent": "help", "lang": lang, "generator": gen}}

    if intent_name == "smalltalk":
        answer, gen = _chatty_answer("smalltalk", lang, text)
        return {"text": answer, "meta": {"intent": "smalltalk", "lang": lang, "generator": gen}}

    if intent_name == "thanks":
        answer, gen = _chatty_answer("thanks", lang, text)
        return {"text": answer, "meta": {"intent": "thanks", "lang": lang, "generator": gen}}

    if intent_name == "language_switch":
        return {"text": kb.msg(lang, "language_switch"), "meta": {"intent": "language_switch", "lang": lang}}

    if intent_name == "disease_info":
        disease_id = entities.find_disease(text)
        if disease_id:
            answer, gen = _disease_answer(disease_id, lang, text, focus="info")
            if answer:
                return {
                    "text": answer,
                    "meta": {"intent": "disease_info", "disease": disease_id, "lang": lang, "generator": gen},
                }

    if intent_name == "prevention":
        disease_id = entities.find_disease(text)
        if disease_id:
            answer, gen = _disease_answer(disease_id, lang, text, focus="prevention")
            if answer:
                return {
                    "text": answer,
                    "meta": {"intent": "prevention", "disease": disease_id, "lang": lang, "generator": gen},
                }

    if intent_name == "symptom_check" and not _is_info_question(text):
        symptoms = entities.find_symptoms(text)
        if symptoms:
            session.set("symptom_flow", {"turn": 1, "symptoms": symptoms})
            probe, gen = _symptom_probe(symptoms, lang, text)
            return {
                "text": probe,
                "meta": {
                    "intent": "symptom_check",
                    "flow": "symptom_probe",
                    "symptoms": symptoms,
                    "lang": lang,
                    "generator": gen,
                },
            }

    if intent_name == "vaccination":
        context, fallback, sources = _vaccine_response(text, lang)
        answer, gen = _llm_wrap(context, text, lang, fallback, sources)
        return {"text": answer, "meta": {"intent": "vaccination", "lang": lang, "generator": gen}}

    if intent_name == "outbreak":
        return {"text": _outbreak_response(lang), "meta": {"intent": "outbreak", "lang": lang}}

    symptoms = entities.find_symptoms(text) if not _is_info_question(text) else []
    if symptoms:
        session.set("symptom_flow", {"turn": 1, "symptoms": symptoms})
        probe, gen = _symptom_probe(symptoms, lang, text)
        return {
            "text": probe,
            "meta": {
                "intent": "symptom_check",
                "flow": "symptom_probe",
                "symptoms": symptoms,
                "lang": lang,
                "generator": gen,
            },
        }

    results = retriever.retrieve(text)
    for top in results:
        if top["type"] == "myth":
            continue
        if not relevance.accept(text, top, _retrieval_relevant(text, top)):
            continue
        if top["type"] == "disease":
            answer, gen = _disease_answer(top["id"], lang, text)
            if answer and not generator.looks_unsure(answer):
                return {
                    "text": answer,
                    "meta": {"intent": "retrieval", "type": "disease", "lang": lang, "score": top["score"], "generator": gen},
                }
        if top["type"] == "faq":
            context, fallback, sources = _faq_answer(top["id"], lang)
            if fallback:
                answer, gen = _llm_wrap(context, text, lang, fallback, sources)
                if answer and not generator.looks_unsure(answer):
                    return {
                        "text": answer,
                        "meta": {"intent": "retrieval", "type": "faq", "lang": lang, "score": top["score"], "generator": gen},
                    }

    answer, source = _fallback_answer(text, lang, session)
    return {"text": answer, "meta": {"intent": "fallback", "source": source, "lang": lang}}
