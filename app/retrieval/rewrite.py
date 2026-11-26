"""Turn a Hindi or Hinglish question into English before searching.

Why: the library is in English. In the S2 test, Hinglish questions searched as typed found a right page only
33-48% of the time; rewritten to English first, 93-100%. The word list fixes everyday words the model got wrong
without it ("loo lagna" became "leukemia", "dast" became "rash").

Safety: the rewrite only changes what is SEARCHED. The answer is still written for the user's own question and
language. Whenever the rewrite fails, is slow, or does not come back in English, the original question is used.
"""
import re
from functools import lru_cache

# Everyday Hindi words for illnesses (S2 test: both rewrite models got these wrong without help).
GLOSSARY = ("loo / लू = heat stroke; dast / दस्त = diarrhoea; ulti / उल्टी = vomiting; bukhar / बुखार = fever; "
            "khansi / खांसी = cough; khoon ki kami / खून की कमी = anaemia; sugar / शुगर = diabetes; BP = blood pressure; "
            "pilia / पीलिया = jaundice; khasra / खसरा = measles; teeka / टीका = vaccine; machhardani / मच्छरदानी = "
            "mosquito net; saans / सांस = breathing; peshab / पेशाब = urine; garbh / गर्भ = pregnancy; "
            "din = days; hafte / हफ्ते = weeks; mahine / महीने = months; teen = three (not a teenager)")

# The exact prompt measured in S2 (eval/results/s2_bakeoff*.md, "gemma-3-27b+glossary").
REWRITE_PROMPT = (
    "Translate this health question into one short, plain English question. The reply must be in English only, "
    "with no Hindi or Hinglish words left. Keep every medical term. Reply with the question only.\n\n"
    "If the question uses one of these everyday Hindi words, this is its meaning: " + GLOSSARY + "\n\nQuestion: {q}")
REWRITE_SYSTEM = "You translate health questions into English for a search engine."
REWRITE_MAX_TOKENS = 60
REWRITE_TIMEOUT_S = 6
MAX_REWRITE_CHARS = 300

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Hindi words typed in English letters that are rare in English sentences. Two or more = Hinglish.
_HINGLISH_WORDS = frozenset("""
hai hain kya kaise kyu kyun kab kaun kitna kitne kitni nahi nahin mujhe mera meri mere hamara ka ke ki ko mein
bhi aur wala wale wali chahiye karna kare karein karu raha rahi rahe hota hoti hote gaya gayi lagta lagti lagte
ho jaye jana dena lena kuch bahut baar bachcha bachche bacche bimari dawai dawa ilaj ilaaj lakshan
se par pe bache bachne bachao bachav kare karen karu upay ghar sakte sakta sakti me khaye khana khana peena
piye pina kyon theek thik liye kaunsi konsi kaunse konse lu lun loon ne liya kaat kaata kata hua hui hue diya
""".split())


def needs_rewrite(question: str) -> bool:
    """True for Hindi (Devanagari letters) or Hinglish (two or more typical Hindi words); English skips the call."""
    if _DEVANAGARI.search(question):
        return True
    words = re.findall(r"[a-z]+", question.lower())
    return sum(w in _HINGLISH_WORDS for w in words) >= 2


def question_language(question: str) -> str:
    """"hi" (Devanagari letters), "hinglish" (Hindi in English letters) or "en". The answer is written in it."""
    if _DEVANAGARI.search(question):
        return "hi"
    return "hinglish" if needs_rewrite(question) else "en"


REWRITE_MODEL_ID = "google.gemma-3-27b-it"  # measured in S2
_rewrite_llm = None


def _call_model(prompt: str) -> str | None:
    """One short call to Gemma 3 27B on Bedrock through LangChain (same client and credentials as the answer step)."""
    global _rewrite_llm
    if _rewrite_llm is None:
        from botocore.config import Config
        from langchain_aws import ChatBedrockConverse

        _rewrite_llm = ChatBedrockConverse(
            model=REWRITE_MODEL_ID, region_name="ap-south-1", temperature=0, max_tokens=REWRITE_MAX_TOKENS,
            config=Config(read_timeout=REWRITE_TIMEOUT_S, connect_timeout=3, retries={"max_attempts": 1}))
    return _rewrite_llm.invoke([("system", REWRITE_SYSTEM), ("human", prompt)]).text


def to_english(question: str, ask=_call_model) -> str:
    """The question to search with: an English rewrite when needed and usable, otherwise the question itself.

    `ask` takes the prompt and returns the model's reply (or None); tests pass a fake one.
    """
    if not needs_rewrite(question):
        return question
    try:
        reply = ask(REWRITE_PROMPT.format(q=question))
    except Exception:
        return question
    lines = (reply or "").strip().splitlines()
    english = lines[0].replace("*", "").strip().strip('"').strip() if lines else ""  # first line, no quotes/bold
    if not english or len(english) > MAX_REWRITE_CHARS or needs_rewrite(english):
        return question  # empty, too long, or still Hindi/Hinglish: search with what the user typed
    return english


@lru_cache(maxsize=512)
def to_english_cached(question: str) -> str:
    """`to_english` with a memory of recent questions: when the library has no answer and the trusted-website
    search runs next, the same English rewrite is reused instead of calling the model twice."""
    return to_english(question)
