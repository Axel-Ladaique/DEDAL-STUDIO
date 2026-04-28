# Meta Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter le support des fichiers `.meta` DEDAL — parsing automatique à l'import, deux dates sur la home page, onglet INFOS dans le viewer avec commentaires.

**Architecture:** Les champs calculés (`flight_date_utc`, `tz_name`, `tz_offset_s`) sont mis en cache dans `session.json` (pattern lazy-populate déjà utilisé pour `gps_home`). Un endpoint `POST /api/sessions/{lid}/reload-meta` permet de déclencher le recalcul après dépôt manuel d'un `log.meta` dans le session folder.

**Tech Stack:** Python `timezonefinder` + `zoneinfo` (stdlib) pour la résolution de timezone côté serveur, FastAPI, HTML/JS vanilla.

---

## File Map

| Fichier | Action | Rôle |
|---------|--------|------|
| `requirements.txt` | Modify | Ajouter `timezonefinder` |
| `dedal/sessions.py` | Modify | `parse_meta_file`, `_parse_gps_utc_ref`, `_resolve_timezone`, `reload_meta`, extension `Session` + `import_log` |
| `dedal/server.py` | Modify | Endpoint `POST /{lid}/reload-meta`, extension `_SessionPatch` + `session_update` |
| `tests/test_sessions.py` | Modify | Tests unitaires des nouvelles fonctions |
| `tests/test_api_sessions.py` | Modify | Tests API reload-meta + PATCH notes |
| `web/index.html` | Modify | Deux colonnes date, bouton ⟳ META |
| `web/viewer.html` | Modify | Onglet ◉ INFOS + pane + JS |

---

## Task 1 — Dépendance + `parse_meta_file`

**Files:**
- Modify: `requirements.txt`
- Modify: `dedal/sessions.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1 — Ajouter timezonefinder à requirements.txt**

```
# requirements.txt — ajouter après numpy>=1.26 :
timezonefinder>=6.5
```

- [ ] **Step 2 — Installer la dépendance**

```bash
source .venv/bin/activate && pip install timezonefinder>=6.5
```

Expected: `Successfully installed timezonefinder-...`

- [ ] **Step 3 — Écrire les tests pour `parse_meta_file`**

Dans `tests/test_sessions.py`, ajouter les imports et les tests suivants (à la fin du fichier) :

```python
from dedal.sessions import parse_meta_file

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
```

- [ ] **Step 4 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py::test_parse_meta_file_valid -v
```

Expected: `FAILED` avec `ImportError: cannot import name 'parse_meta_file'`

- [ ] **Step 5 — Implémenter `parse_meta_file` dans `dedal/sessions.py`**

Ajouter après la ligne `logger = logging.getLogger(__name__)` et avant les helpers existants :

```python
def parse_meta_file(path: Path) -> "dict | None":
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
```

- [ ] **Step 6 — Lancer tous les nouveaux tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "parse_meta_file" -v
```

Expected: 8 tests PASSED

- [ ] **Step 7 — Vérifier que les anciens tests passent toujours**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: tous PASSED

- [ ] **Step 8 — Commit**

```bash
git add requirements.txt dedal/sessions.py tests/test_sessions.py
git commit -m "feat(sessions): add parse_meta_file + timezonefinder dep"
```

---

## Task 2 — `_parse_gps_utc_ref` + `_resolve_timezone`

**Files:**
- Modify: `dedal/sessions.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1 — Écrire les tests**

Ajouter à la fin de `tests/test_sessions.py` :

```python
from dedal.sessions import _parse_gps_utc_ref, _resolve_timezone
from datetime import datetime


def test_parse_gps_utc_ref_with_centiseconds() -> None:
    dt = _parse_gps_utc_ref("2026-04-23T14:32:05.67")
    assert dt == datetime(2026, 4, 23, 14, 32, 5)


def test_parse_gps_utc_ref_without_centiseconds() -> None:
    dt = _parse_gps_utc_ref("2026-04-23T14:32:05")
    assert dt == datetime(2026, 4, 23, 14, 32, 5)


def test_parse_gps_utc_ref_invalid() -> None:
    assert _parse_gps_utc_ref("not-a-date") is None
    assert _parse_gps_utc_ref("") is None


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
```

