"""Unit tests for the Session model."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from dedal.session import Session, _next_lid, get_session, list_sessions


def test_next_lid_empty(tmp_path: Path) -> None:
    lid = _next_lid(tmp_path, datetime(2026, 4, 19))
    assert lid == "20260419-001"


def test_next_lid_increments(tmp_path: Path) -> None:
    (tmp_path / "20260419-001").mkdir()
    (tmp_path / "20260419-002").mkdir()
    lid = _next_lid(tmp_path, datetime(2026, 4, 19))
    assert lid == "20260419-003"


def test_next_lid_different_day_ignored(tmp_path: Path) -> None:
    (tmp_path / "20260418-005").mkdir()
    lid = _next_lid(tmp_path, datetime(2026, 4, 19))
    assert lid == "20260419-001"


def test_next_lid_nonexistent_root(tmp_path: Path) -> None:
    missing = tmp_path / "doesnotexist"
    lid = _next_lid(missing, datetime(2026, 4, 19))
    assert lid == "20260419-001"


def test_session_create_and_load(tmp_path: Path) -> None:
    s = Session.create(tmp_path, name="first flight")

    assert s.lid.endswith("-001")
    assert s.name == "first flight"

    folder = tmp_path / s.lid
    assert folder.is_dir()
    assert (folder / "session.json").exists()

    loaded = Session.load(folder)
    assert loaded.lid == s.lid
    assert loaded.name == s.name
    assert loaded.created_at == s.created_at


def test_session_save_roundtrip(tmp_path: Path) -> None:
    now = datetime(2026, 4, 19, 10, 30, 0)
    s = Session(lid="20260419-001", created_at=now, name="test", notes="n")
    s.save(tmp_path)

    loaded = Session.load(tmp_path / "20260419-001")
    assert loaded.to_dict() == s.to_dict()


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
    sessions = list_sessions(tmp_path)
    assert len(sessions) == 1


def test_get_session_found(tmp_path: Path) -> None:
    created = Session.create(tmp_path)
    found = get_session(tmp_path, created.lid)
    assert found is not None
    assert found.lid == created.lid


def test_get_session_missing(tmp_path: Path) -> None:
    assert get_session(tmp_path, "20260419-999") is None
