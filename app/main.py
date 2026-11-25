import logging
import time

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
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


_started = False


@app.on_event("startup")
def startup():
    global _started
    if _started:
        return
    _started = True
    kb.load()
    intent.load()
    language._load()
    retriever._ensure_index()
    verifier._ensure_index()
    embeddings.get_model()


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
    return {
        "status": "ok",
        "models": "loaded",
        "llm": {
            "backend": generator.backend(),
            "model": generator.model_name(),
        },
        "languages": config.SUPPORTED_LANGUAGES,
    }


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_chat)])
def chat(req: ChatRequest):
    start = time.time()
    session = session_store.get_session(req.session_id)
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
    if factcheck is not None:
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
    )


@app.exception_handler(Exception)
def unhandled(request, exc):
    # The details go to the server log, never to the caller (they can contain paths, settings or secrets).
    logging.getLogger("aarogyasathi").exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Something went wrong. Please try again."})
