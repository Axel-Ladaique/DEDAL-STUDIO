"""Unit tests for the Session model."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from dedal.session import (
    Session,
    _next_lid,
    _parse_log_meta,
    delete_session,
    get_session,
    list_sessions,
)

# ── _next_lid ─────────────────────────────────────────────────────────────


def test_next_lid_empty(tmp_path: Path) -> None:
    assert _next_lid(tmp_path, datetime(2026, 4, 19)) == "20260419-001"


def test_next_lid_increments(tmp_path: Path) -> None:
    (tmp_path / "20260419-001").mkdir()
    (tmp_path / "20260419-002").mkdir()
    assert _next_lid(tmp_path, datetime(2026, 4, 19)) == "20260419-003"


def test_next_lid_different_day_ignored(tmp_path: Path) -> None:
    (tmp_path / "20260418-005").mkdir()
    assert _next_lid(tmp_path, datetime(2026, 4, 19)) == "20260419-001"


def test_next_lid_nonexistent_root(tmp_path: Path) -> None:
    assert _next_lid(tmp_path / "doesnotexist", datetime(2026, 4, 19)) == "20260419-001"


# ── Session CRUD ──────────────────────────────────────────────────────────


def test_session_create_and_load(tmp_path: Path) -> None:
    s = Session.create(tmp_path, name="first flight")
    assert s.lid.endswith("-001")
    assert s.name == "first flight"
    assert s.log is None

    folder = tmp_path / s.lid
    assert folder.is_dir()
    assert (folder / "session.json").exists()

    loaded = Session.load(folder)
    assert loaded.lid == s.lid
    assert loaded.name == s.name
    assert loaded.created_at == s.created_at
    assert loaded.log is None


def test_session_save_roundtrip(tmp_path: Path) -> None:
    now = datetime(2026, 4, 19, 10, 30, 0)
    s = Session(lid="20260419-001", created_at=now, name="test", notes="n")
    s.save(tmp_path)
    loaded = Session.load(tmp_path / "20260419-001")
    assert loaded.to_dict() == s.to_dict()


def test_session_log_persisted(tmp_path: Path) -> None:
    s = Session.create(tmp_path)
    s.log = {"filename": "LOG_017.csv", "duration_s": 42.0, "row_count": 100,
             "config_name": "VTOL", "fw_version": "1.3"}
    s.save(tmp_path)
    loaded = Session.load(tmp_path / s.lid)
    assert loaded.log == s.log


# ── list / get ────────────────────────────────────────────────────────────


def test_list_sessions_empty(tmp_path: Path) -> None:
    assert list_sessions(tmp_path) == []


def test_list_sessions_missing_root(tmp_path: Path) -> None:
    assert list_sessions(tmp_path / "missing") == []


def test_list_sessions_sorted(tmp_path: Path) -> None:
    Session.create(tmp_path)
    Session.create(tmp_path)
    Session.create(tmp_path)
    sessions = list_sessions(tmp_path)
    assert len(sessions) == 3
    lids = [s.lid for s in sessions]
    assert lids == sorted(lids)


def test_list_sessions_skips_nojson(tmp_path: Path) -> None:
    (tmp_path / "not-a-session").mkdir()
    Session.create(tmp_path, name="real")
    assert len(list_sessions(tmp_path)) == 1


def test_get_session_found(tmp_path: Path) -> None:
    created = Session.create(tmp_path)
    found = get_session(tmp_path, created.lid)
    assert found is not None and found.lid == created.lid


def test_get_session_missing(tmp_path: Path) -> None:
    assert get_session(tmp_path, "20260419-999") is None


# ── delete ────────────────────────────────────────────────────────────────


def test_delete_session(tmp_path: Path) -> None:
    s = Session.create(tmp_path)
    assert (tmp_path / s.lid).is_dir()
    assert delete_session(tmp_path, s.lid) is True
    assert not (tmp_path / s.lid).exists()


def test_delete_session_not_found(tmp_path: Path) -> None:
    assert delete_session(tmp_path, "20260419-999") is False


# ── _parse_log_meta ───────────────────────────────────────────────────────

_CSV_CONTENT = """\
timestamp_us,dt_us,armed
# ========================================
# CONFIG_NAME = VTOL_CONFIG_v0.49
# FW_VERSION  = Beta 1.3
# ========================================
1000000,1000000,0
2000000,1000000,1
3500000,1500000,1
"""


def test_parse_log_meta(tmp_path: Path) -> None:
    f = tmp_path / "LOG_TEST.csv"
    f.write_text(_CSV_CONTENT, encoding="utf-8")
    meta = _parse_log_meta(f)
    assert meta["filename"] == "LOG_TEST.csv"
    assert meta["config_name"] == "VTOL_CONFIG_v0.49"
    assert meta["fw_version"] == "Beta 1.3"
    assert meta["row_count"] == 3
    assert meta["duration_s"] == 2.5


def test_parse_log_meta_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty.csv"
    f.write_text("timestamp_us,dt_us\n", encoding="utf-8")
    meta = _parse_log_meta(f)
    assert meta["row_count"] == 0
    assert meta["duration_s"] == 0.0
