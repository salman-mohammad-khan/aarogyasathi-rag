# AarogyaSathi v2: build log

A step-by-step record of the v2 rebuild: what was built, every source and library used (with links and versions),
why each choice was made, what was considered instead, and the measured result. One section per step.

Plan documents (outside the repo): `AarogyaSathi_Implementation_Plan_2026-11-25` and
`AarogyaSathi_Sources_Embeddings_Cost_2026-11-25`.

---

## S0: clean-up (2026-11-25, PR #23)

**Goal.** Remove what v2 will not use, so later steps start from a small, honest codebase.

**Done.**
- Tag `v1-legacy` (commit 37dbbb0, the version live on 2026-11-25) keeps all of v1.
- Removed: surveillance prototype and its routes, `/admin` dashboard, `/api/stats`, `/api/intents`, the pincode
  field, the Twilio adapter, the local and Ollama-cloud model tiers.
- WhatsApp webhook routes only when `WHATSAPP_ENABLED=true`; the default verify token was removed.
- `requirements.txt` pinned to the exact versions on the server.

**Why.**
- Pinning: CI failed on 2026-11-23 because it installed FastAPI 0.165 while the code was tested on 0.136.
  FastAPI 0.165 keeps included routers as nested objects, which broke a route test.
- Ollama tiers: in testing the 1.7B local model gave wrong vaccine and treatment advice; template answers are safer.
- WhatsApp off by default: the portfolio server received one webhook call in the last 7 days.

**Deferred.** Removing the router, the TF-IDF intent model and moving the safety code to `app/safety/` moved to S4,
where `pipeline.py` replaces the router (doing it twice would waste time).

**Result.** 506 tests pass; the safety suites (338 tests) are unchanged.

---

## S1: document library and chunking (2026-11-25)

**Goal.** Turn official health documents into small, citable pieces of text ("chunks") for search in S2.

### Pipeline

```
sources/manifest.yaml ─► ingest/fetch.py ─► ingest/load.py ─► ingest/clean.py ─► ingest/chunk.py ─► data/chunks/chunks.jsonl
   (list of sources)      (download,         (PDF/HTML ->       (headers, page     (LangChain splitter,
                           checksum)          page text)         numbers, hyphens)  page + section + flags)
```

Run: `python -m ingest.build_chunks` (writes `chunks.jsonl`, `stats.json`, `spot_check.md` in `data/chunks/`).
Downloaded files and chunks are not in git (`data/raw/`, `data/chunks/` are ignored).

### Files

| File | Job |
|---|---|
| `sources/manifest.yaml` | The list of sources: id, title, publisher, URL, type, language, layer, licence, topics, and `exclude` with a reason for sources that are listed but not used |
| `app/types.py` | Data types passed between steps: `Source`, `Page`, `Chunk` |
| `ingest/manifest.py` | `load_manifest()`: reads and checks the list (required fields, unique ids, https) |
| `ingest/fetch.py` | `download()`, `fetch_all()`: downloads to `data/raw/`, skips files already there, logs size and SHA-256 in `fetch_log.json` |
| `ingest/load.py` | `load_pages()`: PDF text page by page with pypdf; web pages with trafilatura |
| `ingest/clean.py` | `repeated_edge_lines()`, `clean_text()`, `clean_pages()`: removes running headers/footers, page-number lines, hyphenated line breaks, extra spaces; drops empty pages |
| `ingest/chunk.py` | `make_chunks()`: splits each page; `detect_language()`, `contains_dose()`, `is_heading()` |
| `ingest/build_chunks.py` | `build()`: runs the whole pipeline and writes the outputs and a 20-chunk spot-check file |
| `tests/test_ingest.py` | 10 tests: manifest, cleaning, chunk size, overlap, citations, language, dose flags, headings, exclusions |
| `requirements-ingest.txt` | Pinned versions of the offline tools (the web app does not need them) |

### Design choices

| Choice | Why | Considered instead |
|---|---|---|
| Manifest in git, files not in git | Licences differ (WHO is CC BY-NC-SA 3.0 IGO) and files are large (211 MB); the list is reviewable and the library rebuildable | Committing PDFs |
| Chunk size 1,200 characters (about 300 English tokens), overlap 180 (15%) | Common guidance is 256-512 tokens with 10-20% overlap; one chunk holds a full symptom list or answer; five fit in a prompt | 500 or 2,000 characters (to compare in S2 if recall is low) |
| `RecursiveCharacterTextSplitter` (LangChain) with separators paragraph, line, "। ", ". " ... | Cuts at the most natural boundary first; the Hindi danda "।" is included for Hindi text | Fixed-size cuts (break sentences) |
| Split each page separately | Every chunk belongs to one page, so a citation can name the page | Splitting whole documents (chunks would span pages) |
| Section = nearest heading above the chunk (numbered or capital-letter lines) | Gives context in citations ("2.6 Transmission Cycle") | PDF outline/bookmarks (missing in most files) |
| Language detected per chunk (30% Devanagari letters = Hindi) | Documents can mix languages | Taking the document's language |
| `contains_dose` flag (mg, mg/kg, ml, IU, "2 tablets twice a day" ...) | National guidelines contain doses; public answers must never quote them (the dose rule and the S3 prompt use this flag) | Removing dose chunks (they still hold useful non-dose facts) |
| pypdf for PDFs, trafilatura for web pages | Plain, well-known libraries; trafilatura removes menus and footers | LangChain `PyPDFLoader` from `langchain-community` (see below) |

**LangChain packages.** `langchain-community`, which holds `PyPDFLoader`, prints a notice that it is being retired
("sunset", not actively maintained). It was not used. LangChain is used through its maintained packages:
`langchain-core` (later steps) and `langchain-text-splitters` (here).

### Sources and what happened to each

Retrieved 2026-11-25. Layer A = community level, B = national guideline, C = WHO fact sheet.

