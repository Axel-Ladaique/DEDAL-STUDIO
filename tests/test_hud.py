"""Tests for dedal/hud/ — renderer, generator, and SSE endpoint."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dedal.hud.generator import generate_hud, load_pack
from dedal.hud.renderer import FlightFrame


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_pack(n_frames: int = 50, duration_us: int = 2_000_000) -> dict:
    """Minimal flight_pack with n_frames spread over duration_us."""
    step = duration_us // max(n_frames - 1, 1)
    frames = [
        {
            "t_us": i * step,
            "armed": 1 if i > 5 else 0,
            "fm": 0,
            "roll": 0.0, "pitch": 0.0, "yaw": float(i),
            "lat": 0.0, "lon": 0.0, "alt_m": float(i),
            "spd_ms": 0.0, "sats": 0, "gps_ok": 0,
            "m1": 1200, "m3": 1200,
            "vbat": 23.5,
            "Vfwd": 0.0, "Vlat": 0.0, "Vz": 0.0, "Vh": 0.0,
        }
        for i in range(n_frames)
    ]
    return {
        "version": 1,
        "exported_at": "2026-04-19T14:00:00Z",
        "lid": "DEDAL-20260419-001",
        "meta": {"duration_s": duration_us / 1e6},
        "frames": frames,
    }


@pytest.fixture()
def pack_file(tmp_path: Path) -> Path:
    p = tmp_path / "flight_pack.json"
    p.write_text(json.dumps(_make_pack()), encoding="utf-8")
    return p


# ── load_pack ─────────────────────────────────────────────────────────────


def test_load_pack_basic(pack_file: Path) -> None:
    frames = load_pack(pack_file)
    assert len(frames) == 50
    assert isinstance(frames[0], FlightFrame)
    assert frames[0].timestamp_us == 0
    assert frames[1].timestamp_us > 0
    assert frames[10].armed == 1


def test_load_pack_ekf_fields(pack_file: Path) -> None:
    frames = load_pack(pack_file)
    assert frames[0].Vfwd == 0.0
    assert frames[0].Vlat == 0.0
    assert frames[0].Vz   == 0.0
    assert frames[0].Vh   == 0.0


def test_load_pack_empty(tmp_path: Path) -> None:
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"version": 1, "frames": []}), encoding="utf-8")
    assert load_pack(p) == []


def test_load_pack_null_fields(tmp_path: Path) -> None:
    """Null values (JSON null = None) must not raise TypeError in load_pack."""
    pack = {
        "version": 1,
        "frames": [{
            "t_us": 1000,
            "armed": None, "fm": None,
            "roll": None, "pitch": None, "yaw": None,
            "lat": None, "lon": None, "alt_m": None,
            "spd_ms": None, "sats": None, "gps_ok": None,
            "m1": None, "m3": None, "vbat": None,
            "Vfwd": None, "Vlat": None, "Vz": None, "Vh": None,
        }],
    }
    p = tmp_path / "pack_nulls.json"
    p.write_text(json.dumps(pack), encoding="utf-8")
    frames = load_pack(p)
    assert len(frames) == 1
    assert frames[0].timestamp_us == 1000
    assert frames[0].roll_deg == 0.0
    assert frames[0].pitch_deg == 0.0
    assert frames[0].flight_mode == 0
    assert frames[0].accel_z == 1.0  # default non-nul


# ── generate_hud ──────────────────────────────────────────────────────────


def test_generate_hud_creates_pngs(tmp_path: Path, pack_file: Path) -> None:
    out = tmp_path / "hud_out"
    n = generate_hud(pack_file, out, fps=25, width=320, height=180)
    assert n > 0
    pngs = sorted(out.glob("frame_*.png"))
    assert len(pngs) == n
    assert pngs[0].name == "frame_000000.png"


def test_generate_hud_purges_existing(tmp_path: Path, pack_file: Path) -> None:
    out = tmp_path / "hud_out"
    out.mkdir()
    (out / "stale_frame.png").write_bytes(b"x")
    generate_hud(pack_file, out, fps=25, width=320, height=180)
    assert not (out / "stale_frame.png").exists()


def test_generate_hud_progress_cb(tmp_path: Path, pack_file: Path) -> None:
    calls: list[tuple[int, int]] = []
    generate_hud(pack_file, tmp_path / "out", fps=25, width=320, height=180,
                 progress_cb=lambda c, t: calls.append((c, t)))
    assert calls, "progress_cb was never called"
    assert calls[-1][0] == calls[-1][1], "last call must be current==total"


def test_generate_hud_empty_pack_raises(tmp_path: Path) -> None:
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"version": 1, "frames": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no frames"):
        generate_hud(p, tmp_path / "out")


# ── SSE endpoint ──────────────────────────────────────────────────────────


def _full_pack_json(lid: str, n_frames: int = 50) -> dict:
    return {**_make_pack(n_frames), "lid": lid}


def test_hud_endpoint_no_pack(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    r = client.post(f"/api/sessions/{lid}/hud", json={})
    assert r.status_code == 400
    assert "flight_pack" in r.json()["error"]


def test_hud_endpoint_not_found(client: TestClient) -> None:
    r = client.post("/api/sessions/DEDAL-00000000-999/hud", json={})
    assert r.status_code == 404


def test_hud_endpoint_sse(client: TestClient) -> None:
    lid = client.post("/api/sessions", json={}).json()["lid"]
    client.put(f"/api/sessions/{lid}/pack", json=_full_pack_json(lid))

    with client.stream(
        "POST", f"/api/sessions/{lid}/hud",
        json={"fps": 25, "width": 320, "height": 180},
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        events = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    statuses = [e["status"] for e in events]
    assert "started" in statuses
    assert statuses[-1] in ("done", "error"), f"unexpected last status: {statuses}"
    if statuses[-1] == "done":
        assert events[-1]["frames"] > 0
