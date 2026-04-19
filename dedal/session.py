"""Session model — step 2.

A *session* is a folder inside ``flights_root`` whose name is the LID.
The folder always contains ``session.json`` with the session metadata.

LID format: ``YYYYMMDD-NNN``  (date of creation + 3-digit counter).
Example:  ``20260419-001``,  ``20260419-002``,  ``20260420-001``

Layout::

    ~/DEDAL/flights/
        20260419-001/
            session.json
            LOG_017.csv          ← imported flight log
            (later: video files, flight_pack.json …)
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_DATE_FMT = "%Y%m%d"
_DT_FMT = "%Y-%m-%dT%H:%M:%S"


def _next_lid(flights_root: Path, now: datetime) -> str:
    """Return the next unused LID for *now*'s date."""
    prefix = now.strftime(_DATE_FMT) + "-"
    max_n = 0
    if flights_root.exists():
        for d in flights_root.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                try:
                    max_n = max(max_n, int(d.name[len(prefix):]))
                except ValueError:
                    pass
    return f"{now.strftime(_DATE_FMT)}-{max_n + 1:03d}"


def _parse_log_meta(path: Path) -> dict:
    """Extract metadata from a DEDAL CSV log file.

    Scans comment lines for CONFIG_NAME / FW_VERSION, then iterates data
    rows to compute duration and row count.  Does not load the whole file
    into memory — streams line by line.
    """
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
            if not line or line.startswith("timestamp_us"):
                continue
            parts = line.split(",", 2)
            try:
                ts = int(parts[0])
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
                row_count += 1
            except (ValueError, IndexError):
                pass

    meta["row_count"] = row_count
    if first_ts is not None and last_ts is not None:
        meta["duration_s"] = round((last_ts - first_ts) / 1_000_000, 1)
    return meta


@dataclass
class Session:
    lid: str
    created_at: datetime
    name: str = ""
    notes: str = ""
    log: dict | None = None

    # ── persistence ───────────────────────────────────────────────────────

    def folder(self, flights_root: Path) -> Path:
        return flights_root / self.lid

    def save(self, flights_root: Path) -> None:
        """Write (or overwrite) session.json inside the session folder."""
        folder = self.folder(flights_root)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "session.json").write_text(
            json.dumps(self.to_dict(), indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, folder: Path) -> Session:
        """Load from an existing session folder. Raises if session.json is absent."""
        data = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        return cls(
            lid=data["lid"],
            created_at=datetime.strptime(data["created_at"], _DT_FMT),
            name=data.get("name", ""),
            notes=data.get("notes", ""),
            log=data.get("log"),
        )

    @classmethod
    def create(cls, flights_root: Path, name: str = "") -> Session:
        """Allocate a new LID, persist, and return the Session."""
        now = datetime.now().replace(microsecond=0)
        lid = _next_lid(flights_root, now)
        session = cls(lid=lid, created_at=now, name=name)
        session.save(flights_root)
        return session

    # ── serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "lid": self.lid,
            "created_at": self.created_at.strftime(_DT_FMT),
            "name": self.name,
            "notes": self.notes,
            "log": self.log,
        }


# ── module-level helpers ──────────────────────────────────────────────────


def list_sessions(flights_root: Path) -> list[Session]:
    """Return all sessions sorted by LID (= chronological order)."""
    if not flights_root.exists():
        return []
    sessions: list[Session] = []
    for folder in sorted(flights_root.iterdir()):
        if folder.is_dir() and (folder / "session.json").exists():
            try:
                sessions.append(Session.load(folder))
            except (KeyError, ValueError, OSError):
                pass
    return sessions


def get_session(flights_root: Path, lid: str) -> Session | None:
    """Return the session with the given LID, or None if not found."""
    folder = flights_root / lid
    if not (folder / "session.json").exists():
        return None
    try:
        return Session.load(folder)
    except (KeyError, ValueError, OSError):
        return None


def delete_session(flights_root: Path, lid: str) -> bool:
    """Remove the session folder entirely. Returns False if not found."""
    folder = flights_root / lid
    if not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True
