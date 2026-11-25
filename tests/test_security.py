"""Small security fixes: CORS, rate limit, pincode validation, generic errors, safe admin page."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, ratelimit
from app.main import ChatRequest, app, unhandled

ROOT = Path(__file__).resolve().parent.parent


def test_cors_is_not_open_to_every_origin():
    assert "*" not in config.CORS_ORIGINS
    cors = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"][0]
    assert "*" not in cors.kwargs["allow_origins"]


def test_rate_limit_blocks_the_31st_message_in_a_minute_and_recovers():
    ratelimit.reset()
    for i in range(30):
        assert ratelimit.allow("1.2.3.4", 30, now=1000.0 + i)
    assert not ratelimit.allow("1.2.3.4", 30, now=1040.0)
    assert ratelimit.allow("5.6.7.8", 30, now=1040.0)  # another caller is unaffected
    assert ratelimit.allow("1.2.3.4", 30, now=1061.0)  # the window has moved on
    ratelimit.reset()


class _Req:
    def __init__(self, headers, host="9.9.9.9"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_client_ip_uses_the_proxy_entry_not_a_value_the_client_can_set():
    assert ratelimit.client_ip(_Req({"x-forwarded-for": "6.6.6.6, 203.0.113.5"})) == "203.0.113.5"
    assert ratelimit.client_ip(_Req({})) == "9.9.9.9"


def test_chat_route_is_rate_limited_and_limit_raises_429(monkeypatch):
    route = [r for r in app.routes if getattr(r, "path", None) == "/api/chat" and "POST" in r.methods][0]
    assert ratelimit.rate_limit_chat in [d.call for d in route.dependant.dependencies]
    ratelimit.reset()
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 2)
    req = _Req({})
    ratelimit.rate_limit_chat(req)
    ratelimit.rate_limit_chat(req)
    with pytest.raises(HTTPException) as e:
        ratelimit.rate_limit_chat(req)
    assert e.value.status_code == 429
    ratelimit.reset()


@pytest.mark.parametrize("bad", ["<img src=x onerror=alert(1)>", "12345", "1100011", "abc123", "110 001", ""])
def test_bad_pincode_is_dropped_not_stored(bad):
    assert ChatRequest(message="hi", pincode=bad).pincode is None


def test_good_pincode_is_kept():
    assert ChatRequest(message="hi", pincode="110001").pincode == "110001"
    assert ChatRequest(message="hi").pincode is None


def test_message_length_is_limited():
    with pytest.raises(Exception):
        ChatRequest(message="x" * 2001)


def test_server_errors_do_not_leak_details():
    resp = unhandled(None, RuntimeError("secret path C:/app/.env token=abc"))
    body = resp.body.decode()
    assert resp.status_code == 500
    assert "secret" not in body and ".env" not in body and "token" not in body


def test_admin_page_builds_cells_with_text_not_html():
    js = (ROOT / "web" / "admin.js").read_text(encoding="utf-8")
    assert "textContent" in js
    assert "tr.innerHTML" not in js
