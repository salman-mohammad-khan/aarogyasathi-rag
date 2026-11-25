import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.channels.whatsapp import meta_webhook_verification, simulate_whatsapp_chat


def test_whatsapp_verification_success(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "synthetic-verify-token")
    resp = meta_webhook_verification(
        hub_mode="subscribe",
        hub_verify_token=config.WHATSAPP_VERIFY_TOKEN,
        hub_challenge="challenge_code_987654",
    )
    assert resp.status_code == 200
    assert resp.body.decode("utf-8") == "challenge_code_987654"


def test_whatsapp_verification_failure(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "synthetic-verify-token")
    resp = meta_webhook_verification(
        hub_mode="subscribe",
        hub_verify_token="wrong_secret_token",
        hub_challenge="challenge_code_987654",
    )
    assert resp.status_code == 403


def test_whatsapp_simulation_endpoint():
    req = {
        "from": "919876543210",
        "message": "What are dengue symptoms?",
    }
    data = simulate_whatsapp_chat(req)
    assert data["channel"] == "whatsapp"
    assert data["sender"] == "919876543210"
    assert "fever" in data["bot_reply"].lower()
    assert data["meta_graph_api_payload"]["to"] == "919876543210"
