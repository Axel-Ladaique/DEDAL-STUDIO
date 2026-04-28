"""Session model — step 2.

A *session* is a folder inside ``flights_root`` whose name encodes the date
and counter:  ``flight_YYYYMMDD_NNN/``

The LID (Local ID) is the canonical identifier stored in session.json:
``DEDAL-YYYYMMDD-NNN``

Layout::

    ~/DEDAL/flights/
        flight_20260419_001/
            session.json        ← metadata
            log.csv             ← copy of the original CSV (never moved)
            video.mp4           ← optional, attached later
            sync.json           ← video↔log offset (step 3)
            flight_pack.json    ← computed data written by viewer HTML (step 4)
            hud_output/         ← transparent PNG sequence (step 5)

session.json schema::

    {
        "lid":         "DEDAL-20260419-001",
        "nickname":    "Mission Alpha",
        "created_at":  "2026-04-19T14:32:00",
        "log_file":    "log.csv",
        "video_file":  null,
        "tags":        [],
        "location":    null,
        "log_meta":    { "config_name": "...", "fw_version": "...",
                         "row_count": 12345, "duration_s": 87.4 }
    }

Notes:
- ``dir_path`` is NOT stored in JSON — it is derived from the folder location.
- ``created_at`` uses the source CSV's mtime (no absolute timestamp in CSV).
- The CSV format has no absolute date; GPS columns carry lat/lon but not UTC
  datetime, so mtime is the only reliable date source.
- Save is atomic: write to ``.tmp`` then ``os.replace`` (POSIX-atomic).
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_meta_file(path: Path) -> dict | None:
    """Parse a DEDAL .meta file. Returns dict or None if absent/malformed.

    Expected keys: gps_utc_ref (str), micros_ref (int), log_file (str, optional).
    Unknown keys are silently ignored.
    """
    if not path.exists():
        return None
    result: dict = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if key == "GPS_UTC_REF":
                    result["gps_utc_ref"] = val
                elif key == "MICROS_REF":
                    try:
                        result["micros_ref"] = int(val)
                    except ValueError:
                        return None
                elif key == "LOG_FILE":
                    result["log_file"] = val
    except OSError:
        return None
    if "gps_utc_ref" not in result or "micros_ref" not in result:
        return None
    result.setdefault("log_file", "")
    return result


def _parse_gps_utc_ref(gps_utc_ref: str) -> datetime | None:
    """Parse GPS_UTC_REF string to datetime (truncates centiseconds).

    Accepts YYYY-MM-DDTHH:MM:SS and YYYY-MM-DDTHH:MM:SS.CC formats.
    """
    try:
        dt_str = gps_utc_ref.split(".")[0]
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _resolve_timezone(lat: float, lon: float, dt_utc: datetime) -> tuple[str, int]:
    """Return (tz_name, offset_seconds) for given GPS coords at dt_utc (DST-aware).

    Falls back to ("UTC", 0) on any error (no GPS, ocean coords, missing lib).
    """
    try:
        from timezonefinder import TimezoneFinder
        from zoneinfo import ZoneInfo
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if tz_name is None:
            return ("UTC", 0)
        aware_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
        local = aware_utc.astimezone(ZoneInfo(tz_name))
        offset_s = int(local.utcoffset().total_seconds())
        return (tz_name, offset_s)
    except Exception:
        return ("UTC", 0)


_DT_FMT = "%Y-%m-%dT%H:%M:%S"
_FOLDER_PREFIX = "flight_"


# ── helpers ───────────────────────────────────────────────────────────────


def _lid_to_folder(lid: str) -> str:
    """Convert ``DEDAL-YYYYMMDD-NNN`` to ``flight_YYYYMMDD_NNN``."""
    parts = lid.split("-")  # ["DEDAL", "YYYYMMDD", "NNN"]
    return f"{_FOLDER_PREFIX}{parts[1]}_{parts[2]}"


def _parse_log_meta(path: Path) -> tuple[dict, "dict | None"]:
    """Stream-scan a DEDAL CSV log and return (summary metadata, gps_home or None)."""
    meta: dict = {
        "filename": path.name,
        "config_name": "",
        "fw_version": "",
        "row_count": 0,
        "duration_s": 0.0,
    }
    first_ts: int | None = None
    last_ts: int | None = None
    row_count = 0
    gps_home: dict | None = None
    col_valid: int | None = None
    col_lat: int | None = None
    col_lon: int | None = None

    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                m = re.match(r"#\s*CONFIG_NAME\s*=\s*(.+)", line)
                if m:
                    meta["config_name"] = m.group(1).strip()
                    continue
                m = re.match(r"#\s*FW_VERSION\s*=\s*(.+)", line)
                if m:
                    meta["fw_version"] = m.group(1).strip()
                continue
            if not line:
                continue
            if line.startswith("timestamp_us"):
                cols = line.split(",")
                try:
                    col_valid = cols.index("gps_valid")
                    col_lat   = cols.index("gps_lat")
                    col_lon   = cols.index("gps_lon")
                except ValueError:
                    pass
                continue
            parts = line.split(",")
            try:
                ts = int(parts[0])
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
                row_count += 1
            except (ValueError, IndexError):
                pass
            if gps_home is None and col_valid is not None:
                try:
                    if parts[col_valid].strip() == "1":
                        lat = float(parts[col_lat])
                        lon = float(parts[col_lon])
                        if lat != 0.0 and lon != 0.0:
                            gps_home = {"lat": lat, "lon": lon}
                except (ValueError, IndexError):
                    pass

    meta["row_count"] = row_count
    if first_ts is not None and last_ts is not None:
        meta["duration_s"] = round((last_ts - first_ts) / 1_000_000, 1)
    return meta, gps_home


# ── dataclass ─────────────────────────────────────────────────────────────


@dataclass
class Session:
    lid: str
    nickname: str
    created_at: datetime
    dir_path: Path
    log_file: str = ""            # relative path inside dir_path
    video_file: str | None = None # relative path inside dir_path
    tags: list[str] = field(default_factory=list)
    location: dict | None = None   # {lat, lon, place_name}
    log_meta: dict | None = None   # populated on CSV import
    gps_home: dict | None = None   # {lat, lon} — first valid GPS fix

    def to_dict(self) -> dict:
        return {
            "lid": self.lid,
            "nickname": self.nickname,
            "created_at": self.created_at.strftime(_DT_FMT),
            "log_file": self.log_file,
            "video_file": self.video_file,
            "tags": self.tags,
            "location": self.location,
            "log_meta": self.log_meta,
            "gps_home": self.gps_home,
        }


# ── persistence ───────────────────────────────────────────────────────────


def save_session(session: Session) -> None:
    """Persist session.json atomically (write .tmp then os.replace)."""
    target = session.dir_path / "session.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(target)


def load_session(dir_path: Path) -> Session:
    """Load a Session from its folder. Raises on missing / malformed JSON."""
    data = json.loads((dir_path / "session.json").read_text(encoding="utf-8"))
    return Session(
        lid=data["lid"],
        nickname=data.get("nickname", ""),
        created_at=datetime.strptime(data["created_at"], _DT_FMT),
        dir_path=dir_path,
        log_file=data.get("log_file", ""),
        video_file=data.get("video_file"),
        tags=data.get("tags", []),
        location=data.get("location"),
        log_meta=data.get("log_meta"),
        gps_home=data.get("gps_home"),
    )


# ── module-level helpers ──────────────────────────────────────────────────


def _next_n(flights_root: Path, date_str: str) -> int:
    """Return the next counter for ``date_str`` by scanning existing folders."""
    folder_prefix = f"{_FOLDER_PREFIX}{date_str}_"
    max_n = 0
    if flights_root.exists():
        for d in flights_root.iterdir():
            if d.is_dir() and d.name.startswith(folder_prefix):
                try:
                    max_n = max(max_n, int(d.name[len(folder_prefix):]))
                except ValueError:
                    pass
    return max_n + 1


def create_empty_session(flights_root: Path, nickname: str = "",
                         tags: list[str] | None = None) -> Session:
    """Create a session folder with no log yet."""
    now = datetime.now().replace(microsecond=0)
    date_str = now.strftime("%Y%m%d")
    n = _next_n(flights_root, date_str)
    lid = f"DEDAL-{date_str}-{n:03d}"
    folder = flights_root / _lid_to_folder(lid)
    folder.mkdir(parents=True, exist_ok=True)
    s = Session(lid=lid, nickname=nickname, created_at=now,
                dir_path=folder, tags=tags or [])
    save_session(s)
    return s


def generate_lid(log_csv_path: Path, flights_root: Path) -> str:
    """Return the next unused LID for the given CSV log.

    Date source: file mtime (the CSV contains no absolute UTC timestamp —
    ``timestamp_us`` is microseconds since MCU power-on, not epoch time).
    Falls back gracefully if mtime is unavailable.
    """
    try:
        mtime = log_csv_path.stat().st_mtime
        date = datetime.fromtimestamp(mtime)
    except OSError:
        date = datetime.now()

    date_str = date.strftime("%Y%m%d")
    return f"DEDAL-{date_str}-{_next_n(flights_root, date_str):03d}"


def import_log(csv_path: Path, flights_root: Path, nickname: str = "") -> Session:
    """Create a new session from a CSV log file.

    Copies (never moves) ``csv_path`` into a new session folder as ``log.csv``.
    Extracts metadata from the CSV and writes ``session.json``.
    """
    lid = generate_lid(csv_path, flights_root)
    folder_name = _lid_to_folder(lid)
    folder = flights_root / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    dest = folder / "log.csv"
    shutil.copy2(csv_path, dest)

    try:
        mtime = csv_path.stat().st_mtime
        created_at = datetime.fromtimestamp(mtime).replace(microsecond=0)
    except OSError:
        created_at = datetime.now().replace(microsecond=0)

    log_meta, gps_home = _parse_log_meta(dest)
    session = Session(
        lid=lid,
        nickname=nickname,
        created_at=created_at,
        dir_path=folder,
        log_file="log.csv",
        log_meta=log_meta,
        gps_home=gps_home,
    )
    save_session(session)
    return session


def extract_gps_home(csv_path: Path) -> "dict | None":
    """Return the first valid GPS fix from a CSV log, or None."""
    _, gps = _parse_log_meta(csv_path)
    return gps


def extract_gps_track(csv_path: Path, max_pts: int = 500) -> "list[list[float]]":
    """Return a downsampled GPS track from a CSV log (at most max_pts points)."""
    col_valid: int | None = None
    col_lat: int | None = None
    col_lon: int | None = None
    points: list[list[float]] = []

    with csv_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            if line.startswith("timestamp_us"):
                cols = line.split(",")
                try:
                    col_valid = cols.index("gps_valid")
                    col_lat   = cols.index("gps_lat")
                    col_lon   = cols.index("gps_lon")
                except ValueError:
                    return []
                continue
            if col_valid is None:
                continue
            parts = line.split(",")
            try:
                if parts[col_valid].strip() == "1":
                    lat = float(parts[col_lat])
                    lon = float(parts[col_lon])
                    if lat != 0.0 and lon != 0.0:
                        points.append([lat, lon])
            except (ValueError, IndexError):
                pass

    if not points:
        return []
    step = max(1, len(points) // max_pts)
    return points[::step]


def scan_sessions(flights_root: Path) -> list[Session]:
    """Return all valid sessions sorted by created_at descending."""
    if not flights_root.exists():
        return []
    sessions: list[Session] = []
    for folder in flights_root.iterdir():
        if not folder.is_dir() or not folder.name.startswith(_FOLDER_PREFIX):
            continue
        if not (folder / "session.json").exists():
            continue
        try:
            sessions.append(load_session(folder))
        except (KeyError, ValueError, OSError) as exc:
            logger.warning("Skipping invalid session at %s: %s", folder, exc)
    sessions.sort(key=lambda s: s.created_at, reverse=True)
    return sessions


def get_session(flights_root: Path, lid: str) -> Session | None:
    """Return the session with the given LID, or None if not found."""
    parts = lid.split("-")
    if len(parts) != 3 or parts[0] != "DEDAL":
        return None
    folder = flights_root / _lid_to_folder(lid)
    if not (folder / "session.json").exists():
        return None
    try:
        return load_session(folder)
    except (KeyError, ValueError, OSError):
        return None


def delete_session(flights_root: Path, lid: str) -> bool:
    """Remove the session folder entirely. Returns False if not found."""
    parts = lid.split("-")
    if len(parts) != 3 or parts[0] != "DEDAL":
        return False
    folder = flights_root / _lid_to_folder(lid)
    if not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True