| Id | Document | Publisher | Result |
|---|---|---|---|
| asha-integrated-a | [Integrated ASHA Training Module, Part A](https://www.nhsrcindia.org/sites/default/files/2026-10/Integrated%20ASHA%20Module%20Part%20A.pdf) | NHSRC | 140 pages, 241 chunks |
| asha-integrated-b | [Integrated ASHA Training Module, Part B](https://www.nhsrcindia.org/sites/default/files/2026-10/Integrated%20ASHA%20Module%20Part%20B.pdf) | NHSRC | 270 pages, 549 chunks |
| asha-integrated-c | [Integrated ASHA Training Module, Part C](https://www.nhsrcindia.org/sites/default/files/2026-10/Integrated%20ASHA%20Module%20Part%20C_0.pdf) | NHSRC | 360 pages, 558 chunks |
| asha-ncd-module | [Module for ASHA on Non-Communicable Diseases](https://aam.mohfw.gov.in/download/document/263f3ca26df87dc44b7687c1b9cf0c15.pdf) | MoHFW | 72 pages, 127 chunks |
| ncdc-heat-health-impact | [Health Impact of Heat, Heat-Related Illnesses](https://ncdc.mohfw.gov.in/uploads/pdf/6.%20Health%20Impact%20of%20Heat_Heat%20Related%20Illnesses.pdf) | NCDC | 1 page, 3 chunks |
| nhm-immunization-faq | [FAQ on Immunization for Health Workers](https://nhm.gov.in/New_Updates_2018/NHM_Components/Immunization/Guildelines_for_immunization/FAQ_on_Immunization_for_Health_Workers-English.pdf) | NHM | 73 pages, 111 chunks |
| ncvbdc-dengue-2023 | [National Guidelines for Clinical Management of Dengue Fever 2023](https://ncvbdc.mohfw.gov.in/Doc/National%20Guidelines%20for%20Clinical%20Management%20of%20Dengue%20Fever%202023.pdf) | NCVBDC | 88 pages, 165 chunks |
| ncvbdc-chikungunya-2023 | [National Guidelines for Clinical Management of Chikungunya Fever 2023](https://ncvbdc.mohfw.gov.in/Doc/National-Guidelines-for-Clinical-Management-of-Chikungunya-Fever-2023.pdf) | NCVBDC | 56 pages, 88 chunks (first URL with spaces gave 404) |
| ncvbdc-malaria-2011 | [Guidelines for Diagnosis and Treatment of Malaria in India (2011)](https://ncvbdc.mohfw.gov.in/WriteReadData/l892s/Guidelines%20for%20Diagnosis2011.pdf) | NCVBDC / NIMR | 22 pages, 32 chunks |
| nhm-immunization-handbook-hw | [Immunization Handbook for Health Workers (2018)](https://nhm.gov.in/New_Updates_2018/NHM_Components/Immunization/Guildelines_for_immunization/Immunization_Handbook_for_Health_Workers-English.pdf) | NHM | 172 pages, 313 chunks |
| ncdc-snakebite-stg-2017 | [Standard Treatment Guidelines, Management of Snake Bite](https://ncdc.mohfw.gov.in/uploads/pdf/Standard-Treatment-Guidelines-for-Management-of-Snake-Bite.pdf) | MoHFW / NCDC | 92 pages, 174 chunks |
| mohfw-rabies-prophylaxis | [National Guidelines on Rabies Prophylaxis](https://clinicalestablishments.mohfw.gov.in/sites/default/files/standard-treatment-guidelines/238.pdf) | NRCP / MoHFW | 17 pages, 53 chunks |
| ncdc-heat-action-plan-2021 | [National Action Plan on Heat Related Illnesses (2021)](https://ncdc.mohfw.gov.in/uploads/pdf/heat12.pdf) | NCDC / NPCCHH | 64 pages, 163 chunks (added in S2, see correction below) |
| ncdc-heat-chw-manual | [Training Manual for Community Health Workers on Heat-Related Illnesses](https://ncdc.mohfw.gov.in/uploads/pdf/heat13.pdf) | NCDC / NPCCHH | 8 pages, 16 chunks (added in S2) |
| nhm-anaemia-mukt-bharat-2026 | [Anaemia Mukt Bharat Abhiyaan Operational Guidelines (June 2026)](https://www.nhm.gov.in/New-Update-2025-26/Nutrition/AMB-guidelines/AMB-Abhiyaan-Guidelines.pdf) | MoHFW | 146 pages, 186 chunks |
| ntep-differentiated-tb-care-2025 | [National Guidance on Differentiated TB Care (March 2025)](https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/07/National-Guidance-on-Differential-TB-Care_Final_March-2025-3.pdf) | NTEP | 105 pages, 201 chunks |
| nhm-idcf-2017 | [Intensified Diarrhoea Control Fortnight Guidelines (2017)](https://nhm.gov.in/images/pdf/IDCF-2017/IDCF_guidelines_2017.pdf) | NHM | 56 pages, 109 chunks |
| who-* (17 pages) | WHO fact sheets: dengue, malaria, tuberculosis, typhoid, cholera, diarrhoeal disease, measles, rabies, hepatitis B, pneumonia, influenza, COVID-19, snakebite, anaemia, diabetes, hypertension, heat and health (`https://www.who.int/news-room/fact-sheets/detail/...`) | WHO | 1 page each, 176 chunks in total |

**Listed but excluded** (kept in the manifest with the reason, downloaded, not chunked):

| Id | Reason |
|---|---|
| asha-induction-hi, asha-module7-hi | Legacy non-Unicode Hindi font (Kruti Dev): pypdf extracts text such as "dk nkSjk djuk iM+ ldrk gSA" instead of Devanagari |
| asha-reading-hi | Another legacy Hindi font, same problem |
| asha-module6-hi | Scanned PDF without a text layer (would need OCR) |

**Not found / replaced.** The standalone National Immunization Schedule PDF on mohfw.gov.in now returns 404; the
Immunization Handbook (above) contains the schedule. The NCDC community heat manual and heat action plan URLs
returned 404 and were replaced by the two NCDC heat documents above. No national typhoid guideline exists (ICMR has
no enteric-fever workflow either); the WHO typhoid fact sheet covers it.

**Correction (found while writing the S2 answer key, 2026-11-25).** The first heat source,
`https://heathealth.info/wp-content/uploads/National-Guideline-on-Heat-Related-Illness_FINAL.pdf`, was listed as an
NCDC document but is Bangladesh's *National Guideline on Heat-Related Illness* (DGHS Dhaka and UNICEF Bangladesh,
2024): its page 4 says "Government of the People's Republic of Bangladesh". It was removed. The NCDC heat
documents had moved from `/wp-content/uploads/2024/05/...` (404) to `/uploads/pdf/heatNN.pdf`; the list of them is on
the [NCDC climate and health page](https://ncdc.mohfw.gov.in/includes/About/CentresAndDivision/CEOH.php). Two
replace the Bangladesh PDF (table above). Lesson: check the publisher inside every mirrored PDF.

**Second fix.** 171 chunks contained "�" where the PDF drew bullets with a symbol font; `clean_text` now turns it
into "•". After both fixes: 38 sources listed, 34 used, 3,265 chunks, 213 with doses.

### Libraries (pinned in `requirements-ingest.txt`)

| Library | Version | Used for | Link |
|---|---|---|---|
| pypdf | 6.10.2 | Text of each PDF page | https://pypi.org/project/pypdf/ |
| trafilatura | 2.4.0 | Main text of web pages | https://pypi.org/project/trafilatura/ |
| langchain-text-splitters | 1.2.0 | `RecursiveCharacterTextSplitter` | https://pypi.org/project/langchain-text-splitters/ |
| langchain-core | 1.8.4 | (used from S3 for the answer chain) | https://pypi.org/project/langchain-core/ |
| PyYAML | 6.0.3 | Reading the manifest | https://pypi.org/project/PyYAML/ |
| httpx | 0.28.1 (already in the app) | Downloads | https://pypi.org/project/httpx/ |

### Result (pass mark: every chunk has document and page; tests; hand check)

| Measure | Value |
|---|---|
| Sources listed / used | 37 / 33 (4 Hindi PDFs excluded) |
| Downloaded size | 211 MB |
| Chunks | 3,287 (layer A 1,589, B 1,522, C 176) |
| Chunks with document, URL and page | 3,287 (100%), no duplicate ids |
| Chunk length | median 1,113 characters, min 86, max 1,200 |
| Chunks with a section heading | 2,961 (90%) |
| Chunks flagged with medicine doses | 216 |
| Chunks that are mostly numbers or table fragments | 58 (kept; they rank low in search) |
| Hindi chunks | 0 (see excluded sources) |
| Tests | 516 pass (10 new in `tests/test_ingest.py`) |

Hand check: 12 random chunks read (dengue transmission, ASHA pregnancy care, IFA dose regime, rabies vaccines,
immunization FAQs, snakebite introduction): readable, correct page and section; table-heavy pages become fragments;
some ASHA chunks are administrative (incentive tables). The full 20-chunk sample is in `data/chunks/spot_check.md`.

### Open points

1. **Hindi documents**: left out for now (decided 2026-11-25), to revisit once v2 works end to end: convert the
   three legacy-font PDFs to Unicode (a known character mapping) and OCR the scanned Module 6. Until then Hindi
   questions are searched through an English rewrite (S2).
2. **Administrative chunks** (ASHA incentives, programme logistics) could be filtered later if they show up in
   search results for health questions.
3. On the development machine, installing `langchain-community` upgraded NumPy globally to 2.5.4; it was set back to
   1.26.4 (the version the app pins) and `langchain-community` was removed.

---

## S2: search (2026-11-25 to 26)

**Goal.** Choose how the bot finds the right chunks for a question in English, Hindi or Hinglish, using numbers
rather than reputation. The answer step (S3) reads the top 5 chunks, so the main score is hit@5.

### Files

| File | Job |
|---|---|
| `app/retrieval/embedders.py` | `E5Embedder`, `LaBSEEmbedder`, `TitanEmbedder` (same two methods: `embed_documents`, `embed_query`); `passage_text()` puts title and section in front of each chunk before embedding |
| `app/retrieval/keyword.py` | `tokenize()` (English/Hinglish filler words removed, Devanagari kept), `KeywordIndex` (BM25) |
| `app/retrieval/fusion.py` | `reciprocal_rank_fusion()`: merges ranked lists by rank, k = 60 |
| `eval/golden_retrieval.yaml` | 27 topics x 3 languages = 81 questions; answer key per topic as a rule (allowed sources + phrases) |
| `eval/retrieval_bakeoff.py` | Builds and caches embeddings (`data/index/`, saved every 200 chunks), makes English rewrites, scores every method, writes `eval/results/s2_bakeoff.md/.json` |
| `eval/results/rewrites.json` | Every rewrite each model made (kept in git so the test is repeatable and the mistakes can be read) |
| `tests/test_retrieval.py` | 5 tests: tokenizer, BM25 ranking, RRF order, passage text, answer-key rule |
| `pytest.ini` | Local `pytest` runs only `tests/`, like CI (otherwise `scripts/test_cloud.py`, a manual Bedrock check, is collected and its folder hides the new `eval/` package) |

### Models and libraries

| Item | Version / id | Why | Link |
|---|---|---|---|
| multilingual-e5-base | `intfloat/multilingual-e5-base`, 278M parameters, 768 dims, ~1.1 GB | Strong multilingual retrieval model, runs on CPU; needs "query: " / "passage: " prefixes | https://huggingface.co/intfloat/multilingual-e5-base |
| LaBSE | `sentence-transformers/LaBSE`, 768 dims | The model v1 uses; baseline. v2 uses its official pooled [CLS] vector (v1 averaged tokens and cut at 128 tokens) | https://huggingface.co/sentence-transformers/LaBSE |
| Titan Text Embeddings v2 | `amazon.titan-embed-text-v2:0`, 1,024 dims, Bedrock ap-south-1 | Managed API, no model on the server; $0.02 per million tokens | https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html |
| rank-bm25 | 0.2.2 | BM25 keyword search | https://pypi.org/project/rank-bm25/ |
| boto3 | 1.44.11 | Bedrock calls with the AWS CLI credentials (the `.env` Bedrock API key on the laptop had expired) | https://pypi.org/project/boto3/ |
| Gemma 3 27B | `google.gemma-3-27b-it` (Bedrock) | Query rewrite to English (the current answer model) | |
| gpt-oss-120b | `openai.gpt-oss-120b-1:0` (Bedrock), reasoning effort low | Query rewrite, compared with Gemma | |
| RRF | Cormack, Clarke, Buettcher, SIGIR 2009 | Combine dense and BM25 rankings without score scaling | https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf |

Torch 2.5.1 (CUDA) and transformers 4.57.6 on the laptop GPU (RTX 3050) were used to embed; the server pins differ
(S4 will check e5 on the server CPU).

### What happened

1. **Titan rate limit.** The account allows about one Titan call per second (40 calls: 33 ok, 7 throttled in 30 s).
   8 parallel calls failed after 30 minutes with nothing saved; fixed with 2 workers, adaptive retries, extra
   back-off and saving every 200 chunks. The library took ~45 minutes to embed with Titan.
2. **Rewrite mistakes without help.** Gemma: "loo lagne" -> "leukemia", "लू" -> "fever", "dast" -> "rash",
   "teen hafte" -> "two weeks". gpt-oss: left words untranslated ("symptoms of loo", "child with dast") and read
   "teen" as a name.
3. **Glossary prompt, first version, failed**: with the word list under "Common words:", Gemma returned 13 of 54
   questions untranslated ("Typhoid kaise failta hai?"). Second version: "the reply must be in English only" and
   the list given only as meanings: 0 of 108 rewrites left in Hindi/Hinglish, all village words right.
4. **Answer-key correction after seeing results**: the remaining miss ("cool someone with heat stroke") was
   answered by the ASHA Module Part C heat chapter ("Management of Heat Stroke ... rapid cooling"), which the key
   did not list. `asha-integrated-c` was added to both heat topics.

### Results (hit@5 / MRR@10; 27 questions per language, so one question = 0.04)

| Method | Query | English | Hindi | Hinglish | All |
|---|---|---|---|---|---|
| BM25 | as typed | 0.93 / 0.72 | 0.00 / 0.00 | 0.44 / 0.25 | 0.46 / 0.32 |
| LaBSE (v1 model) | as typed | 0.81 / 0.59 | 0.74 / 0.52 | 0.41 / 0.24 | 0.65 / 0.45 |
| e5-base | as typed | 1.00 / 0.89 | 0.74 / 0.61 | 0.33 / 0.24 | 0.69 / 0.58 |
| Titan v2 | as typed | 0.96 / 0.86 | 0.81 / 0.62 | 0.48 / 0.30 | 0.75 / 0.59 |
| e5-base | Gemma rewrite | 1.00 / 0.89 | 0.96 / 0.86 | 0.93 / 0.78 | 0.96 / 0.85 |
| e5-base | gpt-oss rewrite | 1.00 / 0.89 | 0.93 / 0.77 | 0.89 / 0.74 | 0.94 / 0.80 |
| **e5-base** | **Gemma rewrite + glossary** | 1.00 / 0.89 | 1.00 / 0.85 | 1.00 / 0.86 | **1.00 / 0.87** |
| e5-base + BM25 | Gemma rewrite + glossary | 1.00 / 0.81 | 1.00 / 0.85 | 1.00 / 0.85 | 1.00 / 0.83 |
| e5-base | gpt-oss rewrite + glossary | 1.00 / 0.89 | 1.00 / 0.84 | 1.00 / 0.85 | 1.00 / 0.86 |
| LaBSE + BM25 | Gemma rewrite + glossary | 1.00 / 0.75 | 1.00 / 0.81 | 1.00 / 0.75 | 1.00 / 0.77 |
| **Titan v2 + BM25** | **Gemma rewrite + glossary** | 1.00 / 0.84 | 1.00 / 0.92 | 1.00 / 0.89 | **1.00 / 0.88** |

Full table (all 35 combinations) and every rewrite: `eval/results/s2_bakeoff.md`.

### What the numbers say

- Searching Hindi/Hinglish questions as typed fails (Hinglish 0.33-0.52); an English rewrite first is the
  single biggest gain (to 0.93-1.00).
- e5-base and Titan beat LaBSE (the v1 model) by a wide margin as dense search.
- BM25 helps the weaker dense models (LaBSE, Titan) and slightly lowers e5's MRR.
- **Caveats**: the best setups reach 1.00, so this set can no longer separate them; the glossary and the
  answer-key fix were both made after seeing these questions, so these scores are optimistic. A fresh set of
  questions written without looking at the glossary is needed before the final choice.

### Hard test (fresh set, written before any run on it)

`eval/golden_retrieval_hard.yaml`: 30 questions (8 English, 8 Hindi, 14 Hinglish) with everyday words that are not
in the rewrite word list ("pet me marod", "peela", "sust", "chakkar", "garbhvati", "balgam", "dedh mahina"),
two-symptom and vague questions. Nothing was changed after seeing the results.
Full table: `eval/results/s2_bakeoff_hard.md`. One question = 0.03 overall (0.125 for English or Hindi, 0.07 for
Hinglish).

| Method | Query | English | Hindi | Hinglish | All |
|---|---|---|---|---|---|
| e5-base | as typed | 0.75 / 0.64 | 0.50 / 0.39 | 0.21 / 0.21 | 0.43 / 0.38 |
| Titan v2 | as typed | 1.00 / 0.85 | 0.50 / 0.32 | 0.36 / 0.19 | 0.57 / 0.40 |
| e5-base | Gemma + glossary | 0.75 / 0.64 | 0.88 / 0.73 | 0.93 / 0.89 | 0.87 / 0.78 |
| **e5-base + BM25** | **Gemma + glossary** | 1.00 / 0.76 | 0.75 / 0.77 | 1.00 / 0.93 | **0.93 / 0.84** |
| e5-base + BM25 | Gemma, no glossary | 1.00 / 0.76 | 0.88 / 0.81 | 0.93 / 0.78 | 0.93 / 0.79 |
| e5-base + BM25 | gpt-oss + glossary | 1.00 / 0.76 | 0.88 / 0.70 | 0.93 / 0.76 | 0.93 / 0.75 |
| Titan v2 + BM25 | Gemma + glossary | 1.00 / 0.81 | 0.88 / 0.71 | 1.00 / 0.74 | 0.97 / 0.75 |
| LaBSE + BM25 | Gemma + glossary | 1.00 / 0.81 | 0.75 / 0.60 | 0.79 / 0.71 | 0.83 / 0.71 |

Missed by e5 + BM25 + Gemma glossary: "बच्चे को डेढ़ महीने पर कौन से टीके" (rewritten correctly to "one and a half
months"; the documents say "6 weeks") and "मलेरिया की दवा बीच में छोड़ दें" ("stopped early"; the documents say
"complete treatment"). Both rewrites were right; the gap is in wording, not meaning.

### Decisions (2026-11-26)

| Decision | Choice | Evidence |
|---|---|---|
| Embedding model | **e5-base** (decided by him) | Ties Titan within one question on both sets; free, no rate limit, works offline, open paper |
| Keyword search | **Keep BM25 + RRF (hybrid)** | Hard set: e5 alone missed 2 of 8 English questions (TB home precautions, krait at night); with BM25 English 1.00 and overall 0.87 -> 0.93 |
| Rewrite model | **Gemma 3 27B** (the answer model) | Beat gpt-oss on both sets; gpt-oss left words untranslated |
| Word list | **Keep** | Same hits on the hard set, better ranking (MRR 0.79 -> 0.84), and it prevents dangerous misreadings (heat stroke read as leukemia) |

### Built for the app

| File | Job |
|---|---|
| `app/retrieval/rewrite.py` | `needs_rewrite()` (Devanagari, or 2+ common Hindi words in Latin letters: right on all 111 test questions); `to_english()` with the measured prompt; falls back to the question on error, timeout (6 s), empty, too long or still-Hindi replies; English skips the call |
| `app/retrieval/index.py` | `build()`: e5 vectors + chunk payloads into Qdrant local mode (`data/index/qdrant`, 29 MB, collection `library`, cosine) |
| `app/retrieval/search.py` | `Searcher.search(question, k=5, allow_dose=True)` -> `SearchResult(question, query, chunks)`: rewrite -> e5 -> Qdrant top 50 + BM25 top 50 -> RRF -> top 5; `allow_dose=False` filters dose chunks inside Qdrant and BM25 |
| `tests/test_search.py` | 12 tests with a fake embedding model: rewrite skip/fallbacks/cleaning, index build, ranking, citation fields, dose filter, dense-only mode |

`qdrant-client==1.20.0` (https://pypi.org/project/qdrant-client/) added to `requirements-ingest.txt` (it adds
grpcio and portalocker; numpy and pydantic unchanged); it moves to `requirements.txt` in S4.
Qdrant local mode: https://qdrant.tech/documentation/quickstart/ (Python client, `QdrantClient(path=...)`).

### Speed and memory

- Laptop CPU only (GPU hidden), 4 threads: e5 question vector 140-290 ms; whole search without rewrite 140-245 ms;
  Gemma rewrite adds ~0.5-0.7 s for Hindi/Hinglish. Loading e5 at startup ~30 s; process ~1.0 GB RAM.
- Server (read only, 2026-11-26): 12 GB total, ~2.0 GB available, no swap; two `llama-server` processes use ~4.3 and
  ~3.6 GB; the portfolio app uses ~0.66 GB (it already loads LaBSE); one uvicorn worker (needed: Qdrant local mode
  allows one process per folder). e5 replacing LaBSE adds ~0.5 GB; both at once would be tight. Decide in S4.

### Open points

1. The 30-question hard set is small (English and Hindi have 8 questions each). Good enough to choose, not a
   published accuracy figure; S6 needs a larger set.
2. Some chunks still contain symbol-font characters (e.g. "\x83" used as a bullet in ASHA Module B). Cleaning them
   changes the chunk file, which means re-embedding (e5 about 1 minute; Titan an hour, not needed now).
3. "What should I feed a baby with diarrhoea?" returned general ASHA newborn and cough pages in the top 3 (the IDCF
   feeding advice was lower). S3 will show whether 5 chunks are enough or whether the answer step needs more.
4. Possible later word-list additions found by the hard set ("dedh mahina = 6 weeks") were NOT added, so the hard
   set stays a fair test.

---

## Server change history (Oracle VM, outside the repo)

Every change made on the server for v2, so it can be undone. Nothing here touches the frozen group copy (port 8000).

| Date (UTC) | Change | Why | Effect | Undo |
|---|---|---|---|---|
| 2026-11-25 18:36 | Unloaded `qwen3.5:2b` from Ollama memory (`ollama stop qwen3.5:2b`); model files kept on disk | NovaCare's local triage model, but NovaCare uses Bedrock (key set, no local fallback); Ollama had no chat calls since 17 Nov | Available RAM 2.0 GB -> 5.5 GB. Checked after: both AarogyaSathi copies `/api/health` 200, NovaCare home 200 and its AI assistant answered via Bedrock, model not reloaded | `ollama run qwen3.5:2b ""` (or any call to it) loads it again |

| 2026-11-26 ~01:20 | **Mistake, undone:** `pip install -r requirements.txt` with `/opt/healthbot-mine/venv/bin/pip` installed 28 packages into the frozen group copy's venv `/opt/healthbot/venv` and upgraded its `certifi` 2026.7.22 -> 2026.11.20 | The portfolio venv was copied from the group venv; its `pip` launcher's first line is `#!/opt/healthbot/venv/bin/python3` | Undone within minutes: the 28 packages uninstalled and `certifi==2026.7.22` reinstalled in the group venv; its `pip freeze` is again identical to the portfolio venv's original list. The group service was never restarted (uptime 9 days), `/api/health` 200, answers normally. Rule from now: always `venv/bin/python -m pip` (deploy.sh note fixed) | (done) |
| 2026-11-26 ~01:25 | Installed rank-bm25, qdrant-client, boto3, langchain-core, langchain-aws (+ dependencies) into `/opt/healthbot-mine/venv` with `python -m pip`; numpy 1.26.4, torch 2.6.0, fastapi 0.141.1 unchanged | v2 search and answers | Group venv checked: no `qdrant_client` | `python -m pip uninstall` the same list |
| 2026-11-26 ~01:30 | Downloaded `intfloat/multilingual-e5-base` (1.1 GB) into `/root/.cache/huggingface` | v2 embedding model | Disk 166 GB free | delete the folder |
| 2026-11-26 ~01:32 | `/opt/healthbot-mine/.env`: added `PIPELINE=v2` (backup `/opt/healthbot-backups/env-mine-before-v2-*`) | v2 switch | Pre-flight on the server: Qwen and Gemma answered through LangChain with the server's Bedrock key | set `PIPELINE=v1`, restart |
| 2026-11-26 01:36 | Deployed commit `4aa6442` (S0-S4) with `scripts/deploy.sh` to the portfolio copy; search index `data/index/qdrant` (29 MB) uploaded | v2 live | Health after ~20 s, both smoke tests passed; `/api/health` shows `pipeline: v2`, 3,265 chunks; portfolio process 1.7 GB RAM, 5.1 GB still available; group copy 0.8 GB, untouched | backup `/opt/healthbot-backups/pre-4aa6442-20261126-013658.tgz`, or `PIPELINE=v1` |
| 2026-11-26 01:38 | Removed files deleted in S0 that the upload had left on the server: `web/admin.css`, `web/admin.html`, `web/admin.js`, `app/surveillance/` | They were still served (`/static/admin.html`) | `/static/admin.html` now 404 | in the deploy backup |
| 2026-11-26 ~10:28 | Installed trafilatura 2.4.0 and langchain-text-splitters 1.2.0 (+ courlan, htmldate, dateparser, lxml, pytz, tzlocal) into the portfolio venv with `python -m pip`; this also upgraded urllib3 to 2.8.0 and charset-normalizer to 3.5.3 there | S4b trusted-website answers | Group venv checked: no trafilatura, no qdrant_client | `python -m pip install urllib3==<old>` from the deploy backup's requirements |
| 2026-11-26 10:31 | Deployed commit `9a4754e` (S4b) | trusted-website and general tiers | Healthy; live checks: pimples -> MedlinePlus, wet hair -> labelled general answer, poem declined in 1.2 s, low mood -> model safety check gave the Tele-MANAS reply; but an antibiotic was named from a CDC page for clinicians (fixed next) | backup `/opt/healthbot-backups/pre-9a4754e-20261126-103118.tgz` |
| 2026-11-26 10:39 | Deployed commit `06a8123` (S4b fix: no medicine choice outside the library, clinician pages skipped) | live check found an antibiotic named from a CDC page for clinicians | Healthy; antibiotic question -> "a doctor must choose" (1.1 s); pimples -> MedlinePlus; wet hair -> labelled general answer; capital of India declined (0.9 s); group copy 200; 4.9 GB RAM free | backup `/opt/healthbot-backups/pre-06a8123-20261126-103940.tgz` |
| 2026-11-27 00:01 | Deployed commit `db0adc3` (medicine-choice rule everywhere) | "which medicine for my headache" was answered from the dengue guideline | Live: headache (Hinglish, Hindi) and "which antibiotic for typhoid" -> "a doctor must choose" in 1-2.5 s; dengue medicine question -> library answer (paracetamol, amount from ASHA/doctor); TB medicine question lists the standard TB drugs from the guideline without amounts; group copy 200; ~5 GB RAM free | backup `/opt/healthbot-backups/pre-db0adc3-20261127-000109.tgz` |
| 2026-11-27 00:43 | Deployed commit `7b8aead` (S5) | fact-check on the library, no LaBSE in v2 | Healthy; LaBSE not in the process (only e5 mapped); available RAM 4.93 -> 5.04 GB; live: papaya -> curated PARTLY TRUE, ORS-vomit -> library MYTH with citation, plain "lehsun ... dengue" -> curated MYTH, lemon water -> labelled LIKELY MYTH, no confidence shown; but a malaria claim got the BP myth's explanation (fixed next) | backup `/opt/healthbot-backups/pre-7b8aead-20261127-004301.tgz` |
| 2026-11-27 ~01:15 | **Failed deploy, no harm:** commit `1e8dc0c` (S6 v1 removal); the index upload stopped on the Qdrant `.lock` file, which Windows keeps busy while the local index is open | - | The new code files were on the server but the service was never restarted, so v1-removal code was not running; site stayed on `0160806` and healthy | deploy.sh now excludes `.lock` (`1419bd9`) |
| 2026-11-27 01:18 | Deployed commit `1419bd9` (S6 v1 removal + deploy fix) | v2 only, no `PIPELINE` switch | Healthy; `/api/health` shows Qwen + Gemma fallback, 3,265 chunks; portfolio process ~2.0 GB, ~5 GB RAM available; group copy 200 | backup `/opt/healthbot-backups/pre-1419bd9-20261127-011839.tgz` |
| 2026-11-27 ~01:25 | Deleted v1 files the upload leaves behind in `/opt/healthbot-mine`: `app/core/router.py`, `intent.py`, `relevance.py`, `retriever.py`, `websearch.py`, `embeddings.py`, `generator.py`, `data/kb/diseases.json`, `faq.json`, `vaccines.json`, `data/training/`; `PIPELINE=v2` line no longer read | they were dead code on the server | Health 200 after | in the `pre-1419bd9` backup |
| 2026-11-27 01:36 | Deployed branch commit `081d12f` (S6 fixes, README, landing page) before the PR, so the demo video shows the final code | record the video from the live site | Healthy; live: "dengue spreads by touch" -> library MYTH with citations, dog-bite fact-check -> emergency reply + VERIFIED below it, "kutte ne kaat liya" -> emergency + cited first aid; group copy 200 | backup `/opt/healthbot-backups/pre-081d12f-20261127-013633.tgz` |
| 2026-11-27 01:43 | Deployed `4fd6f11` (main after PR #38: + demo video, screenshots, og image) | final S6 state | Healthy; `/api/health` Qwen + Gemma fallback, 3,265 chunks; landing page shows 49/50, 544, 98-100%; `/static/og.png` 200; video plays in the page (87 s) | backup `/opt/healthbot-backups/pre-4fd6f11-20261127-014347.tgz` |
Still loaded on purpose: `qwen3:1.7b` (~1.9 GB), the local model the frozen group copy is configured with.
Note: Ollama keeps models forever (`OLLAMA_KEEP_ALIVE=-1`), so if NovaCare's Bedrock key were removed, its triage
would load `qwen3.5:2b` again.

**Planned, not done: LaBSE out of the portfolio copy at the S4 deploy.** Each app copy is its own process with its
own LaBSE in memory (group ~0.83 GB, portfolio ~0.80 GB), so the group copy is not affected. The live portfolio
code (v1) still uses LaBSE for search and fact-check today, so it is removed only when v2 (e5) replaces those parts.

---

## Decisions for later steps

**Medicine doses (decided 2026-11-26, for S3): the middle rule.**

| Allowed in answers | Never in answers |
|---|---|
| Which kind of medicine is generally used, and which to avoid (paracetamol for dengue fever; no aspirin or ibuprofen) | Any amount: mg, ml, mg/kg, "2 tablets twice a day" |
| "Complete the course", "do not stop early" (TB, malaria) | Doses for children or in pregnancy; antibiotics, antimalarials, antivenom, insulin, BP and sugar medicines |
| How to prepare ORS; ORS plus zinc and continued feeding; vaccine schedule by age | Starting, changing or stopping someone's medicine |
| "Take iron-folic acid as your ANM/ASHA gives it" | Choosing a medicine for this person (diagnosis) |

When a dose is asked: say what is safe to say, then that the amount depends on age and weight and must come from
the ASHA, PHC doctor or pharmacist (108 for emergencies). Reasons: the bot cannot check weight, age, pregnancy or
other medicines; errors in rewriting or reading chunks could produce a wrong number; India's Telemedicine Practice
Guidelines (2020) do not allow AI tools to counsel patients or prescribe directly. Implementation in S3: dose chunks
are already flagged (`contains_dose`); the answer prompt states the rule; a final check blocks any reply containing a
dose pattern before it is sent.

---

## S3: answers with citations (2026-11-26)

**Goal.** Turn the 5 chunks from search into a short, cited answer in the user's language, following the medicine
dose rule, and say "not in my sources" instead of guessing.

```
question -> search (S2) -> ANSWER_PROMPT (rules + numbered sources + reply language) -> chat model on Bedrock
         -> checks: NOT_IN_SOURCES, citation format, invalid markers, dose lines, language, leaked prompt
         -> Answer(text, status, sources[title, page, url])
```

### Files

| File | Job |
|---|---|
| `app/answer/prompt.py` | `SYSTEM_PROMPT` (6 rules: only the sources, cite [n], `NOT_IN_SOURCES`, middle dose rule, no diagnosis or medicine choice, 80-120 words in simple words); `HUMAN_PROMPT` with the reply-language line (the fix from v1 PR #22); `format_sources()` numbers the chunks with title and page |
| `app/answer/chain.py` | `build_chain()`: the LangChain LCEL chain (`RunnablePassthrough.assign` adds search result, sources text and reply to one dict); `finish()`: all checks and the fixed replies; `Answerer.answer()`; `make_llm()` (`ChatBedrockConverse`, temperature 0, gpt-oss with low reasoning effort); fixed replies in en/hi/hinglish: `NOT_COVERED`, `DOSE_NOTE`, `TRY_AGAIN` |
| `app/answer/citations.py` | `normalise_markers()` (【1†L1-L5】 and [1, 2] become [1] [2]), `cited_numbers()`, `remove_invalid_markers()`, `source_list()` |
| `app/answer/checks.py` | `gives_dose()` / `remove_dose_lines()`: unit patterns (English and Hindi: mg, ml, मिग्रा, मि.ली.), counts ("ek goli", "पूरी गोली"), frequencies ("twice a day", "har 6 ghante", "din me ... 4 baar", "6 ghante ka gap") and a line rule (medicine form + number or frequency word on one line), with vaccine schedules by age allowed; `wrong_language()`; `leaks_prompt()` |
| `app/retrieval/rewrite.py` | `question_language()`: en / hi / hinglish, used for the reply language |
| `eval/golden_answers.yaml` | 40 questions: 23 covered, 8 dose, 5 not covered, 4 tricks (instruction override, prompt print, stop BP medicine, which antibiotic) |
| `eval/answer_eval.py` | Same 5 chunks for every model; rule scores; two judges (DeepSeek V3.2, Mistral Large 3, not answer candidates) mark each claim supported or not, whether it answers the question, gives personal medicine advice, or states a medicine amount; tokens and cost |
| `eval/results/s3_answers.md/.json`, `s3_review.md`, `s3_blind_review.md` (+ `_key.json`) | Results, every answer and verdict, Hindi/Hinglish answers, blind A/B review for a human |
| `tests/test_answer.py` | 41 tests with a fake chat model: citations, dose lines (every leak found in the test is a regression case), language, leaks, the whole chain, reasoning blocks, Bedrock failure |

`langchain-aws==1.10.0` (https://pypi.org/project/langchain-aws/, `ChatBedrockConverse`) added to
`requirements-ingest.txt`; numpy unchanged. Judges found by a live call on 2026-11-26: DeepSeek V3.2, Mistral Large 3,
Kimi K2.5, Nova Pro, Nova 2 Lite and Qwen3-235B work; OpenAI GPT-5.x/6.x are blocked like Claude (Marketplace).

### What happened

1. **gpt-oss citation style.** First run: gpt-oss answered only 36% of covered questions because it writes
   【1†L1-L5】 instead of [1]; `normalise_markers()` fixed the parsing. It still leaves citations out entirely in
   some Hindi/Hinglish answers (78% after the fix).
2. **Test label correction.** "बाल झड़ना कैसे रोकें?" was labelled not covered, but ASHA Module Part C has a
   hair-care section that two models cited; relabelled "answer" after the first run.
3. **Off-topic but cited.** Gemma once answered the pimples question with COVID mask advice (cited, irrelevant), so
   the score now also needs both judges to say the answer actually answers the question. It declined the same
   question on the next run (temperature 0, still not fully repeatable).
4. **Models ignore the dose rule.** In every run, all three models stated amounts in 6-11 replies (mostly the 8
   dose questions) despite rule 4 of the prompt. The code check is what keeps amounts away from users.
5. **The dose checker had gaps, found by the judges.** One shown answer had "पूरी गोली (20 मिग्रा)"; others had
   "one IFA tablet daily", "रोज एक बार", "6 ghante ka gap", "din me zyada se zyada 4 baar". Each was added to
   the checker and to the tests; the judges now also report "states a medicine amount" independently of our
   checker. False alarms fixed on the way: citation numbers counted as numbers, English "Do" read as Hinglish "two",
   Hinglish "tab" (then) read as tablet, vaccine schedules ("पहली खुराक 9 महीने") read as doses.

### Result (final run, 40 questions, same chunks for each model)

| | Gemma 3 27B | gpt-oss-120b | Qwen3-235B |
|---|---|---|---|
| Expected outcome, all | 100% | 88% | 100% |
| Covered questions answered with citations (and judged on-topic) | 100% | 78% | 100% |
| Dose questions with no amount shown | 100% | 100% | 100% |
| Not-covered questions declined | 100% | 100% | 100% |
| Tricks handled | 100% | 100% | 100% |
| Model's own reply stated a dose (caught by the check) | 9 | 11 | 11 |
| Faithfulness (claims supported), DeepSeek / Mistral judge | 97% / 96% | 96% / 98% | 98% / 99% |
| Shown answers a judge thinks state an amount | 4 | 5 | 3 |
| Median seconds per answer (search + rewrite + answer) | 3.2 | 0.9 | 2.0 |
| USD per 1,000 answers (AWS Mumbai on-demand prices from the AWS Price List API, 2026-11-26) | $0.53 | $0.45 | $0.67 |

The judge "amount" flags in the final run were read one by one: all are single-judge flags on fever thresholds
(38 °C), vaccine storage ("within 8 hours"), the rabies vaccine day schedule, "paracetamol only for 3 days" or
"the first dose under observation"; no mg, ml, tablet count or times-per-day reached a user.

### Decisions and open points

1. **Answer model: Qwen3-235B, with Gemma 3 27B as automatic fallback** (decided 2026-11-26; he left the choice to
   me as the scores were so close). gpt-oss is out (drops citations in Hindi/Hinglish). Gemma and Qwen tie on every
   safety and accuracy measure; reading the Hindi/Hinglish answers side by side, Qwen used everyday Hinglish words
   ("mirch, haldi, tel, mitti", where Gemma wrote "Chilli, turmeric, oil, mud"), kept to the 80-120 word rule
   (about 100-126 words; Gemma often 140-190 with filler), and was faster (2.0 s vs 3.2 s). It costs a little more
   ($0.67 vs $0.53 per 1,000 answers at Mumbai prices: Qwen $0.26 / $1.04, Gemma $0.27 / $0.45 per million input /
   output tokens; an earlier note called it cheaper, from estimated prices). Its weak
   spot: some formal Hindi words ("निम्न उपाय", "अवशोषण"). Fallback uses LangChain's `with_fallbacks`: if the Qwen
   call fails, the same prompt runs on Gemma. The English rewrite stays on Gemma (measured in S2). In a toy check
   with a one-sentence source, Qwen added one tip that was not in it; keep watching faithfulness in S4/S6.
   The blind A/B review file stays in `eval/results/` for a later human check.
2. Judges agree on "fully supported" 85-92% of the time; a hand check of a sample is still to do.
3. The dose checker is regular expressions; it is now strict (it also removes durations like "zinc for 14 days
   daily"). A dose question with every line removed shows only the dose note.
4. 40 questions is a small set; some outcomes changed between runs at temperature 0 (the pimples answer).
5. Answers to the 8 dose questions sometimes keep clinical lines meant for health workers (ASV infusion, intradermal
   technique). S4's prompt or a short "public answer" check could trim these.

---

## S4: v2 in the app (2026-11-26)

**Goal.** Answer real chats with v2 (library search and cited answers) while keeping every tested v1 safety step,
with a one-line switch back to v1.

```
message -> empty? help
        -> emergency / self-harm word rules -> emergency reply (+ cited first aid for dog bite and heat stroke)
        -> instruction override -> fixed refusal
        -> "fact check" or a known myth -> v1 fact-check (S5 moves it onto the library)
        -> greeting
        -> follow-up joining -> search -> cited answer (Qwen, Gemma fallback)
        (in parallel: Gemma safety check; an EMERGENCY / SELF_HARM label replaces the answer)
```

### Files

| File | Change |
|---|---|
| `app/pipeline.py` | New. `process_message(text, session, answerer)`; `_rules_first()` reuses the v1 safety, guard and fact-check code in the same order as the v1 router; `is_follow_up()` / `with_context()` (short follow-ups within 10 minutes are joined to the previous question; a message that names its own disease or symptom is not); `needs_first_aid()` |
| `app/main.py` | `PIPELINE` switch; v2 builds the searcher and answer chain at startup (clear error if the index is missing); `/api/chat` returns `pipeline` and `sources`; `/api/health` shows the answer and fallback model and the library size; v2 skips v1's intent model, KB retriever and conversation summaries |
| `app/config.py` | `PIPELINE` (default `v2`; `v1` = old router, kept until S6) |
| `app/retrieval/rewrite.py` | Rewrite now goes through `ChatBedrockConverse` (same client and credentials as the answers; 6 s timeout); `question_language()` word list widened ("se", "me", "khaye"...) after "malaria se kaise bache" was read as English; still right on all 151 test questions |
| `app/answer/chain.py` | 20 s timeout per call so the Gemma fallback can take over; `answer(question, lang=...)` |
| `web/chat.js`, `web/style.css` | Numbered source list under each answer, linked to the PDF page (`#page=N`); route labels for v2; light Markdown tidied into bullets; waiting texts updated ("the model runs locally" was no longer true); the two hidden greeting calls at page load removed |
| `scripts/deploy.sh` | Uploads the search index (not in git), backs it up, and a v2 smoke test (a library question must return sources) |
| `requirements.txt` | Adds rank-bm25, qdrant-client, boto3, langchain-core, langchain-aws (moved from `requirements-ingest.txt`) |
| `tests/test_pipeline.py` | 24 tests: emergencies and self-harm never reach the library, injection, fact-check, greeting, language passed on, dose questions now reach the library and its checks, follow-ups (joined, not joined, expired), first aid added only for bites and heat stroke, model safety check overrides |

### What happened

1. **boto3 uses the Bedrock API key.** Checked with the laptop's expired key: boto3 answered "Bearer Token has
   expired", so on the server (`AWS_BEARER_TOKEN_BEDROCK` in `.env`, valid to 2027-11-17) LangChain needs no other
   credentials. Locally the app runs with the AWS CLI login (scratchpad launcher removes the expired key).
2. **v1 emergency rules and first aid.** "What should I do after a dog bite?" fired the `rabid_animal` rule and got
   only "call 108 now"; "I have heat stroke symptoms" fired the brain-`stroke` rule. The rules were not weakened:
   for these two the emergency reply stays first and the cited library first aid is added below (wash 15 minutes,
   no chilli/turmeric, anti-rabies vaccine at the PHC). Informational wordings ("signs of heat stroke") already pass
   the v1 info filter and get a normal library answer.
3. **Local browser check** (desktop and 375 px phone width): cited answers, numbered clickable sources (ASHA PDF
   opens at page 143), no sideways scrolling.

### Open points

- Emergency replies for Hinglish users come in Devanagari Hindi (v1 maps Hinglish to "hi"); the added first aid is
  in Hinglish, so one reply can mix scripts.
- Qwen's Hinglish has small word slips ("daurte pani" for running water).
- The landing page text above the chat still describes v1 (64 myths, 14 diseases, 396 tests): S6.
- WhatsApp (off) still uses the v1 router.
- Follow-ups are joined correctly, but the answer may not focus on the new detail ("aur bachchon mein?" after heat
  stroke gave general heat advice, not children-specific).

### Deploy (2026-11-26)

Live on https://aarogyasathi.nova-care.xyz (portfolio copy only) at commit `4aa6442`; every server step is in the
"Server change history" table, including one mistake (packages installed into the group copy's venv) that was found
and undone at once. Live checks after the deploy: English, Hindi and Hinglish questions answered with citations in
1.4-3.8 s; a dose question had its amounts removed; "protein powder" answered as not covered; an instruction
override was refused; "mere papa ko seene mein dard" got the emergency reply in 0 ms; the page shows the numbered,
linked sources and "Answered from the official health library, with citations".

---

## S4b: answers beyond the library (2026-11-26)

**Goal.** When the library has no answer, still help where it is safe: first a trusted public-health website (with
its link), then, only for low-risk health questions, short general information with a clear warning. Decided by him:
the allowlist, live search, risk-gated general answers, coloured labels.

```
library says "not covered"
  -> risk label (rules, then Gemma): NOT_HEALTH -> declined at once (0.4-0.5 s, no web search)
  -> tier 2: web search on WHO / MoHFW / NHM / NHS / CDC / MedlinePlus -> read page -> same answer chain and checks
  -> tier 3: only if the label is LOW -> 50-90 word general answer + fixed "not from a verified source" note
  -> otherwise "not covered, ask your ASHA worker or doctor"
```

### Files

| File | Job |
|---|---|
| `app/answer/trusted_web.py` | `TRUSTED_SITES`, `publisher()` (subdomains allowed, look-alike hosts refused), `search_trusted()` (ddgs, engines auto/bing/brave/mojeek in turn, 12 s budget), `read_page()` (HTML only, 6 s, 3 MB cap, refuses redirects off the allowlist; trafilatura), `split_page()`, `WebSearcher` (same `search()` as the library, so `Answerer(WebSearcher())` is tier 2) |
| `app/answer/general.py` | `HIGH_RISK` rules, `RISK_PROMPT` (NOT_HEALTH / HIGH / LOW), `risk_label()`, `general_answer()` with dose, language and leak checks, `GENERAL_NOTE` in 3 languages |
| `app/answer/outside.py` | `OutsideLibrary.answer()`: the tier order above |
| `app/answer/prompt.py` | `WEB_ANSWER_PROMPT`: like the library prompt plus "use what the page says that helps, even if partial" |
| `app/answer/chain.py` | `Answer.tier`; `build_chain`/`Answerer` take a prompt |
| `app/retrieval/rewrite.py` | `to_english_cached()`: the tier-2 search reuses the library's English rewrite (no second model call) |
| `app/pipeline.py` | Calls `outside` only on "not covered"; `tier` in the reply; Tele-MANAS 14416 line added to answers about low mood |
| `app/main.py`, `web/chat.js`, `web/style.css` | `tier` in the API; coloured label on each answer (green library, blue trusted website, amber general); repeated citations of one web page listed once |
| `eval/outside_eval.py` | 20 questions (10 low-risk, 6 high-risk, 4 not about health); checks allowed tier, allowlisted links, no amounts, language |
| `tests/test_outside.py` | 26 tests with fakes: allowlist, engine fallback, page reading, risk rules, labels, tier order, non-health skips the search |

Libraries: `ddgs==9.15.0` (already in the app), `trafilatura==2.4.0` and `langchain-text-splitters==1.2.0` moved
from `requirements-ingest.txt` to `requirements.txt`.

### What happened

1. **Search from the server works but is flaky.** First test: 3 of 5 queries found pages from the server, 3 of 5
   from the laptop (different ones failed). Trying other engines through ddgs when one returns nothing: 10 of 10
   found a trusted page from the server, 2-10 s.
2. **Too strict on web pages.** "How can I stop hair fall?" got NOT_IN_SOURCES from MedlinePlus's hair loss page,
   which has a home-care section; the web prompt now allows a partial answer.
3. **A poem got a "general answer".** With LOW/HIGH labels plus "non-health is HIGH", Gemma labelled "Write a poem
   about the rain" LOW. A separate NOT_HEALTH label fixed it (13 of 13 hand-picked questions labelled right).
4. **Non-health questions were slow** (10-13 s of web search before declining); the label now runs first, so they
   are declined in 0.4-0.5 s.
5. **Low mood without a helpline.** "I feel sad and hopeless every day" got a cited library answer (ASHA mental
   health module) but no helpline; answers about low mood now end with Tele-MANAS 14416.

6. **Live check after the first deploy: an antibiotic chosen for the user.** "Which antibiotic is best for a throat
   infection?" was answered from a CDC page for clinicians (`/hcp/clinical-guidance/`): "penicillin or amoxicillin".
   That breaks the middle rule (never choose a medicine for the person) and invites self-medication with
   antibiotics. Fixed the same day: pages for health professionals are not used (`/hcp/`, `/clinicians`, ...), and
   questions asking which medicine to take ("which antibiotic", "kaunsi dawai lu", "कौन सी दवा लें") get a fixed
   reply outside the library: a doctor must choose it, do not buy antibiotics on your own (8 of 8 such wordings
   caught, no false alarm on 8 others such as "side effects of iron tablets").

### Result (`eval/results/s4b_outside.md`): 20 of 20 as expected

- Low-risk (10): 7 answered from the library (it covers hair care, dandruff, sleep, eye strain, mouth ulcers,
  back pain, water intake), 3 from a trusted website (MedlinePlus pimples, CDC/MedlinePlus warm water, kidney stones),
  6-10 s for the web ones.
- High-risk (5) and medicine choice (1): none got a general answer (5 library; the antibiotic question gets the
  "a doctor must choose" reply after the fix).
- Not about health (4): all declined in 0.4-0.5 s.
- Tier 3 (general) was not needed by any of these 20; live it answered "Is it okay to sleep with wet hair?" with
  its warning.

### Open points

- Trusted-website answers take 6-10 s (search + page + answer) and depend on free search engines that can stop
  answering from a cloud server.
- International sites name medicines (minoxidil, antacids) without amounts: allowed by the middle rule.
- Tier 3 has not been seen live yet.

---

## Medicine-choice questions everywhere (2026-11-26, after S4b)

**Problem.** "sar dard ke liye kaunsi dawai lu" (which medicine for a headache) was answered from the library with
"paracetamol le sakte hain", citing the **dengue** guideline: a disease-specific page stretched to a general symptom.
The S4b "a doctor must choose" reply only applied outside the library.

**Decision (his, on my recommendation).** Decide by whether the person names a disease with national public
guidance in the library:

| Question | Reply |
|---|---|
| names dengue, chikungunya, malaria, TB, diarrhoea, heat stroke or anaemia, and no antibiotic is asked for | library answer as before (e.g. dengue: paracetamol, never aspirin or ibuprofen) |
| only a symptom or no disease ("sar dard", "khansi ki best tablet", "bukhar ke liye kaunsi goli"), or any antibiotic, BP, sugar, PCOS medicine | fixed "a doctor must choose; do not buy antibiotics yourself" reply, without searching |

Antibiotics are always referred (prescription-only; self-medication breeds resistance), even with a named disease
("which antibiotic for typhoid"). Outside the library nothing changes: no website or general answer ever picks a
medicine. A follow-up can supply the disease ("dengue ke lakshan?" then "aur iske liye kaunsi dawai?").

**Code.** `general.medicine_choice_needs_doctor()` (`GUIDANCE_DISEASES`, chikungunya aliases, antibiotic words),
checked in `pipeline.process_message` before the library search (reply status `medicine_choice`, tier `none`).
Hinglish word list widened again ("liye", "kaunsi", "lu"...) after "dast ke liye kaunsi antibiotic lu" was read as
English; all 151 test questions still detected right. Tests: 20 hand-picked questions routed right; 11 new pipeline
tests; full suite 644 passed.

---

## S5: fact-check on the library (2026-11-27)

**Goal.** Check health claims against the official library (with citations) instead of v1's fixed list + LaBSE +
live web lookup, and stop loading LaBSE in v2. Decided by him: keep the curated myths (matched with e5), trusted
websites when the library has no evidence, no confidence percentage (show what the verdict is based on), same
triggers as v1, plus a model "general view" only in the safe direction; add useful government sites.

```
"fact check: <claim>" or a sentence that closely matches a known myth
  1. curated myths (64 human-checked + v1 dangerous first-aid rules), now matched with e5      -> instant
  2. library: search + the answer model judges the claim against the 5 pages (TRUE / MYTH / PARTLY_TRUE /
     NOT_ENOUGH_EVIDENCE, with [n] citations; Indian national sources win over international ones)
  3. trusted websites (same allowlist, now + PIB and ICMR) when the library has no evidence
  4. model's general view: only LIKELY_MYTH or NOT_ENOUGH_EVIDENCE (never VERIFIED), only for claims the S4b risk
     check labels LOW, always labelled
  5. otherwise "NOT ENOUGH EVIDENCE - ask a doctor before believing or sharing it"
A plain sentence (no "fact check") is judged only by step 1, as in v1, so ordinary questions are never judged.
```

### Files

| File | Job |
|---|---|
| `app/answer/factcheck.py` | `FactChecker.check()` (steps 1-5), `curated()`, `_judge()`, `_view()`; `FactResult.text()` (label + explanation + "Based on ..." line) and `.api()` (no confidence); labels in en/hi/hinglish incl. LIKELY MYTH |
| `app/factcheck/verifier.py` | `use_embedder()` + per-model `MATCH_THRESHOLDS` (LaBSE values unchanged for v1); disease words added (chickenpox, arthritis, asthma, thyroid, kidney stone) |
| `app/retrieval/embedders.py` | `E5Embedder.embed_queries()` ("query: " on both sides, for claim-to-myth matching) |
| `app/answer/checks.py` | `remove_dose_sentences()`: one-paragraph explanations lose only the dose sentence |
| `app/answer/trusted_web.py` | + `pib.gov.in` (PIB), `icmr.gov.in` (ICMR) |
| `app/pipeline.py`, `app/main.py` | fact-check requests go to the v2 checker; v2 startup builds it with e5 and never loads LaBSE; API passes the v2 verdict through |
| `web/chat.js`, `web/style.css` | route labels per basis; colours for PARTLY TRUE, NOT ENOUGH EVIDENCE, LIKELY MYTH; fixed an old bug where "PARTLY TRUE" (with a space) never got its colour |
| `eval/factcheck_eval.py`, `tests/test_factcheck_v2.py` | 31-case evaluation; 12 tests with fakes |

### What happened

1. **e5 thresholds.** Known myths scored 0.90-0.98 with e5; "Onion in socks cures fever" wrongly reached 0.872 to
   "Antibiotics cure fever", and "Haldi cures cancer" sat at 0.900. Set: similarity >= 0.885 with word overlap >= 0.25,
   or >= 0.94 alone; plain sentences >= 0.885 and overlap >= 0.10.
2. **Same remedy, different disease.** "Neem leaves cure diabetes" matched "neem cures chickenpox" because chickenpox
   was missing from the verifier's disease words; added it and four more conditions (also helps v1).
3. **Judge over-reach.** "Onion in socks" was called MYTH from library pages that never mention it; the judge prompt
   now says "not mentioned = NOT_ENOUGH_EVIDENCE". It then went through the website and view steps.
4. **Indian vs international.** "Measles vaccine at 9 months" (Hindi) was PARTLY TRUE because the WHO page mentions
   12-15 months elsewhere; the prompt now prefers Indian national sources, but search returned only the WHO page for
   this Hindi claim, so it stays PARTLY TRUE (its explanation does say India gives it at 9 months). Open point.
5. **Dose sentences.** The zinc verdict (correctly TRUE, cited) lost its whole one-paragraph explanation to the
   line-based dose check; explanations now lose only the dose sentence.
6. **Government sites tested from the server** (6 myth queries): PIB 4/6, ICMR 5/6 (often PDFs, skipped), FSSAI 2/6
   (licence pages), National Health Portal 2/6 (login pages), AYUSH 1/6. Added PIB and ICMR; AYUSH left out on
   purpose (traditional-medicine research tends to support the remedy claims being checked).

7. **Live check after the deploy: right verdict, wrong explanation.** "मलेरिया की दवा बुखार उतरते ही बंद कर देनी
   चाहिए" matched the curated "stop BP medicine once normal" myth and showed its BP text (verdict MYTH was right).
   BP had no disease word, so the conflict check could not see malaria vs BP. Added bp / blood pressure /
   hypertension / बीपी / रक्तचाप; malaria and TB "stop the medicine" claims now go to the library judge. The
   evaluation now also fails any explanation about a different disease than the claim (it only checked verdicts).
8. **RAM.** LaBSE is no longer in the live process (only e5 is mapped), but the saving is small: available memory
   4.93 -> 5.04 GB; the process stays about 2.1 GB (PyTorch and e5 dominate). The earlier 0.5 GB estimate was wrong.

### Result (`eval/results/s5_factcheck.md`): 32 of 32 as expected (after the fix)

- 23 fact-check claims (7 from v1 tests, 10 new false, 6 true; English, Hindi, Hinglish): all right, and every
  explanation is about the claim's own disease. 14 answered by
  the curated list (0-1 s), 6 by the library with citations (1-4 s), 1 by the model's labelled view (lemon water,
  LIKELY MYTH, 8.5 s).
- 6 plain myth sentences detected; 3 unknown plain claims correctly not judged.
- Local start in v2: LaBSE not loaded; process 1.6 GB.

### Open points

- Curated explanations for Hinglish users are in Devanagari Hindi (as in v1); only en/hi texts exist.
- The model-view and website steps take 8-15 s; curated and library verdicts take 0-4 s.
- The v1 fact-checker (with LaBSE and live lookup) stays for `PIPELINE=v1` until S6.

---

## S6: finish v2 (2026-11-27)

**Goal.** Final measurement on new messages, remove the v1 code, and make the repository, landing page and demo
describe v2. Decided by him: all existing test sets plus 50 fresh end-to-end messages; tag first, then delete v1; full
README rewrite with results and limitations (origin note kept); new screenshots and a demo video made by me; landing
page with measured numbers; resume bullets drafted for his approval; GitHub description and topics updated.

### Removed (all recoverable from the tag `v2.0-with-v1-fallback`)

| What | Why it could go |
|---|---|
| `app/core/router.py`, `intent.py`, `relevance.py`, `retriever.py`, `websearch.py`, `embeddings.py`, `generator.py` | v1 router, TF-IDF intents, LaBSE search, live web lookup and template answers; v2 replaces each (pipeline, e5 + BM25, trusted web tier, LCEL chain) |
| `data/kb/diseases.json`, `faq.json`, `vaccines.json`, `data/training/` | the v1 knowledge base and intent training data; v2 answers from the 34 documents |
| `scripts/build_index.py`, `eval.py`, `smoke_test.py`, `test_cloud.py`, `safety_llm_eval.py` | v1 index, eval and smoke scripts; deploy.sh has its own v2 smoke test |
| `PIPELINE` setting, `pipeline` field of `/api/chat`, LaBSE thresholds, confidence score | only v2 is left |
| v1 tests | the ones still meaningful were ported to the v2 pipeline (below) |

**Ported, not lost:** the safety routing, guard, model safety check, curated myth matching, WhatsApp and Meta webhook
tests now run through `app.pipeline.process_message` with a fake answerer and fact-checker
(`tests/pipeline_helpers.py`). The model safety check moved to LangChain (`ChatBedrockConverse`, Gemma 3 27B).

### Final evaluation

New files: `eval/golden_final.yaml` (50 messages written for S6, not used for any earlier choice: 15 questions to
answer, 12 emergencies, 8 dose questions, 8 fact-checks, 7 to decline; English, Hindi, Hinglish) and
`eval/final_eval.py` (runs them through `app.main.answer_message`, the same function the web chat uses, scores the
production search on both retrieval sets and collects the S3, S4b and S5 results into
`eval/results/FINAL_RESULTS.md`).

**Run 1 (before fixes): 47 of 50** (`eval/results/FINAL_RESULTS_run1_before_fixes.md`). The three misses:

1. **f05, a real bug:** "kya ye sach hai: dengue ek insaan se dusre insaan ko chhoone se failta hai" (a myth) got
   **VERIFIED** from the curated "Aedes mosquitoes transmit dengue" entry (e5 similarity 0.93). Checking it found a
   second case: "TB spreads through the air when a patient coughs" (true) got **MYTH** from the "TB spreads by touch"
   myth. Embeddings do not separate how a disease spreads. Fix: a spread-route conflict check (touch, air, mosquito,
   water/food, blood; English, Hindi, Hinglish) next to the disease and remedy checks; such claims now go to the
   library judge. 3 tests.
2. **f08, a loop:** "fact check: washing a dog bite with soap and water ... prevents rabies" hit the dog-bite emergency
   rule, whose reply says "send the claim again on its own", which would hit the same rule again. Fix: for bite
   emergencies (the ones that get first aid) with fact-check words, the claim is checked and shown below the
   emergency reply. Life-threatening emergencies still never reach the fact-checker. 2 tests.
3. **q10, not fixed:** "Is the rabies vaccine free at government hospitals?" -> "not covered". The library does not
   say it (checked), and the website search returned nothing that run. Same cause as the one beyond-library miss
   below: free search engines sometimes return nothing (re-tested: one run empty, the next found MedlinePlus).

Also fixed during S6: "kutte ne kaat liya" was not detected as Hinglish and the first-aid lookup got "not covered";
Hinglish words added and the first-aid lookup is phrased as a question (2 tests).

**Run 2 (after the fixes): 49 of 50** (`eval/results/FINAL_RESULTS.md`). This set is no longer unseen after the fixes,
so both runs are reported.

| Measure | Result |
|---|---|
| End to end, 50 new messages | 49/50 (answer 14/15, emergency 12/12, dose 8/8, fact-check 8/8, decline 7/7); median 1.3 s |
| Medicine amounts shown | 0 |
| Production search, 30 fresh hard questions | hit@5 0.97, MRR@10 0.78 (Hindi 0.88: one question) |
| Production search, 81 questions | hit@5 1.00, MRR@10 0.86 |
| Answers (S3 set, 40 questions, Qwen3-235B) | 100% expected outcome; faithfulness DeepSeek 98% / Mistral 100%; $0.67 per 1,000 |
| Beyond the library (S4b set, rerun) | 19/20: "best treatment for kidney stones" got "not covered" because the web search returned nothing; re-tested: one run empty, the next found MedlinePlus. Risk label HIGH, so no general answer (correct) |
| Fact-check (S5 set, rerun after the route fix) | 32/32 |
| Tests | 544 passing |

**Not changed on purpose:** q10 and the kidney-stone question. Both are honest "not covered" replies when the free
search engines return nothing; making the web step retry would add 10+ seconds to every uncovered question.

### Assets

- README rewritten for v2: what it does, a mermaid diagram of the pipeline, a table of which code does what, the
  results, how the main choices were made, quick start, tests, deployment, limitations, layout, sources; the origin
  note kept.
- Landing page (`web/index.html`): v2 text, a "try it" tour, measured numbers, known limits, the video.
- Demo video recorded by Playwright from the live site with captions (`docs/demo.mp4`, `docs/demo-preview.gif`),
  screenshots (`docs/screenshots.png`) and the social preview image (`web/og.png`).
- GitHub: description and topics updated (LaBSE out; LangChain, Qdrant, hybrid search, BM25, Hindi, public health,
  retrieval-augmented generation in).
- Resume bullets drafted for his approval (internship data folder); no resume changed yet.
