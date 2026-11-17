"""Tests for the Amazon Bedrock tier in app/core/generator.py. No network: httpx.post is replaced."""
import pytest

from app.core import generator

KEY = "test-key-123"
OK_BODY = {"output": {"message": {"content": [{"text": " Hello from the model. "}]}}}


class FakeResp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = OK_BODY if body is None else body

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", KEY)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setattr(generator, "_availability", None)
    monkeypatch.setattr(generator, "_bedrock_failures", 0)
    monkeypatch.setattr(generator, "_bedrock_cooldown_until", 0.0)
    monkeypatch.setattr(generator, "_last_backend", None)
    monkeypatch.setattr(generator, "BEDROCK_FALLBACK", "templates")
    # Ollama must never be reached unless a test opts in.
    monkeypatch.setattr(generator, "_local_ok", lambda: False)


def fake_post(monkeypatch, responses):
    """Replace httpx.post; `responses` is a list of FakeResp or Exceptions, used in order. Returns the call log."""
    calls = []
    queue = list(responses)

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        item = queue.pop(0) if queue else FakeResp(500)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(generator.httpx, "post", post)
    return calls


def test_request_shape_and_text(monkeypatch):
    calls = fake_post(monkeypatch, [FakeResp()])
    out = generator.generate("SYSTEM TEXT", "USER TEXT")
    assert out == "Hello from the model."
    assert generator.last_backend() == "bedrock"
    call = calls[0]
    assert call["url"] == "https://bedrock-runtime.ap-south-1.amazonaws.com/model/google.gemma-3-27b-it/converse"
    assert call["headers"]["Authorization"] == "Bearer " + KEY
    assert call["json"]["system"] == [{"text": "SYSTEM TEXT"}]
    assert call["json"]["messages"] == [{"role": "user", "content": [{"text": "USER TEXT"}]}]
    assert call["json"]["inferenceConfig"]["maxTokens"] == generator.BEDROCK_MAX_TOKENS
    assert call["timeout"] == generator.BEDROCK_TIMEOUT_S


def test_key_with_bom_or_newline_is_cleaned(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "﻿" + KEY + "\r\n")
    calls = fake_post(monkeypatch, [FakeResp()])
    assert generator.generate("s", "u") == "Hello from the model."
    assert calls[0]["headers"]["Authorization"] == "Bearer " + KEY
    calls[0]["headers"]["Authorization"].encode("ascii")  # must be a valid HTTP header value


def test_model_id_with_colon_is_url_encoded(monkeypatch):
    monkeypatch.setattr(generator, "BEDROCK_MODEL_ID", "qwen.qwen3-32b-v1:0")
    calls = fake_post(monkeypatch, [FakeResp()])
    generator.generate("s", "u")
    assert calls[0]["url"].endswith("/model/qwen.qwen3-32b-v1%3A0/converse")


def test_reply_blocks_without_text_are_joined_safely(monkeypatch):
    body = {"output": {"message": {"content": [{"reasoningContent": {"x": 1}}, {"text": "Answer."}]}}}
    fake_post(monkeypatch, [FakeResp(body=body)])
    assert generator.generate("s", "u") == "Answer."


def test_http_error_returns_none_and_never_calls_ollama(monkeypatch):
    fake_post(monkeypatch, [FakeResp(status=403)])
    monkeypatch.setattr(generator, "_post", lambda *a, **k: pytest.fail("local Ollama was called"))
    assert generator.generate("s", "u") is None
    assert generator.last_backend() is None


def test_timeout_exception_returns_none(monkeypatch):
    fake_post(monkeypatch, [generator.httpx.ReadTimeout("slow")])
    assert generator.generate("s", "u") is None


def test_three_failures_in_a_row_pause_bedrock_then_it_resumes(monkeypatch):
    calls = fake_post(monkeypatch, [FakeResp(500)] * 3 + [FakeResp()])
    for _ in range(3):
        assert generator.generate("s", "u") is None
    assert len(calls) == 3
    # cooldown active: the fourth call does not reach the network
    assert generator.generate("s", "u") is None
    assert len(calls) == 3
    # cooldown over
    monkeypatch.setattr(generator, "_bedrock_cooldown_until", 0.0)
    assert generator.generate("s", "u") == "Hello from the model."
    assert len(calls) == 4


