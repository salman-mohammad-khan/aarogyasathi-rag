"""v2 fact-check (S5): a health claim in, a verdict with the evidence behind it out.

    claim ("fact check: papaya leaf juice cures dengue")
      1. curated myths (v1 list of 64 human-checked myths + dangerous first-aid rules), matched with e5
      2. the library: search, then the answer model judges the claim against the 5 pages it found
      3. trusted websites (same allowlist as S4b) when the library has no evidence
      4. model's own view, only in the safe direction ("LIKELY MYTH" or "NOT ENOUGH EVIDENCE", never "VERIFIED"),
         only for claims that pass the S4b risk check, always labelled
      5. otherwise "NOT ENOUGH EVIDENCE - please ask a doctor"

Verdicts: VERIFIED, MYTH, PARTLY TRUE, NOT ENOUGH EVIDENCE, and LIKELY MYTH (model view only). There is no
percentage: v1's "confidence" was a similarity score, not a probability. Instead every verdict says what it is based
on ("Based on 2 national guidelines", "Based on 1 trusted website", ...).
"""
import re
from dataclasses import dataclass, field

from langchain_core.prompts import ChatPromptTemplate

from app.answer import checks, general
from app.answer.chain import _text_only
from app.answer.citations import cited_numbers, normalise_markers, remove_invalid_markers, source_list
from app.answer.prompt import LANGUAGE_NAMES, format_sources
from app.factcheck import verifier

E5_THRESHOLDS = {"pairs": ((0.885, 0.25), (0.94, 0.0)), "plain": (0.885, 0.10), "remedy_sure": 0.97}

LABELS = {
    "en": {"TRUE": "VERIFIED", "MYTH": "MYTH", "PARTLY_TRUE": "PARTLY TRUE", "NOT_ENOUGH_EVIDENCE": "NOT ENOUGH EVIDENCE",
           "LIKELY_MYTH": "LIKELY MYTH"},
    "hi": {"TRUE": "सत्य", "MYTH": "भ्रांति", "PARTLY_TRUE": "आंशिक सत्य", "NOT_ENOUGH_EVIDENCE": "पर्याप्त प्रमाण नहीं",
           "LIKELY_MYTH": "संभवतः भ्रांति"},
    "hinglish": {"TRUE": "SACH (VERIFIED)", "MYTH": "MYTH (GALAT)", "PARTLY_TRUE": "AADHA SACH", "NOT_ENOUGH_EVIDENCE":
                 "PAKKA SABOOT NAHI", "LIKELY_MYTH": "SHAYAD MYTH"},
}
TITLE = {"en": "Fact check", "hi": "फैक्ट चेक", "hinglish": "Fact check"}
BASIS = {
    "curated": {"en": "Based on a curated list of common health myths checked against {s}.",
                "hi": "आम स्वास्थ्य भ्रांतियों की जाँची गई सूची के आधार पर ({s})।",
                "hinglish": "Aam health myths ki jaanchi hui list ke aadhar par ({s})."},
    "library": {"en": "Based on {n} official document(s) in the health library.",
                "hi": "स्वास्थ्य लाइब्रेरी के {n} आधिकारिक दस्तावेज़ों के आधार पर।",
                "hinglish": "Health library ke {n} official document(s) ke aadhar par."},
    "trusted_web": {"en": "Based on a trusted health website (not my library).",
                    "hi": "एक विश्वसनीय स्वास्थ्य वेबसाइट के आधार पर (मेरी लाइब्रेरी से नहीं)।",
                    "hinglish": "Ek trusted health website ke aadhar par (meri library se nahi)."},
    "general": {"en": "General view, not from a verified source. Please confirm with a doctor or your ASHA worker.",
                "hi": "यह सामान्य राय है, किसी सत्यापित स्रोत से नहीं। कृपया डॉक्टर या आशा दीदी से पुष्टि करें।",
                "hinglish": "Yeh general raay hai, kisi verified source se nahi. Doctor ya ASHA didi se confirm karein."},
    "none": {"en": "No evidence found in official sources or trusted websites. Please ask a doctor before believing "
                   "or sharing this claim.",
             "hi": "आधिकारिक स्रोतों या विश्वसनीय वेबसाइटों में कोई प्रमाण नहीं मिला। इस दावे पर भरोसा करने या आगे भेजने से "
                   "पहले डॉक्टर से पूछें।",
             "hinglish": "Official sources ya trusted websites mein koi saboot nahi mila. Is daawe par bharosa karne ya "
                         "aage bhejne se pehle doctor se poochhein."},
}

