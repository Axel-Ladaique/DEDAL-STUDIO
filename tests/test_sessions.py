"""Unit tests for the sessions model (step 2)."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest

from dedal.sessions import (
    Session,
    _parse_gps_utc_ref,
    _parse_log_meta,
    _resolve_timezone,
    create_empty_session,
    delete_session,
    generate_lid,
    get_session,
    import_log,
    load_session,
    parse_meta_file,
    reload_meta,
    save_session,
    scan_sessions,
)

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


def _write_csv(path: Path, content: str = _CSV_CONTENT) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ── generate_lid ──────────────────────────────────────────────────────────


def test_generate_lid_format(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path / "log.csv")
    lid = generate_lid(csv, tmp_path / "flights")
    assert lid.startswith("DEDAL-")
    parts = lid.split("-")
    assert len(parts) == 3
    assert parts[2] == "001"


def test_generate_lid_increments(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    csv = _write_csv(tmp_path / "log.csv")
    lid1 = generate_lid(csv, flights)
    # Simulate the first session folder existing
    from dedal.sessions import _lid_to_folder
    (flights / _lid_to_folder(lid1)).mkdir(parents=True)
    lid2 = generate_lid(csv, flights)
    assert lid1 != lid2
    assert int(lid2.split("-")[2]) == int(lid1.split("-")[2]) + 1


# ── import_log ────────────────────────────────────────────────────────────


def test_import_log_copies_not_moves(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "LOG_017.csv")
    import_log(source, flights, nickname="test")
    assert source.exists(), "source CSV must not be moved"


def test_import_log_creates_folder_and_json(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "log.csv")
    s = import_log(source, flights)
    assert s.dir_path.is_dir()
    assert (s.dir_path / "session.json").exists()
    assert (s.dir_path / "log.csv").exists()


def test_import_log_sets_log_meta(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "log.csv")
    s = import_log(source, flights)
    assert s.log_meta is not None
    assert s.log_meta["config_name"] == "VTOL_CONFIG_v0.49"
    assert s.log_meta["fw_version"] == "Beta 1.3"
    assert s.log_meta["row_count"] == 3
    assert s.log_meta["duration_s"] == 2.5


def test_import_log_lid_format(tmp_path: Path) -> None:
    source = _write_csv(tmp_path / "log.csv")
    s = import_log(source, tmp_path / "flights")
    assert s.lid.startswith("DEDAL-")


# ── save / load roundtrip ─────────────────────────────────────────────────


def test_save_load_roundtrip(tmp_path: Path) -> None:
    from datetime import datetime
    folder = tmp_path / "flight_20260419_001"
    folder.mkdir()
    s = Session(
        lid="DEDAL-20260419-001",
        nickname="Alpha",
        created_at=datetime(2026, 4, 19, 14, 0, 0),
        dir_path=folder,
        log_file="log.csv",
        tags=["hover", "windy"],
        location={"lat": 48.8566, "lon": 2.3522, "place_name": "Paris"},
        log_meta={"row_count": 42, "duration_s": 10.0},
    )
    save_session(s)

    loaded = load_session(folder)
    assert loaded.lid == s.lid
    assert loaded.nickname == s.nickname
    assert loaded.created_at == s.created_at
    assert loaded.tags == s.tags
    assert loaded.location == s.location
    assert loaded.log_meta == s.log_meta


def test_save_is_atomic(tmp_path: Path) -> None:
    """Atomic write leaves no .tmp on success."""
    from datetime import datetime
    folder = tmp_path / "flight_20260419_001"
    folder.mkdir()
    s = Session(lid="DEDAL-20260419-001", nickname="",
                created_at=datetime(2026, 4, 19), dir_path=folder)
    save_session(s)
    assert not list(folder.glob("*.tmp"))


# ── scan_sessions ─────────────────────────────────────────────────────────


def test_scan_sessions_orders_desc(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    csv = _write_csv(tmp_path / "log.csv")
    s1 = import_log(csv, flights, nickname="first")
    time.sleep(0.01)
    s2 = import_log(csv, flights, nickname="second")
    time.sleep(0.01)
    s3 = import_log(csv, flights, nickname="third")

    sessions = scan_sessions(flights)
    assert len(sessions) == 3
    dates = [s.created_at for s in sessions]
    assert dates == sorted(dates, reverse=True)


def test_scan_sessions_ignores_broken(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    flights.mkdir()
    # Valid session
    csv = _write_csv(tmp_path / "log.csv")
    import_log(csv, flights, nickname="real")
    # Broken folder (has session.json with invalid JSON)
    broken = flights / "flight_20260419_999"
    broken.mkdir()
    (broken / "session.json").write_text("NOT JSON", encoding="utf-8")

    sessions = scan_sessions(flights)
    assert len(sessions) == 1
    assert sessions[0].nickname == "real"


def test_scan_sessions_ignores_no_json(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    flights.mkdir()
    (flights / "flight_20260419_001").mkdir()  # no session.json
    csv = _write_csv(tmp_path / "log.csv")
    import_log(csv, flights)
    assert len(scan_sessions(flights)) == 1


# ── get / delete ──────────────────────────────────────────────────────────


def test_get_session_found(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path / "log.csv")
    s = import_log(csv, tmp_path / "flights")
    found = get_session(tmp_path / "flights", s.lid)
    assert found is not None and found.lid == s.lid


def test_get_session_not_found(tmp_path: Path) -> None:
    assert get_session(tmp_path / "flights", "DEDAL-20260419-999") is None


def test_get_session_bad_lid(tmp_path: Path) -> None:
    assert get_session(tmp_path / "flights", "bad-lid") is None


def test_delete_session(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path / "log.csv")
    s = import_log(csv, tmp_path / "flights")
    assert delete_session(tmp_path / "flights", s.lid) is True
    assert not s.dir_path.exists()


def test_delete_session_not_found(tmp_path: Path) -> None:
    assert delete_session(tmp_path / "flights", "DEDAL-20260419-999") is False


# ── _parse_log_meta ───────────────────────────────────────────────────────


def test_parse_log_meta(tmp_path: Path) -> None:
    f = _write_csv(tmp_path / "LOG_TEST.csv")
    meta, gps = _parse_log_meta(f)
    assert meta["config_name"] == "VTOL_CONFIG_v0.49"
    assert meta["fw_version"] == "Beta 1.3"
    assert meta["row_count"] == 3
    assert meta["duration_s"] == 2.5


def test_parse_log_meta_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty.csv"
    f.write_text("timestamp_us,dt_us\n", encoding="utf-8")
    meta, gps = _parse_log_meta(f)
    assert meta["row_count"] == 0
    assert meta["duration_s"] == 0.0


# ── parse_meta_file ───────────────────────────────────────────────────────


_META_CONTENT = """\
# DEDAL flight log metadata
GPS_UTC_REF=2026-04-23T14:32:05.67
MICROS_REF=1234567890
LOG_FILE=LOG_023.csv
"""


def _write_meta(path: Path, content: str = _META_CONTENT) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_meta_file_valid(tmp_path: Path) -> None:
    f = _write_meta(tmp_path / "LOG_023.meta")
    result = parse_meta_file(f)
    assert result is not None
    assert result["gps_utc_ref"] == "2026-04-23T14:32:05.67"
    assert result["micros_ref"] == 1234567890
    assert result["log_file"] == "LOG_023.csv"


def test_parse_meta_file_absent(tmp_path: Path) -> None:
    assert parse_meta_file(tmp_path / "missing.meta") is None


def test_parse_meta_file_unknown_keys_ignored(tmp_path: Path) -> None:
    content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=999\nFUTURE_KEY=ignored\n"
    f = _write_meta(tmp_path / "x.meta", content)
    result = parse_meta_file(f)
    assert result is not None
    assert "FUTURE_KEY" not in result


def test_parse_meta_file_missing_required_field(tmp_path: Path) -> None:
    content = "GPS_UTC_REF=2026-04-23T14:32:05.67\n"  # missing MICROS_REF
    f = _write_meta(tmp_path / "x.meta", content)
    assert parse_meta_file(f) is None


def test_parse_meta_file_bad_micros_ref(tmp_path: Path) -> None:
    content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=NOT_A_NUMBER\n"
    f = _write_meta(tmp_path / "x.meta", content)
    assert parse_meta_file(f) is None


def test_parse_meta_file_comments_ignored(tmp_path: Path) -> None:
    content = "# comment\nGPS_UTC_REF=2026-04-23T14:32:05.67\n# another\nMICROS_REF=42\n"
    f = _write_meta(tmp_path / "x.meta", content)
    result = parse_meta_file(f)
    assert result is not None
    assert result["micros_ref"] == 42


def test_parse_meta_file_log_file_optional(tmp_path: Path) -> None:
    content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=42\n"
    f = _write_meta(tmp_path / "x.meta", content)
    result = parse_meta_file(f)
    assert result is not None
    assert result.get("log_file", "") == ""


# ── _parse_gps_utc_ref ────────────────────────────────────────────────────


def test_parse_gps_utc_ref_with_centiseconds() -> None:
    dt = _parse_gps_utc_ref("2026-04-23T14:32:05.67")
    assert dt == datetime(2026, 4, 23, 14, 32, 5)


def test_parse_gps_utc_ref_without_centiseconds() -> None:
    dt = _parse_gps_utc_ref("2026-04-23T14:32:05")
    assert dt == datetime(2026, 4, 23, 14, 32, 5)


def test_parse_gps_utc_ref_invalid() -> None:
    assert _parse_gps_utc_ref("not-a-date") is None
    assert _parse_gps_utc_ref("") is None


# ── _resolve_timezone ─────────────────────────────────────────────────────


def test_resolve_timezone_paris() -> None:
    # Paris coordinates, summer (CEST = UTC+2)
    dt = datetime(2026, 4, 23, 14, 32, 5)
    tz_name, offset_s = _resolve_timezone(48.8566, 2.3522, dt)
    assert tz_name == "Europe/Paris"
    assert offset_s == 7200  # CEST = UTC+2


def test_resolve_timezone_fallback_on_bad_coords() -> None:
    dt = datetime(2026, 4, 23, 14, 32, 5)
    # Ocean coordinates with no timezone → fallback UTC
    tz_name, offset_s = _resolve_timezone(0.0, 0.0, dt)
    assert offset_s == 0


# ── new fields roundtrip ──────────────────────────────────────────────────


def test_save_load_roundtrip_new_fields(tmp_path: Path) -> None:
    folder = tmp_path / "flight_20260423_001"
    folder.mkdir()
    s = Session(
        lid="DEDAL-20260423-001",
        nickname="Test meta",
        created_at=datetime(2026, 4, 23, 12, 0, 0),
        dir_path=folder,
        log_file="log.csv",
        imported_at=datetime(2026, 4, 28, 10, 0, 0),
        flight_date_utc="2026-04-23T14:32:05",
        tz_name="Europe/Paris",
        tz_offset_s=7200,
        meta_ref={"gps_utc_ref": "2026-04-23T14:32:05.67", "micros_ref": 1234567890, "log_file": "LOG_023.csv"},
        notes="Premier vol de test.",
    )
    save_session(s)
    loaded = load_session(folder)
    assert loaded.imported_at == datetime(2026, 4, 28, 10, 0, 0)
    assert loaded.flight_date_utc == "2026-04-23T14:32:05"
    assert loaded.tz_name == "Europe/Paris"
    assert loaded.tz_offset_s == 7200
    assert loaded.meta_ref["micros_ref"] == 1234567890
    assert loaded.notes == "Premier vol de test."


def test_load_session_new_fields_default_to_none(tmp_path: Path) -> None:
    """Old sessions without new fields load without error."""
    import json
    folder = tmp_path / "flight_20260419_001"
    folder.mkdir()
    data = {
        "lid": "DEDAL-20260419-001",
        "nickname": "old",
        "created_at": "2026-04-19T14:00:00",
        "log_file": "log.csv",
        "video_file": None,
        "tags": [],
        "location": None,
        "log_meta": None,
        "gps_home": None,
    }
    (folder / "session.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = load_session(folder)
    assert loaded.imported_at is None
    assert loaded.flight_date_utc is None
    assert loaded.tz_name is None
    assert loaded.tz_offset_s is None
    assert loaded.meta_ref is None
    assert loaded.notes == ""


def test_import_log_sets_imported_at(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "log.csv")
    before = datetime.now().replace(microsecond=0)
    s = import_log(source, flights)
    after = datetime.now().replace(microsecond=0)
    assert s.imported_at is not None
    assert before <= s.imported_at <= after


def test_import_log_with_meta(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    _write_csv(tmp_path / "LOG_023.csv")
    _write_meta(tmp_path / "LOG_023.meta")
    s = import_log(tmp_path / "LOG_023.csv", flights)
    assert s.meta_ref is not None
    assert s.meta_ref["gps_utc_ref"] == "2026-04-23T14:32:05.67"
    assert s.meta_ref["micros_ref"] == 1234567890
    assert s.flight_date_utc == "2026-04-23T14:32:05"
    assert (s.dir_path / "log.meta").exists()


def test_import_log_without_meta(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "LOG_024.csv")
    s = import_log(source, flights)
    assert s.meta_ref is None
    assert s.flight_date_utc is None
    assert not (s.dir_path / "log.meta").exists()


def test_import_log_meta_log_file_mismatch_warns(tmp_path: Path, caplog) -> None:
    """LOG_FILE mismatch logs a warning but does not fail."""
    import logging
    flights = tmp_path / "flights"
    _write_csv(tmp_path / "LOG_025.csv")
    meta_content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=999\nLOG_FILE=WRONG.csv\n"
    _write_meta(tmp_path / "LOG_025.meta", meta_content)
    with caplog.at_level(logging.WARNING, logger="dedal.sessions"):
        s = import_log(tmp_path / "LOG_025.csv", flights)
    assert s.meta_ref is not None
    assert any("WRONG.csv" in r.message for r in caplog.records)


def test_create_empty_session_sets_imported_at(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    before = datetime.now().replace(microsecond=0)
    s = create_empty_session(flights, nickname="empty")
    after = datetime.now().replace(microsecond=0)
    assert s.imported_at is not None
    assert before <= s.imported_at <= after


# ── reload_meta ───────────────────────────────────────────────────────────


def test_reload_meta_found(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "LOG_023.csv")
    s = import_log(source, flights)
    # Deposit log.meta manually into session folder
    _write_meta(s.dir_path / "log.meta")
    result = reload_meta(s)
    assert result is True
    assert s.meta_ref is not None
    assert s.flight_date_utc == "2026-04-23T14:32:05"
    # Verify persisted to session.json
    loaded = load_session(s.dir_path)
    assert loaded.flight_date_utc == "2026-04-23T14:32:05"


def test_reload_meta_not_found(tmp_path: Path) -> None:
    flights = tmp_path / "flights"
    source = _write_csv(tmp_path / "log.csv")
    s = import_log(source, flights)
    result = reload_meta(s)
    assert result is False
    assert s.meta_ref is None
    assert s.flight_date_utc is None
