import logging
import time

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, pipeline
from app.ratelimit import rate_limit_chat
from app.core import embeddings, generator, intent, kb, language, retriever
from app.core import session as session_store
from app.core.router import process_message
from app.factcheck import verifier
from app.channels.whatsapp import whatsapp_router

app = FastAPI(title="AarogyaSathi - AI-Driven Public Health Chatbot", version="0.1.0")

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
    intent: str
    language: str
    latency_ms: int
    generator: str | None = None
    llm_backend: str | None = None
    flow: str | None = None
    factcheck: dict | None = None
    pipeline: str = "v1"
    sources: list[dict] = []  # v2: the documents and pages the answer cites
    tier: str | None = None  # v2: library | trusted_web | general | none


_started = False
_answerer = None  # v2: search index + answer chain, built once at startup
_outside = None  # v2 (S4b): trusted website and general-information tiers
_fact_checker = None  # v2 (S5): fact-check on curated myths, the library and trusted websites


def _build_answerer():
    """Open the Qdrant index and load e5 (about 30-60 s on the server CPU), then build the answer chain."""
    from app.answer.chain import Answerer
    from app.retrieval.index import INDEX_DIR
    from app.retrieval.search import Searcher

    if not INDEX_DIR.exists():
        raise RuntimeError(f"PIPELINE=v2 needs the search index at {INDEX_DIR}. Build it with "
                           "`python -m ingest.build_chunks` and `python -m app.retrieval.index`, or set PIPELINE=v1.")
    return Answerer(Searcher())


@app.on_event("startup")
def startup():
    global _started, _answerer, _outside, _fact_checker
    if _started:
        return
    _started = True
    kb.load()
    language._load()
    if config.PIPELINE == "v2":
        # v2 needs no LaBSE: search and the curated-myth match both use e5 (S5).
        _answerer = _build_answerer()
        from app.answer.chain import default_llm
        from app.answer.factcheck import FactChecker
        from app.answer.outside import OutsideLibrary, _gemma_ask
        from app.answer.trusted_web import WebSearcher

        _outside = OutsideLibrary()
        _fact_checker = FactChecker(_answerer.searcher, WebSearcher(), default_llm(), _gemma_ask(),
                                    _answerer.searcher.embedder.embed_queries)
        verifier._ensure_index()  # curated myths, embedded with e5
    else:
        verifier._ensure_index()  # v1: curated myths with LaBSE
        embeddings.get_model()
        intent.load()
        retriever._ensure_index()


def _update_summary(session):
    import threading

    def _run():
        try:
            summary = generator.summarize_conversation(session.get("history") or [])
            if summary:
                session.set("summary", summary)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


@app.get("/")
def index():
    return FileResponse(str(config.WEB_DIR / "index.html"))


@app.get("/api/health")
def health():
    generator.reset_availability()
    info = {
        "status": "ok",
        "models": "loaded",
        "pipeline": config.PIPELINE,
        "llm": {
            "backend": generator.backend(),
            "model": generator.model_name(),
        },
        "languages": config.SUPPORTED_LANGUAGES,
    }
    if config.PIPELINE == "v2":
        from app.answer.chain import ANSWER_MODEL_ID, FALLBACK_MODEL_ID

        info["llm"] = {"backend": "bedrock", "model": ANSWER_MODEL_ID, "fallback": FALLBACK_MODEL_ID}
        info["library_chunks"] = len(getattr(_answerer.searcher, "chunks", [])) if _answerer else 0
    return info


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
def chat(req: ChatRequest):
    start = time.time()
    session = session_store.get_session(req.session_id)
    if config.PIPELINE == "v2":
        result = pipeline.process_message(req.message, session, _answerer, _outside, _fact_checker)
    else:
        result = process_message(req.message, None, session)
        history = session.get("history") or []
        history.append({"role": "user", "text": req.message[:200]})
        history.append({"role": "bot", "text": result["text"][:300]})
        session.set("history", history[-12:])
        if len(history) >= 6 and (len(history) // 2) % 3 == 0:
            _update_summary(session)
    latency = int((time.time() - start) * 1000)
    meta = result.get("meta", {})
    factcheck = meta.get("factcheck")
    verdict = factcheck.get("verdict") if factcheck else None
    verdict_display = {
        "TRUE": "VERIFIED",
        "MYTH": "MYTH",
        "PARTLY_TRUE": "PARTLY TRUE",
        "UNVERIFIABLE": "UNVERIFIABLE",
    }.get(verdict, verdict)
    if factcheck is not None and "basis" in factcheck:
        pass  # v2 (S5): already in display form (verdict label, basis, source names; no confidence percentage)
    elif factcheck is not None:
        factcheck = {
            "verdict": verdict_display,
            "confidence": factcheck.get("confidence"),
            "fear_mongering": factcheck.get("fear_mongering"),
            "tags": factcheck.get("tags", []),
            "sources": [s["name"] for s in factcheck.get("sources", [])],
        }
    return ChatResponse(
        reply=result["text"],
        intent=meta.get("intent", "unknown"),
        language=meta.get("lang", "en"),
        latency_ms=latency,
        generator=meta.get("generator"),
        llm_backend=generator.last_backend(),
        flow=meta.get("flow"),
        factcheck=factcheck,
        pipeline=config.PIPELINE,
        sources=meta.get("sources") or [],
        tier=meta.get("tier"),
    )


@app.exception_handler(Exception)
def unhandled(request, exc):
    # The details go to the server log, never to the caller (they can contain paths, settings or secrets).
    logging.getLogger("aarogyasathi").exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Something went wrong. Please try again."})
