"""S5 check: the v2 fact-checker on known myths, true facts and new Hindi/Hinglish claims, with real models.

Run:  python -m eval.factcheck_eval      (needs Bedrock access and internet; about 4 minutes)

Each claim lists the verdicts that count as right. "plain" rows are sentences typed without "fact check": they must
be judged only when they match a curated myth (and ordinary questions must never be judged). Writes
eval/results/s5_factcheck.md and .json.
"""
import json
import time
from pathlib import Path

from app.answer import checks
from app.answer.chain import default_llm
from app.answer.factcheck import FactChecker
from app.answer.outside import _gemma_ask
from app.answer.trusted_web import WebSearcher
from app.core import kb
from app.factcheck import verifier
from app.retrieval.rewrite import question_language
from app.retrieval.search import Searcher

RESULTS = Path(__file__).resolve().parent / "results"
FALSE = {"MYTH", "LIKELY_MYTH"}
TRUE_ = {"TRUE"}
CLAIMS = [
    # v1 claim tests (curated myths), now matched with e5
    ("Garlic can cure dengue fever", FALSE), ("Giloy juice cures dengue", {"PARTLY_TRUE"}),
    ("Papaya leaf juice raises platelet count in dengue", {"PARTLY_TRUE"}),
    ("lehsun khane se dengue theek ho jata hai", FALSE), ("kutte ke kaatne par mirchi lagane se rabies nahi hota", FALSE),
    ("garam paani peene se corona khatam ho jata hai", FALSE), ("BP normal aa jaye to dawai band kar sakte hain", FALSE),
    # new false claims
    ("ORS should be stopped if the child vomits", FALSE),
    ("Toothpaste should be applied on a burn", FALSE),
    ("saanp kaatne par zakhm se zeher choos lena chahiye", FALSE),
    ("TB chhoone se ya bartan share karne se failta hai", FALSE | {"PARTLY_TRUE"}),
    ("मलेरिया की दवा बुखार उतरते ही बंद कर देनी चाहिए", FALSE),
    ("Polio drops can make children infertile later in life", FALSE),
    ("दस्त में बच्चे को खाना बंद कर देना चाहिए", FALSE),
    ("Drinking lemon water every morning burns belly fat", FALSE | {"NOT_ENOUGH_EVIDENCE"}),
    ("Dengue only spreads at night", FALSE),
    # true claims
    ("Dengue spreads through the bite of Aedes mosquitoes", TRUE_),
    ("ORS helps prevent dehydration in diarrhoea", TRUE_),
    ("TB ka ilaaj poora karna zaroori hai, beech mein dawai nahi chhodni chahiye", TRUE_),
    ("कुत्ते के काटने पर घाव को साबुन और पानी से धोना चाहिए", TRUE_),
    ("Mosquito nets help prevent malaria", TRUE_),
    ("Zinc is given to children with diarrhoea", TRUE_ | {"PARTLY_TRUE"}),
]
PLAIN_MYTHS = ["Garlic can cure dengue fever", "lehsun khane se dengue theek ho jata hai", "Dengue mosquitoes bite only at night",
               "Haldi can completely cure cancer", "kya lehsun se dengue theek hota hai",
               "Polio drops can make children infertile later in life"]
NOT_CLAIMS = ["Wearing a copper bracelet cures arthritis", "Onion in socks cures fever",
              "Neem leaves cure diabetes completely"]


def main():
    kb.load()
    searcher = Searcher()
    fc = FactChecker(searcher, WebSearcher(), default_llm(), _gemma_ask(), searcher.embedder.embed_queries)
    rows = []
    for claim, ok in CLAIMS:
        lang = question_language(claim)
        start = time.time()
        r = fc.check("fact check: " + claim, lang)
        problems = [] if r.verdict in ok else [f"verdict {r.verdict}, expected {'/'.join(sorted(ok))}"]
        if checks.gives_dose(r.explanation):
            problems.append("medicine amount")
        rows.append({"kind": "fact check", "claim": claim, "verdict": r.verdict, "basis": r.basis,
                     "seconds": round(time.time() - start, 1), "text": r.text(), "problems": problems})
    for claim in PLAIN_MYTHS:
        r = fc.curated(claim, question_language(claim), plain=True) if verifier.looks_like_claim(claim) else None
        rows.append({"kind": "plain myth", "claim": claim, "verdict": r.verdict if r else "-", "basis": "curated",
                     "seconds": 0, "text": r.text() if r else "", "problems": [] if r else ["not detected"]})
    for claim in NOT_CLAIMS:
        r = fc.curated(claim, question_language(claim), plain=True) if verifier.looks_like_claim(claim) else None
        rows.append({"kind": "plain, unknown", "claim": claim, "verdict": r.verdict if r else "-", "basis": "-",
                     "seconds": 0, "text": "", "problems": [f"wrongly matched ({r.verdict})"] if r else []})
    searcher.close()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "s5_factcheck.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# S5 fact-check", "", "| Kind | Claim | Verdict | Based on | Seconds | OK |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['kind']} | {r['claim']} | {r['verdict']} | {r['basis']} | {r['seconds']} | "
              f"{'yes' if not r['problems'] else '; '.join(r['problems'])} |" for r in rows]
    lines += ["", "## Replies", ""] + [f"### {r['claim']}\n\n{r['text']}\n" for r in rows if r["text"]]
    (RESULTS / "s5_factcheck.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[: len(rows) + 4]))
    print(f"\n{sum(not r['problems'] for r in rows)}/{len(rows)} as expected")


if __name__ == "__main__":
    main()
