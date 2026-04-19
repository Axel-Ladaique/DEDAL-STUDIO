"""Integration tests for the sessions API."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from dedal.session import Session


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_sessions_list_empty(client: TestClient) -> None:
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_session_create(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"name": "my flight"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "my flight"
    assert data["lid"].endswith("-001")
    assert "created_at" in data


def test_session_create_increments_lid(client: TestClient) -> None:
    r1 = client.post("/api/sessions", json={})
    r2 = client.post("/api/sessions", json={})
    assert r1.status_code == 201
    assert r2.status_code == 201
    lid1 = r1.json()["lid"]
    lid2 = r2.json()["lid"]
    assert lid1 != lid2
    assert lid1 < lid2


def test_sessions_list_after_create(client: TestClient) -> None:
    client.post("/api/sessions", json={"name": "A"})
    client.post("/api/sessions", json={"name": "B"})
    r = client.get("/api/sessions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["name"] == "A"
    assert items[1]["name"] == "B"


def test_session_get(client: TestClient) -> None:
    created = client.post("/api/sessions", json={"name": "x"}).json()
    lid = created["lid"]

    r = client.get(f"/api/sessions/{lid}")
    assert r.status_code == 200
    assert r.json()["lid"] == lid
    assert r.json()["name"] == "x"


def test_session_get_not_found(client: TestClient) -> None:
    r = client.get("/api/sessions/00000000-999")
    assert r.status_code == 404
    assert "not found" in r.json()["error"]
