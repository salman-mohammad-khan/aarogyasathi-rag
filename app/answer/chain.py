"""The answer chain (LangChain LCEL) and the checks around it.

    question
      -> search (S2): English rewrite, e5 + BM25, top 5 chunks
      -> ANSWER_PROMPT (rules + numbered sources + reply language)
      -> chat model on Bedrock (ChatBedrockConverse; Qwen3-235B, falling back to Gemma 3 27B)
      -> checks: "not in sources", citations, medicine amounts, language, leaked instructions
      -> Answer(text, sources, status)

The LCEL part is `build_chain`: each `|` passes a dict to the next step, and `RunnablePassthrough.assign` adds
one key (search result, sources text, reply) without losing the others, so every intermediate value can be
inspected in tests and in the evaluation.
"""
import time
from dataclasses import dataclass, field

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.answer import checks
from app.answer.citations import cited_numbers, normalise_markers, remove_invalid_markers, source_list
from app.answer.prompt import ANSWER_PROMPT, LANGUAGE_NAMES, NOT_IN_SOURCES, format_sources
from app.retrieval.rewrite import question_language

# Chosen in S3 (docs/v2/BUILD_LOG.md): Qwen3-235B and Gemma 3 27B tied on accuracy and safety; Qwen wrote more natural
# Hinglish, kept to the length rule and was faster (it costs ~$0.14 more per 1,000 answers). Gemma takes over if Qwen fails.
ANSWER_MODEL_ID = "qwen.qwen3-235b-a22b-2507-v1:0"
FALLBACK_MODEL_ID = "google.gemma-3-27b-it"
REGION = "ap-south-1"
MAX_TOKENS = 450
ANSWER_TIMEOUT_S = 20

# Fixed replies, used when the model's own answer cannot be shown.
NOT_COVERED = {
    "en": "My health library does not cover this question yet. Please ask your ASHA worker or the doctor at the "
          "nearest health centre. In an emergency, call 108.",
    "hi": "मेरी स्वास्थ्य जानकारी में अभी इस सवाल का जवाब नहीं है। कृपया अपनी आशा दीदी या नज़दीकी स्वास्थ्य केंद्र के "
          "डॉक्टर से पूछें। आपात स्थिति में 108 पर कॉल करें।",
    "hinglish": "Meri health library mein abhi is sawaal ka jawab nahi hai. Apni ASHA didi ya nazdeeki health centre "
                "ke doctor se poochhein. Emergency mein 108 par call karein.",
}
DOSE_NOTE = {
    "en": "The right amount of any medicine depends on age and weight. Please ask your ASHA worker, the PHC doctor "
          "or a pharmacist.",
    "hi": "किसी भी दवा की सही मात्रा उम्र और वज़न पर निर्भर करती है। कृपया आशा दीदी, PHC डॉक्टर या फार्मासिस्ट से पूछें।",
    "hinglish": "Kisi bhi dawai ki sahi matra umar aur wajan par depend karti hai. ASHA didi, PHC doctor ya "
                "pharmacist se poochhein.",
}

TRY_AGAIN = {
    "en": "Sorry, I could not answer just now. Please try again in a minute. In an emergency, call 108.",
    "hi": "माफ़ कीजिए, अभी जवाब नहीं दे पाया। कृपया एक मिनट बाद फिर पूछें। आपात स्थिति में 108 पर कॉल करें।",
    "hinglish": "Maaf kijiye, abhi jawab nahi de paaya. Ek minute baad dobara poochhein. Emergency mein 108 par call "
                "karein.",
}


@dataclass
class Answer:
    question: str
    language: str  # "en", "hi" or "hinglish"
    text: str  # what the user sees
    status: str  # answered | not_covered | dose_removed | wrong_language | leaked | error
    query: str = ""  # what search used (English rewrite or the question)
    sources: list[dict] = field(default_factory=list)  # cited documents and pages
    chunks: list[dict] = field(default_factory=list)  # all 5 chunks given to the model (for evaluation)
    raw_reply: str = ""  # the model's reply before the checks
    seconds: float = 0.0
    tier: str = "library"  # library | trusted_web | general | none (S4b)