JUDGE_SYSTEM = """You check health claims for people in rural India against numbered sources.
Rules:
1. Use ONLY the numbered sources. Do not use your own knowledge.
2. VERDICT must be one of: TRUE (the sources clearly support the claim), MYTH (the sources clearly contradict it),
   PARTLY_TRUE (the sources support part of it, or it is true only in some cases), NOT_ENOUGH_EVIDENCE (the
   sources do not say). If the sources do not mention the claim at all, the verdict is NOT_ENOUGH_EVIDENCE, even
   if the claim sounds wrong.
   The person lives in India: when an Indian national source (MoHFW, NHM, NCDC, NCVBDC, NHSRC, ASHA module) and an
   international one differ, judge by the Indian source.
3. EXPLANATION: 40-80 simple words, cite the source numbers like [1], say what is actually true and what to do
   instead. Never give a medicine amount or frequency. Do not tell anyone to start or stop a medicine.
Reply in exactly this form:
VERDICT: <one verdict>
EXPLANATION: <text>"""
JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", JUDGE_SYSTEM),
    ("human", "Sources:\n{sources}\n\nClaim: {claim}\n\nReply language for the EXPLANATION: {language}. Keep the "
              "words VERDICT and EXPLANATION and the verdict itself in English."),
])

VIEW_SYSTEM = """No official source covers this health claim. Give a cautious general view.
VERDICT must be LIKELY_MYTH (there is no good evidence for it, or it goes against basic medical knowledge) or
NOT_ENOUGH_EVIDENCE (you are not sure). Never say it is true. EXPLANATION: 30-60 simple words on why, and advise
seeing a doctor; no medicine names, amounts or remedies to try.
Reply in exactly this form:
VERDICT: <LIKELY_MYTH or NOT_ENOUGH_EVIDENCE>
EXPLANATION: <text>"""
VIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", VIEW_SYSTEM),
    ("human", "Claim: {claim}\n\nReply language for the EXPLANATION: {language}. Keep VERDICT and EXPLANATION and the "
              "verdict itself in English."),
])
_REPLY = re.compile(r"VERDICT:\s*(TRUE|MYTH|PARTLY_TRUE|NOT_ENOUGH_EVIDENCE|LIKELY_MYTH)\s*\n+\s*EXPLANATION:\s*(.+)",
                    re.IGNORECASE | re.DOTALL)


@dataclass
class FactResult:
    claim: str
    lang: str
    verdict: str  # TRUE | MYTH | PARTLY_TRUE | NOT_ENOUGH_EVIDENCE | LIKELY_MYTH
    basis: str  # curated | library | trusted_web | general | none
    explanation: str
    sources: list[dict] = field(default_factory=list)  # citations shown under the answer
    source_names: list[str] = field(default_factory=list)  # curated entries: names without links

    def text(self) -> str:
        label = LABELS[self.lang][self.verdict]
        n = len({(s["url"], s.get("page")) for s in self.sources})
        basis = BASIS[self.basis][self.lang].format(n=n, s=", ".join(self.source_names) or "WHO, MoHFW")
        head = f"[{TITLE[self.lang]}] {label}"
        return f"{head}\n{self.explanation}\n\n{basis}" if self.explanation else f"{head}\n{basis}"

    def api(self) -> dict:
        return {"verdict": LABELS["en"][self.verdict], "basis": self.basis, "confidence": None,
                "fear_mongering": False, "tags": [], "sources": self.source_names or
                sorted({s.get("publisher") or s["title"] for s in self.sources})}


