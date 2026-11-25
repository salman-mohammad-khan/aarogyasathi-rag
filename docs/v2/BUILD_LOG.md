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
| ncdc-heat-guideline | [National Guideline on Heat-Related Illness](https://heathealth.info/wp-content/uploads/National-Guideline-on-Heat-Related-Illness_FINAL.pdf) | NCDC (copy on heathealth.info) | 86 pages, 201 chunks |
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

1. **Hindi documents**: decide whether to convert the two Kruti Dev PDFs to Unicode (a known character mapping)
   and OCR the scanned one, or rely on English documents with Hindi answers (the S2 English search rewrite).
2. **Administrative chunks** (ASHA incentives, programme logistics) could be filtered later if they show up in
   search results for health questions.
3. On the development machine, installing `langchain-community` upgraded NumPy globally to 2.5.4; it was set back to
   1.26.4 (the version the app pins) and `langchain-community` was removed.
