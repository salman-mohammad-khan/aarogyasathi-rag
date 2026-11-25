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
- Files removed in S0 (admin page, surveillance) are still on the server until the deploy removes them by hand.
