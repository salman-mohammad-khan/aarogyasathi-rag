"""Tier 2: when the library has no answer, search a short list of trusted public-health websites and answer from
the page found, with its link.

    English query (same rewrite as the library search)
      -> web search limited to the allowlist (ddgs; several engines tried, since one engine sometimes returns nothing)
      -> download the first readable page (trafilatura keeps the article text, drops menus and footers)
      -> cut into 1,200-character pieces, pick the 5 that best match the question (BM25)
      -> the SAME answer chain and checks as the library (citations, dose rule, language)

`WebSearcher` has the same `search()` as the library searcher, so `Answerer(WebSearcher())` is all tier 2 needs.
"""
import time
from urllib.parse import urlparse

import httpx

from app.retrieval.keyword import KeywordIndex
from app.retrieval.rewrite import to_english_cached
from app.retrieval.search import SearchResult

# Decided 2026-11-26: Indian government and WHO, plus three plain-language public health sites (UK NHS, US CDC,
# US National Library of Medicine). Private sites (Mayo Clinic, WebMD, Practo, blogs) are not used.
TRUSTED_SITES = {
    "who.int": "WHO",
    "mohfw.gov.in": "MoHFW",
    "nhm.gov.in": "NHM",
    "nhs.uk": "NHS (UK)",
    "cdc.gov": "CDC (US)",
    "medlineplus.gov": "MedlinePlus (US NLM)",
}
SEARCH_ENGINES = ("auto", "bing", "brave", "mojeek")  # tried in order until one returns a trusted page
SEARCH_BUDGET_S = 12
FETCH_TIMEOUT_S = 6
MAX_PAGE_BYTES = 3_000_000
MIN_PAGE_CHARS = 300
CHUNK_CHARS, CHUNK_OVERLAP, TOP_CHUNKS = 1200, 180, 5
USER_AGENT = "Mozilla/5.0 (compatible; AarogyaSathi health assistant; +https://aarogyasathi.nova-care.xyz)"


# Pages written for doctors and nurses (e.g. CDC "/hcp/" clinical guidance) give treatment choices meant for a
# clinician; the live S4b check answered "Which antibiotic is best for a throat infection?" from one. Not used.
_PROFESSIONAL_PATH = ("/hcp/", "/health-professionals", "/clinicians", "/clinical-guidance", "/professionals/")


def publisher(url: str) -> str | None:
    """The trusted publisher of a URL, or None if the site is not on the list (subdomains count: www.nhs.uk) or the
    page is written for health professionals."""
    parsed = urlparse(url)
    if any(p in parsed.path.lower() for p in _PROFESSIONAL_PATH):
        return None
    host = parsed.netloc.lower().split(":")[0]
    for domain, name in TRUSTED_SITES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def search_trusted(query: str, search=None) -> list[str]:
    """Links on trusted sites for the query, best first. `search(query, backend)` is the ddgs call (tests fake it)."""
    if search is None:
        from ddgs import DDGS

        def search(q, backend):
            return DDGS().text(q, region="in-en", max_results=8, backend=backend)

    site_filter = " (" + " OR ".join("site:" + d for d in TRUSTED_SITES) + ")"
    started = time.time()
    for backend in SEARCH_ENGINES:
        if time.time() - started > SEARCH_BUDGET_S:
            break
        try:
            links = [r["href"] for r in search(query + site_filter, backend) if publisher(r.get("href", ""))]
        except Exception:  # "No results found", rate limits, network: try the next engine
            continue
        if links:
            return list(dict.fromkeys(links))
    return []


def read_page(url: str, get=None) -> tuple[str, str]:
    """(title, main text) of an HTML page, or ("", "") if it cannot be read. PDFs and huge pages are skipped."""
    import trafilatura

    get = get or (lambda u: httpx.get(u, timeout=FETCH_TIMEOUT_S, follow_redirects=True,
                                      headers={"User-Agent": USER_AGENT}))
    try:
        response = get(url)
        if response.status_code != 200 or "html" not in response.headers.get("content-type", "") \
                or len(response.content) > MAX_PAGE_BYTES or not publisher(str(response.url)):
            return "", ""  # also refuses a redirect that leaves the trusted sites
        html = response.text
    except Exception:
        return "", ""
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    meta = trafilatura.extract_metadata(html)
    return ((meta.title if meta and meta.title else "") or url), text


def split_page(text: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_CHARS, chunk_overlap=CHUNK_OVERLAP,
                                              separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""])
    return [c for c in splitter.split_text(text) if len(c) >= 80]


class WebSearcher:
    """Same interface as the library `Searcher`: search(question) -> SearchResult with up to 5 chunks."""

    def __init__(self, rewrite=to_english_cached, search=None, get=None, pages_to_try: int = 3):
        self.rewrite, self.search_fn, self.get, self.pages_to_try = rewrite, search, get, pages_to_try

    def search(self, question: str, k: int = TOP_CHUNKS, allow_dose: bool = True) -> SearchResult:
        query = self.rewrite(question)
        for url in search_trusted(query, self.search_fn)[: self.pages_to_try]:
            title, text = read_page(url, self.get)
            if len(text) < MIN_PAGE_CHARS:
                continue
            pieces = split_page(text)
            if not pieces:
                continue
            scores = KeywordIndex(pieces).scores(query)
            ranked = sorted(range(len(pieces)), key=lambda i: -scores[i])[:k]
            chunks = [{"id": f"{url}#c{i}", "title": title, "publisher": publisher(url), "url": url, "page": None,
                       "section": "", "text": pieces[i], "contains_dose": False} for i in sorted(ranked)]
            return SearchResult(question=question, query=query, chunks=chunks)
        return SearchResult(question=question, query=query, chunks=[])
