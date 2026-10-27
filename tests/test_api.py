"""
Tests for the HTTP API's rules (Phase 8d) - no LLM, no graph run.

FastAPI's TestClient calls the app in-process, like a fake browser.
"""

import pytest
from fastapi.testclient import TestClient

import api

KEY = "test-key"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(api, "API_KEY", KEY)
    return TestClient(api.app)


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_key_is_rejected(client):
    assert client.get("/jobs").status_code == 401


def test_wrong_key_is_rejected(client):
    assert client.get("/jobs", headers={"X-API-Key": "nope"}).status_code == 401


def test_unknown_run_is_404(client):
    r = client.get("/runs/does-not-exist", headers={"X-API-Key": KEY})
    assert r.status_code == 404


def test_invalid_decision_value_is_rejected(client):
    # Pydantic validates incoming JSON: only approve / edit / reject allowed.
    r = client.post("/runs/x/decision", json={"decision": "maybe"},
                    headers={"X-API-Key": KEY})
    assert r.status_code == 422


def test_decision_only_when_awaiting_approval(client, monkeypatch):
    # The HTTP version of the approval guardrail: you can't "approve" a run
    # that isn't paused at the review step.
    monkeypatch.setattr(api, "run_status", lambda tid: {"thread_id": tid, "status": "running"})
    r = client.post("/runs/x/decision", json={"decision": "approve"},
                    headers={"X-API-Key": KEY})
    assert r.status_code == 409
