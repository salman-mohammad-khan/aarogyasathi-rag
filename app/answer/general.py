"""Tier 3: a short general answer from the model's own knowledge, only for low-risk questions, always labelled.

Used only when neither the library (tier 1) nor a trusted website (tier 2) answered. Two gates decide whether a
question is low-risk enough:
  1. rules: anything about medicines or doses, diagnosis, pregnancy, babies and young children, mental-health crisis,
     or warning symptoms is high-risk (no model call);
  2. a short Gemma check, which must answer LOW; anything else (HIGH, unclear, error) counts as high-risk.
High-risk questions get the safe "ask your ASHA worker or doctor" reply instead. Low-risk answers go through the same
dose, language and prompt-leak checks as every other answer, and end with a fixed warning that they are not from a
verified source.
"""
import re

from langchain_core.prompts import ChatPromptTemplate

from app.answer import checks
from app.answer.prompt import LANGUAGE_NAMES

HIGH_RISK = re.compile(
    r"medicine|medication|tablet|capsule|syrup|injection|dose|dosage|\bmg\b|antibiotic|painkiller|steroid|"
    r"dawa|dawai|davai|goli|dose|दवा|दवाई|गोली|खुराक|इंजेक्शन|"
    r"pregnan|garbh|गर्भ|breastfeed|stanpan|स्तनपान|"
    r"\bbaby\b|babies|infant|newborn|toddler|\bchild\b|children|\bkid|navjaat|shishu|bachch|bacch|बच्च|शिशु|नवजात|"
    r"suicid|kill myself|self.?harm|depress|anxiety|panic|aatmahatya|आत्महत्या|"
    r"blood|bleed|khoon|खून|chest pain|seena|सीने|breath|saans|सांस|faint|behosh|बेहोश|unconscious|seizure|fits|"
    r"cancer|tumou?r|lump|gaanth|गांठ|"
    r"do i have|is it serious|which disease|kya mujhe|mujhe kya hua|कौन सी बीमारी",
    re.IGNORECASE)

# Three labels: with only LOW/HIGH plus "a non-health question is HIGH", Gemma still answered LOW for
# "Write a poem about the rain" (S4b check), so being about health is now its own decision.
RISK_PROMPT = ("You sort questions for a health chatbot that is not a doctor. Reply with exactly one label:\n"
               "NOT_HEALTH - the question is not about health or the body (poems, jobs, phones, general knowledge).\n"
               "HIGH - a health question about symptoms that might be serious, diagnosis, medicines, pregnancy, "
               "children, mental health, or anything where a wrong answer could cause harm.\n"
               "LOW - a health question about general wellness, hygiene, diet, sleep or lifestyle, where general "
               "information cannot hurt anyone.\n\nQuestion: {q}\n\nLabel:")

GENERAL_SYSTEM = """You are AarogyaSathi, a health information assistant for people in rural India. No official
source covers this question, so give only short, widely accepted general information.
Rules: 50-90 words in simple everyday words; one short opening sentence and up to 4 short bullet points; no medicine
names, amounts or frequencies; do not diagnose; do not mention sources or studies; end with one line saying to see a
doctor or ASHA worker if the problem continues."""
GENERAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", GENERAL_SYSTEM),
    ("human", "Question: {question}\n\nReply language for this message: {language}. Write the whole answer in "
              "{language}."),
])

GENERAL_NOTE = {
    "en": "General information, not from a verified source. Please confirm with a doctor or your ASHA worker.",
    "hi": "यह सामान्य जानकारी है, किसी सत्यापित स्रोत से नहीं। कृपया डॉक्टर या आशा दीदी से पुष्टि करें।",
    "hinglish": "Yeh general jaankari hai, kisi verified source se nahi. Doctor ya ASHA didi se zaroor confirm karein.",
}


# "Which antibiotic should I take", "best tablet for headache", "kaunsi dawai lu", "कौन सी दवा लें": the person wants
# a medicine chosen for them. Outside the library this is never answered (middle rule: no choosing medicines).
_WHICH_MEDICINE = re.compile(
    r"\b(which|best|good)\b.{0,30}\b(antibiotic|medicine|medication|tablet|pill|capsule|syrup|drug|cream|"
    r"ointment)s?\b|\b(antibiotic|medicine|tablet|pill|drug)s?\b.{0,20}\b(should i|to take|to buy|best)\b|"
    r"\b(kaunsi|kaun si|konsi|kon si|kya)\b.{0,15}\b(dawai|dawa|davai|goli|tablet|medicine|antibiotic)\b|"
    r"\b(dawai|dawa|goli|tablet|antibiotic)\b.{0,20}\b(lu|loon|lun|le sakta|le sakti|kharidu|kaunsi)\b|"
    r"कौन\s*सी\s*(दवा|दवाई|गोली)|कौनसी\s*(दवा|दवाई|गोली)|(दवा|दवाई|गोली)\s*(लूं|लूँ|लू|लें)", re.IGNORECASE)
