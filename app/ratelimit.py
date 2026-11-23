"""A small in-memory rate limit for the public chat API (one process, sliding one-minute window)."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app import config

_hits = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request):
    """The address of the caller. Behind Caddy the proxy appends the real address as the LAST X-Forwarded-For entry;
    earlier entries can be set by the client, so they are ignored."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def allow(key, limit, window=60.0, now=None):
    """True when `key` has sent fewer than `limit` messages in the last `window` seconds (and records this one)."""
    now = time.time() if now is None else now
    with _lock:
        q = _hits[key]
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def reset():
    with _lock:
        _hits.clear()


def rate_limit_chat(request: Request):
    limit = config.RATE_LIMIT_PER_MIN
    if limit <= 0:
        return
    if not allow(client_ip(request), limit):
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute and try again.")
