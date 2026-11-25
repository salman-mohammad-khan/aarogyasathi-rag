"""Checks on the model's reply before it is shown: medicine amounts, language, leaked instructions.

These run on every answer because a prompt rule alone is not enough: in v1 testing Gemma followed injected
instructions 3 times out of 3 (docs/v2/BUILD_LOG.md and the audit), so the rules are also enforced in code.
"""
import re

from app.answer.prompt import SYSTEM_PROMPT

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# A number in digits or words; the look-behind stops "ek" matching inside "week".
_NUMBER = (r"(?<![\w.])(\d+(\.\d+)?|½|¼|one|two|three|four|half|full|whole|quarter|ek|do|teen|char|aadhi|aadha|"
           r"poori|puri|chauthai|एक|दो|तीन|चार|आधी|आधा|पूरी|पूरा|चौथाई)")
_DOSE_PATTERNS = [
    # an amount with a unit: "500 mg", "5 ml", "10 mg/kg", "500 मिलीग्राम", "20 मिग्रा", "5 मि.ली."
    re.compile(r"\d+(\.\d+)?\s*(mg|mcg|µg|ml|iu|units?)\b", re.IGNORECASE),
    re.compile(r"\d+(\.\d+)?\s*(मिलीग्राम|मिग्रा|मि\.?\s?ग्रा|एमजी|एम\.जी|माइक्रोग्राम|मिलीलीटर|मिली|मि\.?\s?ली|एमएल|"
               r"यूनिट)"),
    re.compile(r"\b(mg|ml)\s*/\s*kg\b", re.IGNORECASE),
    # a count of tablets/spoons/drops: "2 tablets", "ek goli", "दो गोली", "1 चम्मच"
    re.compile(_NUMBER + r"\s*(an?\s+|of\s+an?\s+)?(tablets?|tabs?|capsules?|pills?|doses?|goli|goliyan|spoons?|teaspoons?|drops?|"
               r"chammach|khurak|गोली|गोलियां|गोलियाँ|टैबलेट|कैप्सूल|चम्मच|बूंद|बूँद|खुराक|डोज़|डोज)", re.IGNORECASE),
    # a frequency: "twice a day", "3 times a day", "every 6 hours", "din me do baar", "har 6 ghante"
    re.compile(r"\b(twice|thrice|\d+\s*times)\s*(a|per)\s*day\b", re.IGNORECASE),
    re.compile(r"\bevery\s*\d+\s*(-|to)?\s*\d*\s*hours?\b", re.IGNORECASE),
    re.compile(r"din\s*(me|mein)\s*" + _NUMBER + r"\s*(baar|bar)|दिन\s*में\s*" + _NUMBER + r"\s*बार", re.IGNORECASE),
    re.compile(r"\bhar\s*\d+\s*(-|se)?\s*\d*\s*ghante|हर\s*\d+\s*(-|से)?\s*\d*\s*घंटे", re.IGNORECASE),
    # "din me zyada se zyada 4 baar", "दिन में अधिक से अधिक 4 बार", "6 ghante ka gap", "6 घंटे का अंतर"
    re.compile(r"din\s*(me|mein)\b.{0,30}?\d+\s*(baar|bar)\b|दिन\s*में.{0,30}?\d+\s*बार", re.IGNORECASE),
    re.compile(r"\d+\s*(ghante|ghanton|hours?)\s*(ka|ke|of)?\s*(gap|antar|interval|apart)|\d+\s*घंटे\s*(का|के)\s*(अंतर|गैप)",
               re.IGNORECASE),
]
# Line rule: a medicine form AND a number or frequency word on the same line is treated as a dose, e.g.
# "one iron-folic acid tablet daily", "जिंक की गोली 14 दिन तक रोज एक बार दें". Stricter than needed on purpose.
_MEDICINE_FORM = re.compile(r"\b(tablets?|capsules?|pills?|doses?|syrups?|goli|goliyan|khurak|dawai ki matra)\b|"
                            r"गोली|गोलियां|गोलियाँ|टैबलेट|कैप्सूल|खुराक|डोज़|डोज|सिरप", re.IGNORECASE)
_QUANTITY = re.compile(r"(?<![\w.])(\d+|½|¼|one|two|three|four|half|ek|teen|char|aadhi|aadha|एक|दो|तीन|चार|आधी|आधा)"
                       r"(?![\w])|\b(daily|once|twice|thrice|every day|each day|per day|a day|roz|rozana|roj|"
                       r"baar|\d+\s*times)\b|रोज़|रोज|रोजाना|प्रतिदिन|बार", re.IGNORECASE)  # no "do": "Do not ..."
_CITATION = re.compile(r"\[\d{1,2}\]")
# Vaccine schedule by age is allowed (middle rule): "Hepatitis B birth dose within 24 hours", "पहली खुराक 9 महीने".
_VACCINE = re.compile(r"vaccin|teek|immuni|\b(bcg|opv|ipv|penta\w*|rota\w*|measles|mr|hep\w*\s*b|dpt|td)\b|टीक|टीका|"
                      r"खसर|पेंटा|रोटा", re.IGNORECASE)
_AGE = re.compile(r"\b(birth|janam|janm|weeks?|months?|years?|saal|mahin\w*|hafte)\b|जन्म|हफ्ते|सप्ताह|महीन|साल|वर्ष",
                  re.IGNORECASE)


def _dose_line(line: str, about_vaccines: bool = False) -> bool:
    """A medicine form and a number/frequency on one line, unless it is a vaccine schedule by age."""
    line = _CITATION.sub("", line)
    if not (_MEDICINE_FORM.search(line) and _QUANTITY.search(line)):
        return False
    return not ((about_vaccines or _VACCINE.search(line)) and _AGE.search(line))


# Distinct phrases of the system prompt: if one appears in a reply, the reply is repeating the instructions.
_PROMPT_FINGERPRINTS = ("Use ONLY the numbered sources", "Do not add facts from your own knowledge",
                        "reply with exactly", "You must NEVER give an amount")


def gives_dose(text: str) -> bool:
    return any(_is_dose(line, bool(_VACCINE.search(text))) for line in text.splitlines())


def _is_dose(line: str, about_vaccines: bool) -> bool:
    return any(p.search(line) for p in _DOSE_PATTERNS) or _dose_line(line, about_vaccines)


def remove_dose_lines(text: str) -> str:
    """Drop every line that states a medicine amount or frequency; keep the rest of the answer."""
    about_vaccines = bool(_VACCINE.search(text))  # a schedule line may name the vaccine only in an earlier line
    return "\n".join(line for line in text.splitlines() if not _is_dose(line, about_vaccines)).strip()


def wrong_language(text: str, lang: str) -> bool:
    """Hindi answers must be mostly Devanagari; English and Hinglish answers must not be."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    share = sum(bool(_DEVANAGARI.match(c)) for c in letters) / len(letters)
    return share < 0.5 if lang == "hi" else share > 0.1


def leaks_prompt(text: str) -> bool:
    low = text.lower()
    return any(f.lower() in low for f in _PROMPT_FINGERPRINTS)


assert all(f.lower() in SYSTEM_PROMPT.lower() for f in _PROMPT_FINGERPRINTS), "fingerprints must match the prompt"