CHOOSE_MEDICINE = {
    "en": "Which medicine is right depends on the cause, your age, weight and health, so it must be chosen by a doctor "
          "after checking you. Please do not buy antibiotics or other medicines on your own. Visit your PHC or ask "
          "your ASHA worker. In an emergency, call 108.",
    "hi": "कौन सी दवा सही है, यह बीमारी की वजह, आपकी उम्र, वज़न और सेहत पर निर्भर करता है, इसलिए डॉक्टर जाँच के बाद ही "
          "दवा तय करें। कृपया एंटीबायोटिक या कोई भी दवा खुद से न खरीदें। PHC जाएँ या आशा दीदी से पूछें। आपात स्थिति में 108 पर कॉल करें।",
    "hinglish": "Kaunsi dawai sahi hai, yeh bimari ki wajah, aapki umar, wajan aur sehat par depend karta hai, isliye "
                "doctor check karke hi dawai tay kare. Antibiotic ya koi bhi dawai khud se na khareedein. PHC jaayein "
                "ya ASHA didi se poochhein. Emergency mein 108 par call karein.",
}


def asks_which_medicine(text: str) -> bool:
    return bool(_WHICH_MEDICINE.search(text or ""))


# Diseases whose national guidelines in the library give public medicine advice ("dengue: paracetamol, never
# aspirin or ibuprofen", "TB: complete the course", "diarrhoea: ORS and zinc"). A medicine question that names one of
# these is answered from the library; any other medicine-choice question is referred to a doctor (decided 2026-11-26).
GUIDANCE_DISEASES = {"dengue", "malaria", "diarrhoea", "tuberculosis", "heatstroke", "anaemia"}
_CHIKUNGUNYA = re.compile(r"chikun\w*|chikan\w*|चिकनगुनिया|चिकुनगुनिया", re.IGNORECASE)
_ANTIBIOTIC = re.compile(r"antibiotic|antibiotik|एंटीबायोटिक|एंटीबायोटिक्स", re.IGNORECASE)


def medicine_choice_needs_doctor(text: str) -> bool:
    """True when someone asks which medicine to take and the library must not answer it:
    - no disease with national guidance is named ("sar dard ke liye kaunsi dawai lu", "khansi ki best tablet"), or
    - an antibiotic is asked for (prescription only, and self-medication breeds resistance), whatever the disease.
    "dengue me bukhar ke liye kaunsi dawai" names dengue, so the library answers (paracetamol yes, aspirin no)."""
    if not asks_which_medicine(text):
        return False
    if _ANTIBIOTIC.search(text):
        return True
    from app.core import entities

    named = entities.find_disease(text) in GUIDANCE_DISEASES or bool(_CHIKUNGUNYA.search(text))
    return not named


def risk_label(question: str, english: str, ask_risk) -> str:
    """"NOT_HEALTH", "HIGH" or "LOW". The rules decide HIGH without a model call; otherwise Gemma labels it, and an
    unclear reply or an error counts as HIGH. `english` is the search rewrite, so Hindi is checked in English too."""
    if HIGH_RISK.search(question) or HIGH_RISK.search(english):
        return "HIGH"
    try:
        verdict = (ask_risk(RISK_PROMPT.format(q=english or question)) or "").strip().upper()
    except Exception:
        return "HIGH"
    for label in ("NOT_HEALTH", "LOW", "HIGH"):
        if verdict.startswith(label):
            return label
    return "HIGH"


def is_low_risk(question: str, english: str, ask_risk) -> bool:
    return risk_label(question, english, ask_risk) == "LOW"


def general_answer(question: str, lang: str, llm) -> str | None:
    """The labelled general answer, or None if the model's reply fails a check."""
    from app.answer.chain import _text_only

    try:
        reply = _text_only((GENERAL_PROMPT | llm).invoke({"question": question, "language": LANGUAGE_NAMES[lang]}))
    except Exception:
        return None
    text = reply.strip()
    if not text or checks.leaks_prompt(text) or checks.gives_dose(text) or checks.wrong_language(text, lang):
        return None
    return text + "\n\n" + GENERAL_NOTE[lang]