def make_llm(model_id: str = ANSWER_MODEL_ID, region: str = REGION):
    """A LangChain chat model for Bedrock's Converse API. gpt-oss gets low reasoning effort (faster, cheaper)."""
    from botocore.config import Config
    from langchain_aws import ChatBedrockConverse

    extra = {"reasoning_effort": "low"} if model_id.startswith("openai.") else None
    # A stuck call gives up after 20 s so the fallback model (or the "try again" reply) can take over.
    timeouts = Config(read_timeout=ANSWER_TIMEOUT_S, connect_timeout=5, retries={"max_attempts": 2})
    return ChatBedrockConverse(model=model_id, region_name=region, temperature=0, max_tokens=MAX_TOKENS,
                               additional_model_request_fields=extra, config=timeouts)


def _text_only(message) -> str:
    """The reply text. Reasoning models (gpt-oss) also return reasoning blocks, which are left out."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")


def build_chain(searcher, llm, prompt=ANSWER_PROMPT):
    """question dict in -> dict with search result, sources text, language and the model's raw reply out."""
    return (
        RunnablePassthrough.assign(found=RunnableLambda(lambda x: searcher.search(x["question"])))
        | RunnablePassthrough.assign(
            sources=RunnableLambda(lambda x: format_sources(x["found"].chunks)),
            language=RunnableLambda(lambda x: LANGUAGE_NAMES[x["lang"]]),
        )
        | RunnablePassthrough.assign(reply=prompt | llm | RunnableLambda(_text_only) | StrOutputParser())
    )


def finish(question: str, lang: str, found, reply: str) -> Answer:
    """Apply the checks to the model's reply and decide what the user sees."""
    chunks = found.chunks
    base = dict(question=question, language=lang, query=found.query, chunks=chunks, raw_reply=reply)
    text = reply.strip()
    if not text or NOT_IN_SOURCES in text or not chunks:
        return Answer(text=NOT_COVERED[lang], status="not_covered", **base)
    if checks.leaks_prompt(text):
        return Answer(text=NOT_COVERED[lang], status="leaked", **base)
    text = remove_invalid_markers(normalise_markers(text), len(chunks))
    status = "answered"
    if checks.gives_dose(text):  # the prompt forbids amounts; if one slips through, drop those lines
        kept = checks.remove_dose_lines(text)
        text = (kept + "\n\n" if kept else "") + DOSE_NOTE[lang]
        status = "dose_removed"
    if checks.wrong_language(text, lang):
        return Answer(text=NOT_COVERED[lang], status="wrong_language", **base)
    numbers = cited_numbers(text, len(chunks))
    if not numbers:  # nothing left points to a source
        if status == "dose_removed":
            return Answer(text=DOSE_NOTE[lang], status=status, **base)
        return Answer(text=NOT_COVERED[lang], status="not_covered", **base)
    return Answer(text=text, status=status, sources=source_list(chunks, numbers), **base)


def default_llm():
    """Qwen first; if the call fails (error, timeout, throttling), LangChain runs the same prompt on Gemma."""
    return make_llm(ANSWER_MODEL_ID).with_fallbacks([make_llm(FALLBACK_MODEL_ID)])


class Answerer:
    def __init__(self, searcher, llm=None, prompt=ANSWER_PROMPT):
        self.searcher = searcher
        self.chain = build_chain(searcher, llm or default_llm(), prompt)

    def answer(self, question: str, lang: str | None = None) -> Answer:
        """`lang` overrides detection, e.g. a Hinglish follow-up joined to an English question keeps Hinglish."""
        start = time.time()
        lang = lang or question_language(question)
        try:
            out = self.chain.invoke({"question": question, "lang": lang})
            result = finish(question, lang, out["found"], out["reply"])
        except Exception:  # Bedrock down, timeout, throttling: never show a half answer or an error trace
            result = Answer(question=question, language=lang, text=TRY_AGAIN[lang], status="error")
        result.seconds = round(time.time() - start, 2)
        return result
