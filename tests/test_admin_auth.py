"""The WhatsApp test route needs ADMIN_TOKEN; the public chat API stays open; the removed v1 routes are gone."""
import pytest
from fastapi import HTTPException

from app import config
from app.admin_auth import require_admin
from app.channels.whatsapp import whatsapp_router
from app.main import app

PUBLIC = [("/api/chat", "POST"), ("/api/health", "GET"), ("/", "GET")]
REMOVED = ["/admin", "/api/stats", "/api/intents", "/api/surveillance/alerts", "/api/surveillance/run",
           "/api/surveillance/seed", "/api/surveillance/clear", "/webhook/twilio", "/webhook/whatsapp/twilio"]


def _walk(routes, prefix=""):
    # Newer FastAPI versions can keep included routers nested instead of flattening them.
    for route in routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            context = getattr(route, "include_context", None)
            yield from _walk(original.routes, prefix + (getattr(context, "prefix", "") or ""))
        elif hasattr(route, "dependant"):
            yield prefix + route.path, route


def _route(routes, path, method):
    for full, route in _walk(routes):
        if full == path and method in getattr(route, "methods", set()):
            return route
    raise AssertionError(f"route {method} {path} not found")


def _guards(route):
    return [dep.call for dep in route.dependant.dependencies]


def test_whatsapp_simulate_route_requires_the_admin_check():
    assert require_admin in _guards(_route(whatsapp_router.routes, "/simulate", "POST"))


@pytest.mark.parametrize("path,method", PUBLIC)
def test_public_routes_have_no_admin_check(path, method):
    assert require_admin not in _guards(_route(app.routes, path, method))


@pytest.mark.parametrize("path", REMOVED)
def test_removed_v1_routes_are_gone(path):
    assert all(full != path for full, _ in _walk(app.routes))


def test_whatsapp_webhook_is_off_by_default():
    assert config.WHATSAPP_ENABLED is False
    assert all(not full.startswith("/webhook/whatsapp") for full, _ in _walk(app.routes))


def test_disabled_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    with pytest.raises(HTTPException) as err:
        require_admin(authorization="Bearer anything", x_admin_token=None)
    assert err.value.status_code == 503


def test_missing_token_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "s3cret-value")
    with pytest.raises(HTTPException) as err:
        require_admin(authorization=None, x_admin_token=None)
    assert err.value.status_code == 401


@pytest.mark.parametrize("authorization,x_token", [
    ("Bearer wrong", None),
    ("Basic s3cret-value", None),
    ("bearer ", None),
    (None, "wrong"),
    ("Bearer s3cret-valu", None),
    ("Bearer s3cret-value-and-more", None),
])
def test_wrong_tokens_are_rejected(monkeypatch, authorization, x_token):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "s3cret-value")
    with pytest.raises(HTTPException) as err:
        require_admin(authorization=authorization, x_admin_token=x_token)
    assert err.value.status_code == 401


@pytest.mark.parametrize("authorization,x_token", [
    ("Bearer s3cret-value", None),
    ("bearer s3cret-value", None),
    (None, "s3cret-value"),
])
def test_correct_token_is_accepted(monkeypatch, authorization, x_token):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "s3cret-value")
    assert require_admin(authorization=authorization, x_admin_token=x_token) is None
