"""Tests for the offline document pipeline (S1). No network: they use small made-up pages."""
from app.types import Page, Source
from ingest.chunk import CHUNK_CHARS, contains_dose, detect_language, is_heading, make_chunks
from ingest.clean import clean_pages, clean_text, repeated_edge_lines
from ingest.manifest import load_manifest

SOURCE = Source(id="test-doc", title="Test Guideline", publisher="MoHFW", url="https://example.gov.in/test.pdf",
                type="pdf", language="en", layer="B", licence="Government of India publication", topics=("dengue",))


# --- manifest -------------------------------------------------------------------------------------------------

def test_manifest_entries_are_complete_unique_and_https():
    sources = load_manifest()
    assert len(sources) >= 30
    assert len({s.id for s in sources}) == len(sources)
    assert all(s.url.startswith("https://") for s in sources)
    assert {s.layer for s in sources} == {"A", "B", "C"}
    assert any(s.language == "hi" for s in sources)


# --- clean ----------------------------------------------------------------------------------------------------

def test_repeated_header_and_footer_lines_are_found():
    pages = [Page("d", n, f"Module for ASHA\nreal text {n} about fever\nPage {n} of 9") for n in range(1, 10)]
    drop = repeated_edge_lines(pages)
    assert "module for asha" in drop
    assert "page # of #" in drop


def test_clean_text_rejoins_hyphenated_words_and_drops_page_numbers():
    text = "Give ORS and continue breast-\nfeeding the child.\n12\nSee a doctor."
    out = clean_text(text)
    assert "breastfeeding" in out
    assert "\n12\n" not in out


def test_clean_text_turns_broken_bullet_symbols_into_bullets():
    assert clean_text("� Keep water covered") == "• Keep water covered"


def test_clean_pages_drops_empty_pages_and_headers():
    bodies = ["Dengue causes high fever.", "Use bed nets at night.", "Give ORS for diarrhoea.",
              "TB needs six months of treatment.", "Wash hands with soap."]
    pages = [Page("d", n, f"NATIONAL GUIDELINES\n{body}\nThis line is different on page {chr(64 + n)} only.\n"
                          f"More detail for {body.split()[0]} here.\nAnd another line.\n{n}")
             for n, body in enumerate(bodies, 1)] + [Page("d", 6, "  ")]
    cleaned = clean_pages(pages)
    assert len(cleaned) == 5
    assert all("NATIONAL GUIDELINES" not in p.text for p in cleaned)


# --- chunk ----------------------------------------------------------------------------------------------------

def test_chunks_keep_citation_details_and_page_numbers():
    text = "3.1 Clinical features\n" + ("Dengue causes high fever, severe headache and pain behind the eyes. " * 40)
    chunks = make_chunks([Page("test-doc", 14, text)], SOURCE)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.page == 14 and c.source_id == "test-doc" and c.url == SOURCE.url and c.title == SOURCE.title
        assert len(c.text) <= CHUNK_CHARS
        assert c.id.startswith("test-doc#p14-c")
    assert chunks[0].section == "3.1 Clinical features"
    assert len({c.id for c in chunks}) == len(chunks)


def test_consecutive_chunks_overlap():
    text = " ".join(f"Sentence number {i} about malaria prevention with bed nets." for i in range(80))
    a, b = make_chunks([Page("test-doc", 1, text)], SOURCE)[:2]
    assert a.text[-60:].split()[-1] in b.text[:400]


def test_language_is_detected_per_chunk():
    assert detect_language("डेंगू में तेज़ बुखार, सिरदर्द और जोड़ों में दर्द होता है।") == "hi"
    assert detect_language("Dengue causes high fever and joint pain.") == "en"
    assert detect_language("ORS घोल बनाने के लिए एक लीटर साफ पानी लें") == "hi"


def test_dose_mentions_are_flagged():
    assert contains_dose("Paracetamol 15 mg/kg every 6 hours")
    assert contains_dose("Give 500 mg twice daily")
    assert contains_dose("2 tablets twice a day for 5 days")
    assert not contains_dose("Drink plenty of fluids and rest; see a doctor if fever lasts more than 2 days.")


def test_headings_are_recognised():
    assert is_heading("3.2 Management of severe dengue")
    assert is_heading("CLINICAL FEATURES")
    assert not is_heading("Dengue causes high fever.")
    assert not is_heading("12")


def test_excluded_sources_carry_a_reason_and_are_not_chunked():
    excluded = [s for s in load_manifest() if s.exclude]
    assert excluded, "the legacy-font Hindi PDFs are listed with a reason"
    assert all(len(s.exclude) > 10 for s in excluded)
