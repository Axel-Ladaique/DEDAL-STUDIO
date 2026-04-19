"""Integration tests for the sessions API."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from dedal.session import Session

_MINIMAL_CSV = (
    "timestamp_us,dt_us,armed\n"
    "# CONFIG_NAME = TEST_CONFIG\n"
    "# FW_VERSION  = 1.0\n"
    "1000000,1000000,0\n"
    "3000000,2000000,1\n"
)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── list / create ─────────────────────────────────────────────────────────


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
    assert data["log"] is None


def test_session_create_increments_lid(client: TestClient) -> None:
    r1 = client.post("/api/sessions", json={})
    r2 = client.post("/api/sessions", json={})
    assert r1.json()["lid"] < r2.json()["lid"]


def test_sessions_list_after_create(client: TestClient) -> None:
    client.post("/api/sessions", json={"name": "A"})
    client.post("/api/sessions", json={"name": "B"})
    items = client.get("/api/sessions").json()
    assert len(items) == 2
    assert items[0]["name"] == "A"
    assert items[1]["name"] == "B"


# ── get ───────────────────────────────────────────────────────────────────


def test_session_get(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={"name": "x"}).json()["lid"]
    r = client.get(f"/api/sessions/{lid}")
    assert r.status_code == 200
    assert r.json()["name"] == "x"


def test_session_get_not_found(client: TestClient) -> None:
    r = client.get("/api/sessions/00000000-999")
    assert r.status_code == 404


# ── patch ─────────────────────────────────────────────────────────────────


def test_session_patch_name(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={"name": "old"}).json()["lid"]
    r = client.patch(f"/api/sessions/{lid}", json={"name": "new"})
    assert r.status_code == 200
    assert r.json()["name"] == "new"


def test_session_patch_notes(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    r = client.patch(f"/api/sessions/{lid}", json={"notes": "great flight"})
    assert r.status_code == 200
    assert r.json()["notes"] == "great flight"


def test_session_patch_not_found(client: TestClient) -> None:
    r = client.patch("/api/sessions/00000000-999", json={"name": "x"})
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────


def test_session_delete(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    r = client.delete(f"/api/sessions/{lid}")
    assert r.status_code == 204
    assert client.get(f"/api/sessions/{lid}").status_code == 404


def test_session_delete_not_found(client: TestClient) -> None:
    r = client.delete("/api/sessions/00000000-999")
    assert r.status_code == 404


# ── import log ────────────────────────────────────────────────────────────


def test_session_import_log(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={"name": "log test"}).json()["lid"]
    r = client.post(
        f"/api/sessions/{lid}/log",
        files={"file": ("LOG_TEST.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["log"] is not None
    assert data["log"]["filename"] == "LOG_TEST.csv"
    assert data["log"]["config_name"] == "TEST_CONFIG"
    assert data["log"]["row_count"] == 2
    assert data["log"]["duration_s"] == 2.0


def test_session_import_log_not_found(client: TestClient) -> None:
    r = client.post(
        "/api/sessions/00000000-999/log",
        files={"file": ("x.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 404
