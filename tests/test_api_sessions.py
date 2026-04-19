"""Integration tests for the sessions API."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

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
    assert client.get("/api/sessions").json() == []


def test_session_create_empty(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"nickname": "Test"})
    assert r.status_code == 201
    d = r.json()
    assert d["nickname"] == "Test"
    assert d["lid"].startswith("DEDAL-")
    assert d["log_file"] == ""
    assert d["log_meta"] is None


def test_session_create_increments_lid(client: TestClient) -> None:
    r1 = client.post("/api/sessions", json={})
    r2 = client.post("/api/sessions", json={})
    assert r1.json()["lid"] < r2.json()["lid"]


def test_sessions_list_returns_desc(client: TestClient) -> None:
    client.post("/api/sessions", json={"nickname": "A"})
    client.post("/api/sessions", json={"nickname": "B"})
    items = client.get("/api/sessions").json()
    assert len(items) == 2
    # scan_sessions returns newest first
    dates = [i["created_at"] for i in items]
    assert dates == sorted(dates, reverse=True)


# ── import ────────────────────────────────────────────────────────────────


def test_session_import(client: TestClient) -> None:
    r = client.post(
        "/api/sessions/import?nickname=TestFlight",
        files={"file": ("LOG_017.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")},
    )
    assert r.status_code == 201
    d = r.json()
    assert d["lid"].startswith("DEDAL-")
    assert d["nickname"] == "TestFlight"
    assert d["log_file"] == "LOG_017.csv"
    assert d["log_meta"]["config_name"] == "TEST_CONFIG"
    assert d["log_meta"]["row_count"] == 2
    assert d["log_meta"]["duration_s"] == 2.0


def test_session_import_auto_lid(client: TestClient) -> None:
    r1 = client.post(
        "/api/sessions/import",
        files={"file": ("a.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")},
    )
    r2 = client.post(
        "/api/sessions/import",
        files={"file": ("b.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")},
    )
    assert r1.json()["lid"] != r2.json()["lid"]


# ── get ───────────────────────────────────────────────────────────────────


def test_session_get(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={"nickname": "x"}).json()["lid"]
    r = client.get(f"/api/sessions/{lid}")
    assert r.status_code == 200
    assert r.json()["nickname"] == "x"


def test_session_get_not_found(client: TestClient) -> None:
    assert client.get("/api/sessions/DEDAL-00000000-999").status_code == 404


# ── patch ─────────────────────────────────────────────────────────────────


def test_session_patch_nickname(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={"nickname": "old"}).json()["lid"]
    r = client.patch(f"/api/sessions/{lid}", json={"nickname": "new"})
    assert r.status_code == 200
    assert r.json()["nickname"] == "new"


def test_session_patch_tags(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    r = client.patch(f"/api/sessions/{lid}", json={"tags": ["hover", "windy"]})
    assert r.status_code == 200
    assert r.json()["tags"] == ["hover", "windy"]


def test_session_patch_not_found(client: TestClient) -> None:
    assert client.patch("/api/sessions/DEDAL-00000000-999",
                        json={"nickname": "x"}).status_code == 404


# ── delete ────────────────────────────────────────────────────────────────


def test_session_delete(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    assert client.delete(f"/api/sessions/{lid}").status_code == 204
    assert client.get(f"/api/sessions/{lid}").status_code == 404


def test_session_delete_not_found(client: TestClient) -> None:
    assert client.delete("/api/sessions/DEDAL-00000000-999").status_code == 404


# ── flight pack ───────────────────────────────────────────────────────────


_MINIMAL_PACK = {
    "version": 1,
    "exported_at": "2026-04-19T14:00:00Z",
    "lid": "",
    "meta": {"duration_s": 10.0, "max_alt_m": 5.0, "max_speed_ms": 3.0,
             "armed_s": 8.0, "total_dist_m": 20, "vbat_min_v": 22.1, "vbat_max_v": 24.8},
    "frames": [
        {"t_us": 1000000, "armed": 0, "fm": 0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
         "lat": 0.0, "lon": 0.0, "alt_m": 0.0, "spd_ms": 0.0, "sats": 0, "gps_ok": 0,
         "m1": 1000, "m3": 1000, "vbat": 24.0, "Vfwd": 0.0, "Vlat": 0.0, "Vz": 0.0, "Vh": 0.0},
    ],
}


def test_pack_not_found_session(client: TestClient) -> None:
    assert client.get("/api/sessions/DEDAL-00000000-999/pack").status_code == 404


def test_pack_not_yet_generated(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    assert client.get(f"/api/sessions/{lid}/pack").status_code == 404


def test_pack_put_and_get(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    pack = {**_MINIMAL_PACK, "lid": lid}
    r = client.put(f"/api/sessions/{lid}/pack", json=pack)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "frames": 1}
    got = client.get(f"/api/sessions/{lid}/pack").json()
    assert got["version"] == 1
    assert got["meta"]["duration_s"] == 10.0
    assert len(got["frames"]) == 1


def test_pack_put_not_found_session(client: TestClient) -> None:
    assert client.put("/api/sessions/DEDAL-00000000-999/pack",
                      json=_MINIMAL_PACK).status_code == 404


def test_pack_overwrites(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    client.put(f"/api/sessions/{lid}/pack", json={**_MINIMAL_PACK, "lid": lid})
    pack2 = {**_MINIMAL_PACK, "lid": lid,
             "frames": _MINIMAL_PACK["frames"] * 3}
    client.put(f"/api/sessions/{lid}/pack", json=pack2)
    assert len(client.get(f"/api/sessions/{lid}/pack").json()["frames"]) == 3