def test_one_slow_call_does_not_pause_bedrock(monkeypatch):
    calls = fake_post(monkeypatch, [FakeResp(500), FakeResp(500), FakeResp(), FakeResp(500), FakeResp(500), FakeResp()])
    results = [generator.generate("s", "u") for _ in range(6)]
    assert [r is not None for r in results] == [False, False, True, False, False, True]
    assert len(calls) == 6


def test_fallback_local_uses_ollama_after_a_bedrock_failure(monkeypatch):
    monkeypatch.setattr(generator, "BEDROCK_FALLBACK", "local")
    monkeypatch.setattr(generator, "_local_ok", lambda: True)
    monkeypatch.setattr(generator, "_post", lambda *a, **k: "local answer")
    fake_post(monkeypatch, [FakeResp(500)])
    assert generator.generate("s", "u") == "local answer"
    assert generator.last_backend() == "local"


def test_without_a_key_bedrock_is_never_called(monkeypatch):
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK")
    monkeypatch.setattr(generator.httpx, "post", lambda *a, **k: pytest.fail("network was called"))
    assert generator.bedrock_configured() is False
    assert generator.generate("s", "u") is None


def test_api_key_is_never_logged(monkeypatch, caplog):
    fake_post(monkeypatch, [FakeResp(status=403)])
    with caplog.at_level("DEBUG"):
        generator.generate("s", "u")
    assert KEY not in caplog.text
    assert "Bedrock call failed" in caplog.text


def test_empty_reply_is_not_counted_as_a_failure(monkeypatch):
    body = {"output": {"message": {"content": [{"text": "   "}]}}}
    fake_post(monkeypatch, [FakeResp(body=body)] * 4)
    for _ in range(4):
        assert generator.generate("s", "u") is None
    assert generator._bedrock_failures == 0
    assert generator._bedrock_cooldown_until == 0.0


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Here's the analysis in Hindi, following all the rules:\n\nआपको बुखार है।", "आपको बुखार है।"),
        ("Here's my response:\n\nक्या आपको उल्टी है?", "क्या आपको उल्टी है?"),
        ("Here is the answer:\nDrink ORS.", "Drink ORS."),
        ("How many days?\n\n(Translation: For how many days?)", "How many days?"),
        ("How many days?\n\n**(Roughly translates to: how long?)**", "How many days?"),
        # normal lead-ins and ordinary text must be left alone
        ("Here are the symptoms:\n- fever\n- rash", "Here are the symptoms:\n- fever\n- rash"),
        ("Drink plenty of fluids (water, ORS).", "Drink plenty of fluids (water, ORS)."),
    ],
)
def test_strip_meta_removes_chatter_only(raw, expected):
    assert generator._strip_meta(raw) == expected


def test_bedrock_reply_is_cleaned_and_empty_after_cleaning_is_none(monkeypatch):
    body = {"output": {"message": {"content": [{"text": "Here's my response:\n\nOnly this."}]}}}
    fake_post(monkeypatch, [FakeResp(body=body)])
    assert generator.generate("s", "u") == "Only this."
    body = {"output": {"message": {"content": [{"text": "(Translation: nothing else)"}]}}}
    fake_post(monkeypatch, [FakeResp(body=body)])
    assert generator.generate("s", "u") is None


def test_symptom_prompts_do_not_push_the_model_into_hindi():
    for prompt in (generator.PROBE_SYSTEM_PROMPT, generator.SYMPTOM_ANALYSIS_SYSTEM_PROMPT):
        assert "second language" in prompt
        assert "English" in prompt


def test_backend_and_model_name_report_bedrock():
    assert generator.backend() == "bedrock"
    assert generator.model_name() == generator.BEDROCK_MODEL_ID