def _parse(reply: str):
    match = _REPLY.search(reply or "")
    if not match:
        return None, ""
    return match.group(1).upper(), match.group(2).strip()


class FactChecker:
    def __init__(self, searcher, web_searcher, llm, ask_risk, embed_texts):
        self.searcher, self.web, self.llm, self.ask_risk = searcher, web_searcher, llm, ask_risk
        verifier.MATCH_THRESHOLDS["e5"] = E5_THRESHOLDS
        verifier.use_embedder("e5", embed_texts)

    # --- 1. curated myths ---------------------------------------------------------------------------------------
    def curated(self, text: str, lang: str, plain: bool = False) -> FactResult | None:
        result = verifier.verify_claim(text, "hi" if lang != "en" else "en", strict_remedy=plain, allow_live=False,
                                       plain=plain)
        if result.get("verdict") in ("UNVERIFIABLE", "INVALID", None):
            return None
        explanation = result["explanation"].get("hi" if lang != "en" else "en") or result["explanation"].get("en", "")
        explanation = checks.remove_dose_sentences(explanation)  # curated texts follow the same dose rule
        names = [s.get("name", "") for s in result.get("sources", []) if s.get("name")]
        verdict = {"VERIFIED": "TRUE", "PARTLY TRUE": "PARTLY_TRUE"}.get(result["verdict"], result["verdict"])
        if verdict not in LABELS["en"]:
            return None
        return FactResult(result["claim"], lang, verdict, "curated", explanation, source_names=names)

    # --- 2 and 3. judge against found pages ---------------------------------------------------------------------
    def _judge(self, claim: str, lang: str, chunks: list[dict], basis: str) -> FactResult | None:
        if not chunks:
            return None
        try:
            reply = _text_only((JUDGE_PROMPT | self.llm).invoke(
                {"sources": format_sources(chunks), "claim": claim, "language": LANGUAGE_NAMES[lang]}))
        except Exception:
            return None
        verdict, explanation = _parse(reply)
        if verdict not in ("TRUE", "MYTH", "PARTLY_TRUE"):
            return None
        explanation = remove_invalid_markers(normalise_markers(explanation), len(chunks))
        if checks.gives_dose(explanation):
            explanation = checks.remove_dose_sentences(explanation)
        numbers = cited_numbers(explanation, len(chunks))
        if not numbers or not explanation or checks.leaks_prompt(explanation) or \
                checks.wrong_language(explanation, lang):
            return None  # a verdict that points to no source, or fails a check, is not shown
        return FactResult(claim, lang, verdict, basis, explanation, sources=source_list(chunks, numbers))

    # --- 4. model's view, safe direction only -------------------------------------------------------------------
    def _view(self, claim: str, lang: str, english: str) -> FactResult | None:
        if general.risk_label(claim, english, self.ask_risk) != "LOW":
            return None  # cures for serious disease, medicines, children, pregnancy: no model view
        try:
            reply = _text_only((VIEW_PROMPT | self.llm).invoke({"claim": claim, "language": LANGUAGE_NAMES[lang]}))
        except Exception:
            return None
        verdict, explanation = _parse(reply)
        if verdict not in ("LIKELY_MYTH", "NOT_ENOUGH_EVIDENCE") or not explanation or \
                checks.gives_dose(explanation) or checks.leaks_prompt(explanation) or \
                checks.wrong_language(explanation, lang):
            return None
        return FactResult(claim, lang, verdict, "general", explanation)

    def check(self, text: str, lang: str) -> FactResult:
        claim = verifier.clean_claim(text) or text
        curated = self.curated(text, lang)
        if curated:
            return curated
        found = self.searcher.search(claim)
        verdict = self._judge(claim, lang, found.chunks, "library")
        if verdict:
            return verdict
        if self.web is not None:
            verdict = self._judge(claim, lang, self.web.search(claim).chunks, "trusted_web")
            if verdict:
                return verdict
        verdict = self._view(claim, lang, found.query)
        if verdict:
            return verdict
        return FactResult(claim, lang, "NOT_ENOUGH_EVIDENCE", "none", "")
