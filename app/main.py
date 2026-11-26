"""AarogyaSathi web app (FastAPI): the chat page, /api/chat and /api/health.

At startup it opens the search index and loads e5 (app/retrieval), builds the answer chain (app/answer/chain.py), the
beyond-the-library tiers (app/answer/outside.py) and the fact-checker (app/answer/factcheck.py). Each chat message
goes through app/pipeline.py.
"""
import logging
import time

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, pipeline
from app.channels.whatsapp import whatsapp_router
from app.core import kb, language
from app.core import session as session_store
from app.factcheck import verifier
from app.ratelimit import rate_limit_chat

app = FastAPI(title="AarogyaSathi - multilingual public-health assistant", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/static", StaticFiles(directory=str(config.WEB_DIR)), name="static")
# WhatsApp (Meta Cloud API) is optional and off unless WHATSAPP_ENABLED=true.
if config.WHATSAPP_ENABLED:
    app.include_router(whatsapp_router, prefix="/webhook/whatsapp", tags=["whatsapp"])


class ChatRequest(BaseModel):
    message: str = Field(max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    reply: str
    intent: str  # library_answer | fact_check | emergency | guard | greeting | help
    language: str  # en | hi | hinglish (other codes for emergency replies in other Indian languages)
    latency_ms: int
    generator: str | None = None
    flow: str | None = None  # answered, not_covered, dose_removed, medicine_choice, curated, library, ...
    factcheck: dict | None = None  # verdict, basis, source names (no confidence percentage)
    sources: list[dict] = []  # the documents and pages the answer cites
    tier: str | None = None  # library | trusted_web | general | none


_started = False
_answerer = None  # search index + answer chain
_outside = None  # trusted-website and general-information tiers
_fact_checker = None  # curated myths, the library and trusted websites


def startup_objects():
    """Build everything once (also used by the WhatsApp channel). About 20-60 s, mostly loading e5."""
    global _started, _answerer, _outside, _fact_checker
    if _started:
        return _answerer, _outside, _fact_checker
    from app.answer.chain import Answerer, default_llm
    from app.answer.factcheck import FactChecker
    from app.answer.outside import OutsideLibrary, _gemma_ask
    from app.answer.trusted_web import WebSearcher
    from app.retrieval.index import INDEX_DIR
    from app.retrieval.search import Searcher

    if not INDEX_DIR.exists():
        raise RuntimeError(f"The search index is missing at {INDEX_DIR}. Build it with `python -m ingest.build_chunks` "
                           "and `python -m app.retrieval.index`.")
    kb.load()
    language._load()
    _answerer = Answerer(Searcher())
    _outside = OutsideLibrary()
    _fact_checker = FactChecker(_answerer.searcher, WebSearcher(), default_llm(), _gemma_ask(),
                                _answerer.searcher.embedder.embed_queries)
    verifier._ensure_index()  # the curated myths, embedded with e5
    _started = True
    return _answerer, _outside, _fact_checker


@app.on_event("startup")
def startup():
    startup_objects()


def answer_message(text: str, session) -> dict:
    """One message through the pipeline (web chat and WhatsApp)."""
    answerer, outside, fact_checker = startup_objects()
    return pipeline.process_message(text, session, answerer, outside, fact_checker)


@app.get("/")
def index():
    return FileResponse(str(config.WEB_DIR / "index.html"))


@app.get("/api/health")
def health():
    from app.answer.chain import ANSWER_MODEL_ID, FALLBACK_MODEL_ID

    return {
        "status": "ok",
        "llm": {"backend": "bedrock", "model": ANSWER_MODEL_ID, "fallback": FALLBACK_MODEL_ID},
        "library_chunks": len(getattr(_answerer.searcher, "chunks", [])) if _answerer else 0,
        "languages": ["en", "hi", "hinglish"],
    }


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
def chat(req: ChatRequest):
    start = time.time()
    session = session_store.get_session(req.session_id)
    result = answer_message(req.message, session)
    meta = result.get("meta", {})
    return ChatResponse(
        reply=result["text"],
        intent=meta.get("intent", "unknown"),
        language=meta.get("lang", "en"),
        latency_ms=int((time.time() - start) * 1000),
        generator=meta.get("generator"),
        flow=meta.get("flow"),
        factcheck=meta.get("factcheck"),
        sources=meta.get("sources") or [],
        tier=meta.get("tier"),
    )


@app.exception_handler(Exception)
def unhandled(request, exc):
    # The details go to the server log, never to the caller (they can contain paths, settings or secrets).
    logging.getLogger("aarogyasathi").exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Something went wrong. Please try again."})