- [ ] **Step 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "parse_gps_utc_ref or resolve_timezone" -v
```

Expected: FAILED avec `ImportError`

- [ ] **Step 3 — Implémenter les deux fonctions dans `dedal/sessions.py`**

Ajouter immédiatement après `parse_meta_file` :

```python
def _parse_gps_utc_ref(gps_utc_ref: str) -> "datetime | None":
    """Parse GPS_UTC_REF string to datetime (truncates centiseconds).

    Accepts YYYY-MM-DDTHH:MM:SS and YYYY-MM-DDTHH:MM:SS.CC formats.
    """
    try:
        dt_str = gps_utc_ref.split(".")[0]
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _resolve_timezone(lat: float, lon: float, dt_utc: datetime) -> "tuple[str, int]":
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
```

- [ ] **Step 4 — Lancer les tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "parse_gps_utc_ref or resolve_timezone" -v
```

Expected: 5 tests PASSED

- [ ] **Step 5 — Commit**

```bash
git add dedal/sessions.py tests/test_sessions.py
git commit -m "feat(sessions): add _parse_gps_utc_ref + _resolve_timezone"
```

---

## Task 3 — Extension du dataclass `Session` + sérialisation

**Files:**
- Modify: `dedal/sessions.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1 — Écrire le test roundtrip avec les nouveaux champs**

Ajouter à la fin de `tests/test_sessions.py` :

```python
def test_save_load_roundtrip_new_fields(tmp_path: Path) -> None:
    from datetime import datetime
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
    folder = tmp_path / "flight_20260419_001"
    folder.mkdir()
    import json
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
```

- [ ] **Step 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "roundtrip_new_fields or new_fields_default" -v
```

Expected: FAILED (champs inconnus dans Session dataclass)

- [ ] **Step 3 — Étendre le dataclass `Session`**

Dans `dedal/sessions.py`, remplacer le bloc `@dataclass class Session:` existant par :

```python
@dataclass
class Session:
    lid: str
    nickname: str
    created_at: datetime
    dir_path: Path
    log_file: str = ""
    video_file: str | None = None
    tags: list[str] = field(default_factory=list)
    location: dict | None = None
    log_meta: dict | None = None
    gps_home: dict | None = None
    imported_at: datetime | None = None
    flight_date_utc: str | None = None
    tz_name: str | None = None
    tz_offset_s: int | None = None
    meta_ref: dict | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "lid": self.lid,
            "nickname": self.nickname,
            "created_at": self.created_at.strftime(_DT_FMT),
            "imported_at": self.imported_at.strftime(_DT_FMT) if self.imported_at else None,
            "log_file": self.log_file,
            "video_file": self.video_file,
            "tags": self.tags,
            "location": self.location,
            "log_meta": self.log_meta,
            "gps_home": self.gps_home,
            "flight_date_utc": self.flight_date_utc,
            "tz_name": self.tz_name,
            "tz_offset_s": self.tz_offset_s,
            "meta_ref": self.meta_ref,
            "notes": self.notes,
        }
```

- [ ] **Step 4 — Mettre à jour `load_session`**

Remplacer la fonction `load_session` existante par :

```python
def load_session(dir_path: Path) -> Session:
    """Load a Session from its folder. Raises on missing / malformed JSON."""
    data = json.loads((dir_path / "session.json").read_text(encoding="utf-8"))
    imported_at_str = data.get("imported_at")
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
        imported_at=datetime.strptime(imported_at_str, _DT_FMT) if imported_at_str else None,
        flight_date_utc=data.get("flight_date_utc"),
        tz_name=data.get("tz_name"),
        tz_offset_s=data.get("tz_offset_s"),
        meta_ref=data.get("meta_ref"),
        notes=data.get("notes", ""),
    )
```

- [ ] **Step 5 — Lancer les tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -v
```

Expected: tous PASSED

- [ ] **Step 6 — Commit**

```bash
git add dedal/sessions.py tests/test_sessions.py
git commit -m "feat(sessions): extend Session dataclass with meta/tz/notes fields"
```

---

## Task 4 — Extension de `import_log` + `create_empty_session`

**Files:**
- Modify: `dedal/sessions.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1 — Écrire les tests**

Ajouter à la fin de `tests/test_sessions.py` :

