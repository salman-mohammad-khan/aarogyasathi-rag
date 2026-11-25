"""S2 bake-off: which search method finds the right chunk for English, Hindi and Hinglish questions?

Run:  python -m eval.retrieval_bakeoff [--models e5-base,labse,titan-v2]
      python -m eval.retrieval_bakeoff --golden eval/golden_retrieval_hard.yaml --out s2_bakeoff_hard

Methods compared
  bm25            keyword search only
  <model>         embedding search only (e5-base, labse, titan-v2)
  <model>+bm25    both, merged with Reciprocal Rank Fusion (the "hybrid" search the plan proposes)
Each method is run on the question as typed, and on an English rewrite of Hindi and Hinglish questions made
by each rewrite model (Gemma 3 27B and gpt-oss-120b on Bedrock, same prompt). Rewrites are made once and saved in
eval/results/rewrites.json, so the test is repeatable. English questions are always used as typed.

Scores (per language and overall; the answer key is in eval/golden_retrieval.yaml)
  hit@5   share of questions with at least one correct chunk in the first 5 results (the answer step
          reads 5 chunks, so this is what matters most)
  MRR@10  average of 1 / position of the first correct chunk (1.0 = always first; 0 if not in the top 10)

Writes eval/results/s2_bakeoff.md and .json. Embeddings are cached in data/index/ (not in git).
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from app.retrieval.embedders import EMBEDDERS, passage_text
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword import KeywordIndex
from app.retrieval.rewrite import REWRITE_PROMPT as APP_REWRITE_PROMPT

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks" / "chunks.jsonl"
GOLDEN = ROOT / "eval" / "golden_retrieval.yaml"
CACHE = ROOT / "data" / "index"
RESULTS = ROOT / "eval" / "results"
REWRITES = RESULTS / "rewrites.json"
LANGS = ("en", "hi", "hinglish")
TOP_K = 5
MRR_DEPTH = 10
GEMMA, GPT_OSS = "google.gemma-3-27b-it", "openai.gpt-oss-120b-1:0"
REWRITE_PROMPT = ("Rewrite this health question as one short, plain English question. Keep every medical term. "
                  "Reply with the question only.\n\nQuestion: {q}")
# The word-list prompt is the one the app uses (app/retrieval/rewrite.py). Its first version put the list under
# "Common words:" and Gemma then often copied the Hinglish back untranslated ("Typhoid kaise failta hai?").
REWRITE_PROMPT_GLOSSARY = APP_REWRITE_PROMPT
# name -> (Bedrock model id, prompt)
REWRITERS = {
    "gemma-3-27b": (GEMMA, REWRITE_PROMPT),
    "gpt-oss-120b": (GPT_OSS, REWRITE_PROMPT),
    "gemma-3-27b+glossary": (GEMMA, REWRITE_PROMPT_GLOSSARY),
    "gpt-oss-120b+glossary": (GPT_OSS, REWRITE_PROMPT_GLOSSARY),
}


def load_chunks():
    return [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]


def is_relevant(topic: dict, chunk: dict) -> bool:
    text = chunk["text"].lower()
    return (chunk["source_id"] in topic["sources"]
            and any(p in text for p in topic["any"])
            and all(p in text for p in topic.get("all", [])))


def load_questions(chunks, golden: Path = GOLDEN):
    """One row per question: topic, language, text and the set of chunk positions that count as correct.

    A topic either has `questions: {en, hi, hinglish}` (first set: one topic asked three ways) or a single
    `question` with its `lang` (hard set)."""
    rows = []
    for topic in yaml.safe_load(Path(golden).open(encoding="utf-8"))["topics"]:
        correct = {i for i, c in enumerate(chunks) if is_relevant(topic, c)}
        assert correct, f"answer key for {topic['id']} matches no chunk"
        asked = topic["questions"].items() if "questions" in topic else [(topic["lang"], topic["question"])]
        for lang, question in asked:
            rows.append({"topic": topic["id"], "lang": lang, "question": question, "correct": correct})
    return rows


def _rewrite(client, model_id: str, prompt: str, question: str) -> str:
    extra = {"reasoning_effort": "low"} if model_id.startswith("openai.") else {}
    reply = client.converse(modelId=model_id,
                            messages=[{"role": "user", "content": [{"text": prompt.format(q=question)}]}],
                            inferenceConfig={"maxTokens": 400 if extra else 60, "temperature": 0},
                            additionalModelRequestFields=extra)
    # gpt-oss returns its reasoning as a separate block first; the answer is the block with "text".
    text = next(block["text"] for block in reply["output"]["message"]["content"] if "text" in block)
    return text.strip().strip('"').replace("*", "")


def english_rewrites(rows) -> dict:
    """{rewriter name: {Hindi/Hinglish question: English question}}, made once on Bedrock and then read from file."""
    saved = json.loads(REWRITES.read_text(encoding="utf-8")) if REWRITES.exists() else {}
    for old_key, name in ((GEMMA, "gemma-3-27b"), (GPT_OSS, "gpt-oss-120b")):  # first runs were keyed by model id
        if old_key in saved:
            saved[name] = saved.pop(old_key)
    client = None
    for name, (model_id, prompt) in REWRITERS.items():
        done = saved.setdefault(name, {})
        for q in (r["question"] for r in rows if r["lang"] != "en"):
            if q not in done:
                if client is None:
                    import boto3

                    client = boto3.client("bedrock-runtime", region_name="ap-south-1")
                done[q] = _rewrite(client, model_id, prompt, q)
            done[q] = done[q].replace("*", "")
    RESULTS.mkdir(parents=True, exist_ok=True)
    REWRITES.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    return saved


def document_vectors(embedder, chunks) -> np.ndarray:
    """Embed every chunk once and keep the result on disk; rebuilt when the chunk file changes.

    Work is saved every 200 chunks (in a ".partial.npy" file), so a stopped run continues where it ended.
    This matters for Titan: the account allows about one call per second, so the library takes ~1 hour.
    """
    fingerprint = hashlib.sha256("".join(c["id"] + c["text"] for c in chunks).encode()).hexdigest()[:12]
    path = CACHE / f"emb_{embedder.name}_{fingerprint}.npy"
    partial = path.with_suffix(".partial.npy")
    if path.exists():
        return np.load(path)
    CACHE.mkdir(parents=True, exist_ok=True)
    texts = [passage_text(c) for c in chunks]
    blocks = [np.load(partial)] if partial.exists() else []
    done = sum(len(b) for b in blocks)
    for start in range(done, len(texts), 200):
        blocks.append(embedder.embed_documents(texts[start:start + 200]).astype(np.float32))
        np.save(partial, np.vstack(blocks))
        print(f"  {embedder.name}: {min(start + 200, len(texts))}/{len(texts)} chunks embedded", flush=True)
    vectors = np.vstack(blocks)
    np.save(path, vectors)
    partial.unlink(missing_ok=True)
    return vectors


def score(rankings: list[list[int]], rows) -> dict:
    """hit@5 and MRR@10 per language and overall."""
    out = {}
    for lang in (*LANGS, "all"):
        hits, rr = [], []
        for ranking, row in zip(rankings, rows):
            if lang != "all" and row["lang"] != lang:
                continue
            first = next((pos for pos, i in enumerate(ranking[:MRR_DEPTH], 1) if i in row["correct"]), None)
            hits.append(first is not None and first <= TOP_K)
            rr.append(1 / first if first else 0.0)
        out[lang] = {"hit@5": round(float(np.mean(hits)), 3), "mrr@10": round(float(np.mean(rr)), 3)}
    return out


def main(model_names, golden: Path = GOLDEN, out_name: str = "s2_bakeoff"):
    chunks = load_chunks()
    rows = load_questions(chunks, golden)
    rewrites = english_rewrites(rows)
    query_sets = {"as typed": [r["question"] for r in rows]}
    for name in REWRITERS:
        query_sets[f"rewrite {name}"] = [rewrites[name].get(r["question"], r["question"]) for r in rows]
    bm25 = KeywordIndex([passage_text(c) for c in chunks])

    def top(scores):
        return list(np.argsort(-np.asarray(scores))[:50])

    keyword_rank = {mode: [top(bm25.scores(q)) for q in queries] for mode, queries in query_sets.items()}
    results, misses = {}, {}
    for mode in query_sets:
        results[f"bm25 | {mode}"] = score(keyword_rank[mode], rows)
    for name in model_names:
        embedder = EMBEDDERS[name]()  # loaded once per model
        docs = document_vectors(embedder, chunks)
        # English questions repeat across the query sets: embed each distinct text once.
        distinct = sorted({q for queries in query_sets.values() for q in queries})
        query_vector = {q: embedder.embed_query(q) for q in distinct}
        for mode, queries in query_sets.items():
            dense_rank = [top(docs @ query_vector[q]) for q in queries]
            hybrid_rank = [reciprocal_rank_fusion([d, k]) for d, k in zip(dense_rank, keyword_rank[mode])]
            results[f"{name} | {mode}"] = score(dense_rank, rows)
            results[f"{name}+bm25 | {mode}"] = score(hybrid_rank, rows)
            for label, ranks in ((name, dense_rank), (f"{name}+bm25", hybrid_rank)):
                misses[f"{label} | {mode}"] = [f"{r['topic']} ({r['lang']})" for ranking, r in zip(ranks, rows)
                                               if not set(ranking[:TOP_K]) & r["correct"]]
        del embedder
    write_report(results, misses, rows, rewrites, Path(golden), out_name)
    return results


def write_report(results, misses, rows, rewrites, golden: Path, out_name: str):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{out_name}.json").write_text(json.dumps({"scores": results, "misses": misses}, indent=2),
                                              encoding="utf-8")
    per_lang = ", ".join(f"{lang} {sum(r['lang'] == lang for r in rows)}" for lang in LANGS)
    lines = [f"# S2 retrieval bake-off: {golden.name}", "",
             f"{len(rows)} questions ({per_lang}). hit@5 / MRR@10.", "",
             "| Method | Query | English | Hindi | Hinglish | All |", "|---|---|---|---|---|---|"]
    for key, s in results.items():
        method, mode = key.split(" | ")
        cells = [f"{s[l]['hit@5']:.2f} / {s[l]['mrr@10']:.2f}" for l in (*LANGS, "all")]
        lines.append(f"| {method} | {mode} | " + " | ".join(cells) + " |")
    lines += ["", "## Questions missed (no correct chunk in the top 5)", ""]
    lines += [f"- **{k}**: {', '.join(v) or 'none'}" for k, v in misses.items()]
    lines += ["", "## English rewrites used", "", "| Question | " + " | ".join(REWRITERS) + " |",
              "|---|" + "---|" * len(REWRITERS)]
    for q in (r["question"] for r in rows if r["lang"] != "en"):
        lines.append(f"| {q} | " + " | ".join(rewrites[m].get(q, "") for m in REWRITERS) + " |")
    (RESULTS / f"{out_name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="e5-base,labse,titan-v2")
    parser.add_argument("--golden", default=str(GOLDEN))
    parser.add_argument("--out", default="s2_bakeoff")
    args = parser.parse_args()
    for key, s in main(args.models.split(","), Path(args.golden), args.out).items():
        print(f"{key:34} " + "  ".join(f"{l}={s[l]['hit@5']:.2f}/{s[l]['mrr@10']:.2f}" for l in (*LANGS, "all")))
