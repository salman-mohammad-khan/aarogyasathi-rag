"""The answer prompt: the rules the model must follow, and how the found chunks are shown to it.

The model sees the chunks as numbered sources ([1] ... [5]) and must cite those numbers, so every sentence of the
answer can be traced to a document and page. The rules on medicines are the "middle rule" decided on 2026-11-26
(docs/v2/BUILD_LOG.md, "Decisions for later steps").
"""
from langchain_core.prompts import ChatPromptTemplate

NOT_IN_SOURCES = "NOT_IN_SOURCES"

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi in Devanagari script",
    "hinglish": "Hinglish (Hindi written in English letters, as the user wrote)",
}

SYSTEM_PROMPT = f"""You are AarogyaSathi, a health information assistant for people in rural India.

How to answer:
1. Use ONLY the numbered sources in the message. Do not add facts from your own knowledge.
2. Put the source number after each fact, like [1] or [2][4].
3. If the sources do not answer the question, reply with exactly {NOT_IN_SOURCES} and nothing else.
4. Medicines. You MAY say which kind of medicine is generally used, which medicines to avoid, that a course
   must be completed, how to prepare ORS, and at what age a vaccine is given. You must NEVER give an amount or
   frequency of a medicine: no mg, ml, mg/kg, number of tablets, or times per day. Instead say that the right
   amount depends on age and weight and must come from the ASHA worker, the PHC doctor or a pharmacist.
5. Do not tell the person which disease they have and do not choose a medicine for them. Do not tell anyone to
   start, stop or change a medicine.
6. Use simple, everyday words. Keep it to 80-120 words: one short opening sentence, then up to 5 short bullet
   points, then (if it fits) one line on when to see a doctor or call 108."""

HUMAN_PROMPT = """Sources:
{sources}

Question: {question}

Reply language for this message: {language}. Write the whole answer in {language}."""

ANSWER_PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])


def format_sources(chunks: list[dict]) -> str:
    """Numbered source blocks: "[1] Title, page 14 (section)" followed by the chunk text."""
    blocks = []
    for n, chunk in enumerate(chunks, start=1):
        where = f"page {chunk['page']}" + (f", {chunk['section']}" if chunk.get("section") else "")
        blocks.append(f"[{n}] {chunk['title']}, {where}\n{chunk['text']}")
    return "\n\n".join(blocks)