```python
def test_import_log_sets_imported_at(tmp_path: Path) -> None:
    from datetime import datetime
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
    # meta says LOG_FILE=WRONG.csv
    meta_content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=999\nLOG_FILE=WRONG.csv\n"
    _write_meta(tmp_path / "LOG_025.meta", meta_content)
    with caplog.at_level(logging.WARNING, logger="dedal.sessions"):
        s = import_log(tmp_path / "LOG_025.csv", flights)
    assert s.meta_ref is not None  # still parsed
    assert any("mismatch" in r.message.lower() or "WRONG.csv" in r.message for r in caplog.records)


def test_create_empty_session_sets_imported_at(tmp_path: Path) -> None:
    from datetime import datetime
    flights = tmp_path / "flights"
    before = datetime.now().replace(microsecond=0)
    s = create_empty_session(flights, nickname="empty")
    after = datetime.now().replace(microsecond=0)
    assert s.imported_at is not None
    assert before <= s.imported_at <= after
```

- [ ] **Step 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "import_log_sets_imported or import_log_with_meta or import_log_without_meta or import_log_meta_log or create_empty_session_sets" -v
```

Expected: tous FAILED

- [ ] **Step 3 — Étendre `import_log` dans `dedal/sessions.py`**

Remplacer la fonction `import_log` existante par :

```python
def import_log(csv_path: Path, flights_root: Path, nickname: str = "") -> Session:
    """Create a new session from a CSV log file.

    Copies (never moves) csv_path into a new session folder.
    Also copies {csv_stem}.meta from the same directory if present.
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

    imported_at = datetime.now().replace(microsecond=0)
    log_meta, gps_home = _parse_log_meta(dest)

    meta_ref: dict | None = None
    flight_date_utc: str | None = None
    tz_name: str | None = None
    tz_offset_s: int | None = None

    source_meta = csv_path.parent / (csv_path.stem + ".meta")
    if source_meta.exists():
        parsed = parse_meta_file(source_meta)
        if parsed:
            shutil.copy2(source_meta, folder / "log.meta")
            meta_ref = parsed
            dt = _parse_gps_utc_ref(parsed["gps_utc_ref"])
            if dt:
                flight_date_utc = dt.strftime(_DT_FMT)
                if gps_home:
                    tz_name, tz_offset_s = _resolve_timezone(
                        gps_home["lat"], gps_home["lon"], dt
                    )
            if parsed.get("log_file") and parsed["log_file"] != csv_path.name:
                logger.warning(
                    "meta LOG_FILE=%r doesn't match CSV name %r — loading anyway",
                    parsed["log_file"], csv_path.name,
                )

    session = Session(
        lid=lid,
        nickname=nickname,
        created_at=created_at,
        dir_path=folder,
        log_file="log.csv",
        log_meta=log_meta,
        gps_home=gps_home,
        imported_at=imported_at,
        flight_date_utc=flight_date_utc,
        tz_name=tz_name,
        tz_offset_s=tz_offset_s,
        meta_ref=meta_ref,
    )
    save_session(session)
    return session
```

- [ ] **Step 4 — Étendre `create_empty_session`**

Remplacer la fonction `create_empty_session` existante par :

```python
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
                dir_path=folder, tags=tags or [], imported_at=now)
    save_session(s)
    return s
```

- [ ] **Step 5 — Lancer les tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -v
```

Expected: tous PASSED

- [ ] **Step 6 — Commit**

```bash
git add dedal/sessions.py tests/test_sessions.py
git commit -m "feat(sessions): auto-detect .meta at import, set imported_at"
```

---

## Task 5 — Fonction `reload_meta` + tests unitaires

**Files:**
- Modify: `dedal/sessions.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1 — Écrire les tests**

Ajouter à la fin de `tests/test_sessions.py` :

```python
from dedal.sessions import reload_meta


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
    from dedal.sessions import load_session
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
```

- [ ] **Step 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -k "reload_meta" -v
```

Expected: FAILED avec `ImportError: cannot import name 'reload_meta'`

- [ ] **Step 3 — Implémenter `reload_meta` dans `dedal/sessions.py`**

Ajouter après `extract_gps_track` :

```python
def reload_meta(session: Session) -> bool:
    """Read log.meta from session folder, update session fields, save atomically.

    Returns True if log.meta was found and parsed successfully, False otherwise.
    Clears meta fields if no valid log.meta is present.
    """
    meta_path = session.dir_path / "log.meta"
    parsed = parse_meta_file(meta_path)
    if not parsed:
        session.meta_ref = None
        session.flight_date_utc = None
        session.tz_name = None
        session.tz_offset_s = None
        save_session(session)
        return False

    session.meta_ref = parsed
    dt = _parse_gps_utc_ref(parsed["gps_utc_ref"])
    if dt:
        session.flight_date_utc = dt.strftime(_DT_FMT)
        if session.gps_home:
            session.tz_name, session.tz_offset_s = _resolve_timezone(
                session.gps_home["lat"], session.gps_home["lon"], dt
            )
    save_session(session)
    return True
```

- [ ] **Step 4 — Lancer les tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_sessions.py -v
```

Expected: tous PASSED

- [ ] **Step 5 — Commit**

```bash
git add dedal/sessions.py tests/test_sessions.py
git commit -m "feat(sessions): add reload_meta function"
```

---

## Task 6 — Extension `server.py` : endpoint reload-meta + PATCH notes

**Files:**
- Modify: `dedal/server.py`
- Modify: `tests/test_api_sessions.py`

- [ ] **Step 1 — Écrire les tests API**

Ajouter à la fin de `tests/test_api_sessions.py` :

```python
import io
from pathlib import Path


def test_patch_notes(client) -> None:
    r = client.post("/api/sessions/import",
                    files={"file": ("log.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")})
    lid = r.json()["lid"]
    r2 = client.patch(f"/api/sessions/{lid}", json={"notes": "Premier test."})
    assert r2.status_code == 200
    assert r2.json()["notes"] == "Premier test."
    # Verify persisted
    r3 = client.get(f"/api/sessions/{lid}")
    assert r3.json()["notes"] == "Premier test."


def test_patch_notes_empty_string(client) -> None:
    r = client.post("/api/sessions/import",
                    files={"file": ("log.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")})
    lid = r.json()["lid"]
    client.patch(f"/api/sessions/{lid}", json={"notes": "some text"})
    r2 = client.patch(f"/api/sessions/{lid}", json={"notes": ""})
    assert r2.json()["notes"] == ""


def test_reload_meta_no_meta_file(client) -> None:
    r = client.post("/api/sessions/import",
                    files={"file": ("log.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")})
    lid = r.json()["lid"]
    r2 = client.post(f"/api/sessions/{lid}/reload-meta")
    assert r2.status_code == 200
    assert "warning" in r2.json()


def test_reload_meta_with_meta_file(client, flights_root: Path) -> None:
    """After depositing log.meta manually, reload-meta picks it up."""
    r = client.post("/api/sessions/import",
                    files={"file": ("log.csv", io.BytesIO(_MINIMAL_CSV.encode()), "text/csv")})
    lid = r.json()["lid"]
    # Simulate manual deposit of log.meta
    from dedal.sessions import _lid_to_folder
    folder = flights_root / _lid_to_folder(lid)
    meta_content = "GPS_UTC_REF=2026-04-23T14:32:05.67\nMICROS_REF=1234567890\nLOG_FILE=log.csv\n"
    (folder / "log.meta").write_text(meta_content, encoding="utf-8")
    r2 = client.post(f"/api/sessions/{lid}/reload-meta")
    assert r2.status_code == 200
    data = r2.json()
    assert data["flight_date_utc"] == "2026-04-23T14:32:05"
    assert data["meta_ref"]["micros_ref"] == 1234567890


def test_reload_meta_not_found(client) -> None:
    r = client.post(f"/api/sessions/DEDAL-20990101-999/reload-meta")
    assert r.status_code == 404
```

- [ ] **Step 2 — Lancer les tests, vérifier qu'ils échouent**

```bash
source .venv/bin/activate && python -m pytest tests/test_api_sessions.py -k "patch_notes or reload_meta" -v
```

Expected: FAILED

- [ ] **Step 3 — Mettre à jour les imports dans `dedal/server.py`**

Dans la section `from .sessions import (...)`, ajouter `reload_meta` :

```python
from .sessions import (
    create_empty_session,
    delete_session,
    extract_gps_home,
    extract_gps_track,
    get_session,
    import_log,
    reload_meta,
    save_session,
    scan_sessions,
)
```

- [ ] **Step 4 — Étendre `_SessionPatch` pour accepter `notes`**

Remplacer la classe `_SessionPatch` existante par :

```python
class _SessionPatch(BaseModel):
    nickname: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
```

- [ ] **Step 5 — Mettre à jour `session_update` pour gérer `notes`**

Dans la fonction `session_update`, ajouter après `if body.tags is not None:` :

```python
    if body.notes is not None:
        s.notes = body.notes
```

- [ ] **Step 6 — Ajouter l'endpoint `reload-meta`**

Ajouter après l'endpoint `session_put_sync` (ligne ~273) :

```python
@_sessions.post("/{lid}/reload-meta")
def session_reload_meta(lid: str, request: Request) -> JSONResponse:
    """Re-read log.meta from the session folder and update cached fields.

    Use after manually depositing a .meta file into the session directory.
    """
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    found = reload_meta(s)
    result = s.to_dict()
    if not found:
        result["warning"] = "no log.meta found in session folder"
    return JSONResponse(result)
```

- [ ] **Step 7 — Lancer tous les tests**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: tous PASSED

- [ ] **Step 8 — Commit**

```bash
git add dedal/server.py tests/test_api_sessions.py
git commit -m "feat(api): add POST /reload-meta, extend PATCH with notes field"
```

---

## Task 7 — Home page : deux dates + bouton ⟳ META

**Files:**
- Modify: `web/index.html`

Note : pas de tests automatisés pour le HTML. Tester manuellement après modification.

- [ ] **Step 1 — Mettre à jour le grid CSS (styles)**

Dans `web/index.html`, remplacer les deux occurrences de :
```css
grid-template-columns: 170px 1fr 110px 220px 160px;
```
par :
```css
grid-template-columns: 170px 1fr 110px 110px 220px 160px;
```
(Il y a deux occurrences : `.sessions-header` et `.session-row`, lignes ~108 et ~116.)

- [ ] **Step 2 — Mettre à jour le header de la liste**

Remplacer :
```html
      <div class="sessions-header">
        <div>LID</div>
        <div>Nom</div>
        <div>Date</div>
        <div>Log</div>
        <div></div>
      </div>
```
par :
```html
      <div class="sessions-header">
        <div>LID</div>
        <div>Nom</div>
        <div>Vol</div>
        <div>Import</div>
        <div>Log</div>
        <div></div>
      </div>
```

- [ ] **Step 3 — Ajouter la fonction `fmtFlightDate` dans le JS**

Dans la section JS (avant `renderSessions`), ajouter :

```javascript
function fmtFlightDate(s) {
  // Use flight_date_utc + tz_offset_s if available, else created_at
  if (s.flight_date_utc && s.tz_offset_s != null) {
    const utcMs = new Date(s.flight_date_utc + 'Z').getTime();
    const localMs = utcMs + s.tz_offset_s * 1000;
    const d = new Date(localMs);
    const pad = n => String(n).padStart(2, '0');
    const dateStr = `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())}`;
    const timeStr = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
    const tzLabel = s.tz_name ? ` <span style="color:var(--dim);font-size:9px;">[${s.tz_name.split('/').pop()}]</span>` : '';
    return dateStr + ' ' + timeStr + tzLabel;
  }
  if (s.flight_date_utc) {
    return s.flight_date_utc.replace('T', ' ').slice(0, 16) + ' <span style="color:var(--dim);font-size:9px;">UTC</span>';
  }
  return fmtDate(s.created_at) + ' <span style="color:var(--dim);font-size:9px;">≈mtime</span>';
}

function fmtImportDate(s) {
  return fmtDate(s.imported_at || s.created_at);
}
```

- [ ] **Step 4 — Mettre à jour le rendu de la session-row**

Trouver la ligne dans `renderSessions` qui affiche la date (actuellement) :
```javascript
      <div class="date" title="Date du vol (mtime CSV)">VOL ${fmtDate(s.created_at)}</div>
```
Remplacer par :
```javascript
      <div class="date">${fmtFlightDate(s)}</div>
      <div class="date">${fmtImportDate(s)}</div>
```

- [ ] **Step 5 — Ajouter le bouton ⟳ META dans les row-actions**

Dans le template de session-row, trouver la div `.row-actions` et ajouter le bouton ⟳ META (avant le bouton VID) :

```javascript
      <div class="row-actions" onclick="event.stopPropagation()">
        ${s.log_file ? `<button class="btn sm" title="Recharger .meta depuis le dossier session" onclick="reloadMeta('${s.lid}')">⟳ META</button>` : ''}
        <label class="import-label" title="Attacher une vidéo">
          VID
          <input type="file" accept="video/*" onchange="attachVideo('${s.lid}', this)">
        </label>
        <button class="btn sm danger" onclick="deleteSession('${s.lid}')">✕</button>
      </div>
```

- [ ] **Step 6 — Ajouter la fonction `reloadMeta` dans le JS**

```javascript
async function reloadMeta(lid) {
  try {
    const r = await fetch(`/api/sessions/${lid}/reload-meta`, { method: 'POST' });
    const data = await r.json();
    if (!r.ok) { showBanner('err', 'Erreur reload-meta : ' + (data.error || r.status)); return; }
    if (data.warning) {
      showBanner('err', `${lid} : aucun log.meta trouvé dans le dossier session.`);
    } else {
      showBanner('ok', `${lid} : métadonnées rechargées — ${data.flight_date_utc || 'pas de date GPS'}`);
    }
    // Refresh session in local array
    const idx = sessions.findIndex(s => s.lid === lid);
    if (idx >= 0) sessions[idx] = data;
    renderSessions();
  } catch(e) {
    showBanner('err', 'Erreur réseau : ' + e.message);
  }
}
```

- [ ] **Step 7 — Vérifier manuellement**

Lancer l'app :
```bash
source .venv/bin/activate && python app.py --browser
```
Vérifier :
- La home page affiche 2 colonnes de dates (Vol / Import)
- Le bouton ⟳ META apparaît sur les sessions avec un log
- Cliquer ⟳ META sur une session sans `log.meta` affiche le banner d'avertissement

- [ ] **Step 8 — Commit**

```bash
git add web/index.html
git commit -m "feat(ui): two date columns (vol/import) + reload-meta button on home page"
```

---

## Task 8 — Viewer : onglet ◉ INFOS

**Files:**
- Modify: `web/viewer.html`

- [ ] **Step 1 — Ajouter l'onglet dans la tab-bar**

Dans `web/viewer.html`, trouver :
```html
  <div class="vtab" data-tab="analyse">◎ ANALYSE</div>
  <div class="vtab disabled">⚙ HUD</div>
```
Remplacer par :
```html
  <div class="vtab" data-tab="analyse">◎ ANALYSE</div>
  <div class="vtab" data-tab="info">◉ INFOS</div>
  <div class="vtab disabled">⚙ HUD</div>
```

- [ ] **Step 2 — Ajouter le pane HTML après `pane-analyse`**

Trouver la ligne :
```html
<div class="tab-pane" id="pane-analyse">
```

Juste avant cette div (ou après la fermeture de `pane-analyse` — trouver `</div>` correspondant puis insérer après), ajouter le nouveau pane. Le plus simple est de l'insérer **avant** `pane-analyse`. Trouver la ligne 1889 environ :
```html
<div class="tab-pane" id="pane-analyse">
```
Et ajouter juste **après** la fermeture du `pane-analyse` (chercher la dernière `</div>` avant `<div class="tab-pane" id="pane-graphs">` ou similaire).

En pratique, chercher `</div>` juste avant `<!-- ══ FIN PANE ANALYSE ══ -->` ou le prochain `<div class="tab-pane"`. Insérer le bloc suivant :

```html
<!-- ══ TAB INFOS ══ -->
<div class="tab-pane" id="pane-info">
  <div id="info-content" style="padding:24px 32px;max-width:820px;margin:0 auto;">
    <div id="info-loading" style="font-family:var(--font-mono);font-size:11px;color:var(--dim);letter-spacing:1px;">CHARGEMENT…</div>
  </div>
</div>
```

- [ ] **Step 3 — Ajouter le cas 'info' dans le tab switching**

Dans le bloc tab switching (autour de la ligne 10094), trouver :
```javascript
      if (t.dataset.tab === 'analyse') {
        renderAnalysisPanels();
      }
```
Ajouter après :
```javascript
      if (t.dataset.tab === 'info') {
        loadInfoTab();
      }
```

- [ ] **Step 4 — Ajouter les fonctions `loadInfoTab`, `renderInfoTab`, `saveInfoNotes`**

À la fin du fichier (avant `</script>` final, ou après le bloc tab switching), ajouter :

```javascript
// ── ONGLET INFOS ──────────────────────────────────────────────────────────
var _infoLoaded = false;

function loadInfoTab() {
  if (_infoLoaded) return;
  _infoLoaded = true;
  var lid = new URLSearchParams(location.search).get('lid');
  if (!lid) {
    document.getElementById('info-content').innerHTML =
      '<p style="font-family:var(--font-mono);font-size:11px;color:var(--dim);">Session non disponible hors mode intégré.</p>';
    return;
  }
  fetch('/api/sessions/' + lid)
    .then(function(r) { return r.json(); })
    .then(function(s) { renderInfoTab(s); })
    .catch(function() {
      document.getElementById('info-content').innerHTML =
        '<p style="font-family:var(--font-mono);font-size:11px;color:var(--danger);">Erreur lors du chargement de la session.</p>';
    });
}

function renderInfoTab(s) {
  var flightDateDisplay = '—';
  var localTimeDisplay = '—';
  if (s.flight_date_utc) {
    flightDateDisplay = s.flight_date_utc + ' UTC';
    if (s.tz_offset_s !== null && s.tz_offset_s !== undefined) {
      var utcMs = new Date(s.flight_date_utc + 'Z').getTime();
      var localMs = utcMs + s.tz_offset_s * 1000;
      var ld = new Date(localMs);
      function pad(n) { return String(n).padStart(2, '0'); }
      var localStr = ld.getUTCFullYear() + '-' + pad(ld.getUTCMonth()+1) + '-' + pad(ld.getUTCDate())
        + ' ' + pad(ld.getUTCHours()) + ':' + pad(ld.getUTCMinutes()) + ':' + pad(ld.getUTCSeconds());
      localTimeDisplay = localStr + (s.tz_name ? ' [' + s.tz_name + ']' : '');
    }
  } else if (s.created_at) {
    flightDateDisplay = s.created_at + ' <span style="color:var(--dim);font-size:10px;">(estimé depuis mtime CSV)</span>';
  }

  var lm = s.log_meta || {};
  var dur = lm.duration_s > 0 ? lm.duration_s + 's' : '—';
  var pts = lm.row_count > 0 ? lm.row_count + ' points' : '—';
  var gpsStr = s.gps_home ? s.gps_home.lat.toFixed(5) + ', ' + s.gps_home.lon.toFixed(5) : '—';

  var metaRefHtml;
  if (s.meta_ref) {
    metaRefHtml = '<div class="irow"><span class="ilbl">GPS_UTC_REF</span><span class="ival">' + s.meta_ref.gps_utc_ref + '</span></div>'
      + '<div class="irow"><span class="ilbl">MICROS_REF</span><span class="ival">' + s.meta_ref.micros_ref + '</span></div>';
  } else {
    metaRefHtml = '<span style="color:var(--dim);font-style:italic;font-family:var(--font-mono);font-size:11px;">Horodatage absolu non disponible</span>';
  }

  document.getElementById('info-content').innerHTML = '<style>'
    + '.isec{margin-bottom:24px}'
    + '.isec-title{font-family:var(--font-mono);font-size:10px;letter-spacing:2px;color:var(--accent);text-transform:uppercase;border-bottom:1px solid var(--border);padding-bottom:6px;margin-bottom:12px}'
    + '.irow{display:flex;gap:16px;margin-bottom:8px;align-items:baseline}'
    + '.ilbl{font-family:var(--font-mono);font-size:10px;letter-spacing:1px;color:var(--dim);text-transform:uppercase;width:160px;flex-shrink:0}'
    + '.ival{font-family:var(--font-mono);font-size:12px;color:var(--text)}'
    + '.inotes{width:100%;min-height:120px;background:var(--surface2);border:1px solid var(--border2);color:var(--text);font-family:-apple-system,sans-serif;font-size:13px;padding:10px 12px;border-radius:4px;resize:vertical;outline:none}'
    + '.inotes:focus{border-color:var(--accent)}'
    + '</style>'
    + '<div class="isec"><div class="isec-title">◈ Vol</div>'
    + '<div class="irow"><span class="ilbl">Date UTC</span><span class="ival">' + flightDateDisplay + '</span></div>'
    + '<div class="irow"><span class="ilbl">Heure locale</span><span class="ival">' + localTimeDisplay + '</span></div>'
    + '<div class="irow"><span class="ilbl">Durée</span><span class="ival">' + dur + '</span></div>'
    + '<div class="irow"><span class="ilbl">Points log</span><span class="ival">' + pts + '</span></div>'
    + '</div>'
    + '<div class="isec"><div class="isec-title">⚙ Système</div>'
    + '<div class="irow"><span class="ilbl">Firmware</span><span class="ival">' + (lm.fw_version || '—') + '</span></div>'
    + '<div class="irow"><span class="ilbl">Config</span><span class="ival">' + (lm.config_name || '—') + '</span></div>'
    + '<div class="irow"><span class="ilbl">GPS home</span><span class="ival">' + gpsStr + '</span></div>'
    + '</div>'
    + '<div class="isec"><div class="isec-title">⏱ Référence temporelle</div>' + metaRefHtml + '</div>'
    + '<div class="isec"><div class="isec-title">📝 Commentaires</div>'
    + '<textarea class="inotes" id="info-notes-ta"></textarea>'
    + '<div style="margin-top:10px;display:flex;align-items:center;gap:12px;">'
    + '<button class="btn sm" onclick="saveInfoNotes(\'' + (s.lid || '') + '\')">Sauvegarder</button>'
    + '<span id="info-notes-fb" style="font-family:var(--font-mono);font-size:10px;"></span>'
    + '</div></div>';

  // Set textarea value safely after innerHTML (avoids HTML injection)
  document.getElementById('info-notes-ta').value = s.notes || '';
}

function saveInfoNotes(lid) {
  var notes = document.getElementById('info-notes-ta').value;
  var fb = document.getElementById('info-notes-fb');
  fb.textContent = '';
  fetch('/api/sessions/' + lid, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({notes: notes})
  }).then(function(r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    fb.style.color = 'var(--accent3)';
    fb.textContent = '✓ Sauvegardé';
    setTimeout(function() { fb.textContent = ''; }, 2000);
  }).catch(function(e) {
    fb.style.color = 'var(--danger)';
    fb.textContent = '✗ Erreur : ' + e.message;
  });
}
```

- [ ] **Step 5 — Vérifier manuellement dans le viewer**

```bash
source .venv/bin/activate && python app.py --browser
```

- Ouvrir une session avec log, aller dans le viewer
- Cliquer l'onglet ◉ INFOS
- Vérifier : blocs Vol, Système, Référence temporelle, Commentaires s'affichent
- Taper des notes, cliquer Sauvegarder → feedback vert ✓
- Rafraîchir la page, revenir sur INFOS → les notes sont toujours là

- [ ] **Step 6 — Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): add INFOS tab with flight recap and notes editor"
```

---

## Task 9 — Tests de régression + mise à jour CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1 — Lancer la suite complète**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: tous PASSED, aucun nouveau warning inattendu.

- [ ] **Step 2 — Mettre à jour CLAUDE.md**

Dans la section **Roadmap**, changer l'étape 9 et ajouter l'étape 10 :

```markdown
| 9 | Graph explorer — améliorations UX | ✅ |
| 10 | Support fichiers .meta (timezone, dates, onglet INFOS, notes) | ✅ |
```

Dans la section **Endpoints API**, ajouter :

```markdown
| POST | `/api/sessions/{lid}/reload-meta` | Recharger les métadonnées depuis `log.meta` sur disque |
```

Et dans le PATCH existant, noter le champ `notes`.

Dans **session.json Format**, ajouter les nouveaux champs (`imported_at`, `flight_date_utc`, `tz_name`, `tz_offset_s`, `meta_ref`, `notes`).

- [ ] **Step 3 — Commit final**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for step 10 (.meta support)"
```
