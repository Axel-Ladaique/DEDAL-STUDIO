"""FastAPI app factory."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
from pathlib import Path
from queue import Empty, Queue

from fastapi import APIRouter, FastAPI, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import os
from .config import Config
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


WEB_DIR = Path(__file__).resolve().parents[1] / "web"


# ── sessions router ───────────────────────────────────────────────────────


class _SessionCreate(BaseModel):
    nickname: str = ""
    tags: list[str] = []


class _SessionPatch(BaseModel):
    nickname: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


_sessions = APIRouter(prefix="/api/sessions", tags=["sessions"])


@_sessions.get("")
def sessions_list(request: Request) -> JSONResponse:
    items = scan_sessions(request.app.state.cfg.flights_root)
    # Lazy-populate gps_home from flight_pack.json for sessions that don't have it yet.
    for s in items:
        if s.gps_home is None:
            pack_file = s.dir_path / "flight_pack.json"
            if pack_file.exists():
                try:
                    frames = json.loads(pack_file.read_text(encoding="utf-8")).get("frames", [])
                    for fr in frames:
                        if fr.get("gps_ok") and fr.get("lat") and fr.get("lon"):
                            s.gps_home = {"lat": fr["lat"], "lon": fr["lon"]}
                            save_session(s)
                            break
                except (OSError, ValueError):
                    pass
            elif s.log_file:
                csv_path = s.dir_path / s.log_file
                if csv_path.exists():
                    try:
                        gps = extract_gps_home(csv_path)
                        if gps:
                            s.gps_home = gps
                            save_session(s)
                    except (OSError, ValueError):
                        pass
    return JSONResponse([s.to_dict() for s in items])


@_sessions.post("", status_code=201)
def session_create(body: _SessionCreate, request: Request) -> JSONResponse:
    """Create an empty session (no log attached yet)."""
    s = create_empty_session(
        request.app.state.cfg.flights_root,
        nickname=body.nickname,
        tags=body.tags,
    )
    return JSONResponse(s.to_dict(), status_code=201)


@_sessions.post("/import", status_code=201)
async def session_import(
    request: Request,
    file: UploadFile,
    nickname: str = Query(default=""),
    meta_file: UploadFile | None = None,
) -> JSONResponse:
    """Import a CSV log — automatically creates a new session."""
    cfg = request.app.state.cfg
    suffix = Path(file.filename or "log.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        tmp_path.write_bytes(await file.read())
        s = import_log(tmp_path, cfg.flights_root, nickname=nickname)
        # Rename log.csv to the original filename when it differs.
        if file.filename and file.filename != "log.csv":
            orig_dest = s.dir_path / file.filename
            (s.dir_path / "log.csv").rename(orig_dest)
            s.log_file = file.filename
            if s.log_meta:
                s.log_meta["filename"] = file.filename
            save_session(s)
        # Save and apply .meta if provided alongside the CSV.
        if meta_file is not None:
            meta_bytes = await meta_file.read()
            (s.dir_path / "log.meta").write_bytes(meta_bytes)
            reload_meta(s)
    finally:
        tmp_path.unlink(missing_ok=True)
    return JSONResponse(s.to_dict(), status_code=201)


@_sessions.get("/{lid}")
def session_get(lid: str, request: Request) -> JSONResponse:
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    return JSONResponse(s.to_dict())


@_sessions.patch("/{lid}")
def session_update(lid: str, body: _SessionPatch, request: Request) -> JSONResponse:
    cfg = request.app.state.cfg
    s = get_session(cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    if body.nickname is not None:
        s.nickname = body.nickname
    if body.tags is not None:
        s.tags = body.tags
    if body.notes is not None:
        s.notes = body.notes
    save_session(s)
    return JSONResponse(s.to_dict())


@_sessions.delete("/{lid}", status_code=204)
def session_delete(lid: str, request: Request) -> Response:
    found = delete_session(request.app.state.cfg.flights_root, lid)
    if not found:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    return Response(status_code=204)


@_sessions.get("/{lid}/log")
def session_get_log(lid: str, request: Request) -> Response:
    """Serve the raw CSV log file for this session."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    if not s.log_file:
        return JSONResponse({"error": "no log attached"}, status_code=404)
    path = s.dir_path / s.log_file
    if not path.exists():
        return JSONResponse({"error": "log file missing on disk"}, status_code=404)
    return FileResponse(path, media_type="text/csv", filename=s.log_file)


@_sessions.get("/{lid}/pack")
def session_get_pack(lid: str, request: Request) -> Response:
    """Return flight_pack.json computed by the viewer HTML."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    pack_file = s.dir_path / "flight_pack.json"
    if not pack_file.exists():
        return JSONResponse({"error": "flight_pack.json not yet generated"}, status_code=404)
    try:
        return JSONResponse(json.loads(pack_file.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return JSONResponse({"error": "corrupted flight_pack.json"}, status_code=500)


@_sessions.put("/{lid}/pack")
async def session_put_pack(lid: str, request: Request) -> JSONResponse:
    """Receive and persist flight_pack.json from the viewer HTML."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    pack_file = s.dir_path / "flight_pack.json"
    tmp = pack_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(pack_file)
    # Extract and cache the first valid GPS fix in session.json.
    if s.gps_home is None:
        for fr in data.get("frames", []):
            if fr.get("gps_ok") and fr.get("lat") and fr.get("lon"):
                s.gps_home = {"lat": fr["lat"], "lon": fr["lon"]}
                save_session(s)
                break
    return JSONResponse({"ok": True, "frames": len(data.get("frames", []))})


@_sessions.get("/{lid}/track")
def session_get_track(lid: str, request: Request) -> JSONResponse:
    """Return a downsampled GPS track (max 500 pts) from flight_pack.json or CSV fallback."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)

    points: list = []
    pack_file = s.dir_path / "flight_pack.json"
    if pack_file.exists():
        try:
            frames = json.loads(pack_file.read_text(encoding="utf-8")).get("frames", [])
            gps = [
                [fr["lat"], fr["lon"]]
                for fr in frames
                if fr.get("gps_ok") and fr.get("lat") and fr.get("lon")
            ]
            if gps:
                step = max(1, len(gps) // 500)
                points = gps[::step]
        except (OSError, ValueError):
            pass

    if not points and s.log_file:
        csv_path = s.dir_path / s.log_file
        if csv_path.exists():
            try:
                points = extract_gps_track(csv_path)
            except (OSError, ValueError):
                pass

    if not points:
        return JSONResponse({"points": [], "home": None})

    home = points[0]
    if s.gps_home is None:
        s.gps_home = {"lat": home[0], "lon": home[1]}
        save_session(s)
    return JSONResponse({"points": points, "home": {"lat": home[0], "lon": home[1]}})


@_sessions.get("/{lid}/sync")
def session_get_sync(lid: str, request: Request) -> JSONResponse:
    """Return the video↔log sync offset (or empty dict if not set)."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    sync_file = s.dir_path / "sync.json"
    if not sync_file.exists():
        return JSONResponse({})
    try:
        return JSONResponse(json.loads(sync_file.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return JSONResponse({})


class _SyncBody(BaseModel):
    video_offset_ms: float


@_sessions.put("/{lid}/sync")
def session_put_sync(lid: str, body: _SyncBody, request: Request) -> JSONResponse:
    """Persist the video↔log sync offset to sync.json."""
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    data = {"video_offset_ms": body.video_offset_ms}
    sync_file = s.dir_path / "sync.json"
    tmp = sync_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(sync_file)
    return JSONResponse(data)


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


class _HudParams(BaseModel):
    fps: int = 25
    width: int = 1920
    height: int = 1080
    cells: int = 6
    min_gps_sats: int = 0
    t_start_s: float = 0.0
    t_end_s: float | None = None
    output_path: str | None = None


@_sessions.post("/{lid}/hud")
async def session_generate_hud(
    lid: str, body: _HudParams, request: Request
) -> StreamingResponse:
    """Generate a transparent PNG HUD sequence via SSE progress stream.

    Requires flight_pack.json to exist (produced by the viewer HTML).
    Output goes to session_dir/hud_output/.
    """
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    pack_file = s.dir_path / "flight_pack.json"
    if not pack_file.exists():
        return JSONResponse(
            {"error": "flight_pack.json missing — export from the viewer first"},
            status_code=400,
        )

    try:
        from .hud.generator import generate_hud
    except ImportError as exc:
        return JSONResponse({"error": f"HUD module unavailable: {exc}"}, status_code=500)

    output_dir = Path(body.output_path) if body.output_path else s.dir_path / "hud_output"
    q: Queue = Queue()
    cancel_event = threading.Event()

    def _progress(current: int, total: int) -> None:
        q.put(("progress", current, total))

    def _run() -> None:
        try:
            n = generate_hud(
                pack_file, output_dir,
                fps=body.fps, width=body.width, height=body.height,
                cells=body.cells, min_gps_sats=body.min_gps_sats,
                t_start_s=body.t_start_s, t_end_s=body.t_end_s,
                progress_cb=_progress,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
                q.put(("cancelled",))
            else:
                q.put(("done", n, str(output_dir)))
        except Exception as exc:
            q.put(("error", str(exc)))

    async def _stream():
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, _run)

        yield _sse({"status": "started"})

        while True:
            await asyncio.sleep(0.05)
            if await request.is_disconnected():
                cancel_event.set()
                return
            while True:
                try:
                    msg = q.get_nowait()
                except Empty:
                    break
                kind = msg[0]
                if kind == "progress":
                    _, cur, tot = msg
                    pct = round(cur / tot * 100) if tot else 0
                    yield _sse({"status": "progress", "frame": cur, "total": tot, "pct": pct})
                elif kind == "done":
                    yield _sse({"status": "done", "frames": msg[1], "output_dir": msg[2]})
                    return
                elif kind == "cancelled":
                    yield _sse({"status": "cancelled"})
                    return
                elif kind == "error":
                    yield _sse({"status": "error", "message": msg[1]})
                    return
            if fut.done():
                # Drain any remaining messages
                while not q.empty():
                    pass
                break

    return StreamingResponse(_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@_sessions.post("/{lid}/video")
async def session_attach_video(
    lid: str, file: UploadFile, request: Request
) -> JSONResponse:
    """Attach a video file to an existing session."""
    cfg = request.app.state.cfg
    s = get_session(cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    dest = s.dir_path / (file.filename or "video.mp4")
    dest.write_bytes(await file.read())
    s.video_file = dest.name
    save_session(s)
    return JSONResponse(s.to_dict())


# ── app factory ───────────────────────────────────────────────────────────


def create_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="DEDAL Studio", version="0.2.0")
    app.state.cfg = cfg

    @app.get("/api/health")
    def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "version": app.version,
            "flights_root": str(cfg.flights_root),
        })

    _no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    @app.get("/viewer.html")
    def viewer() -> Response:
        f = WEB_DIR / "viewer.html"
        if not f.exists():
            return JSONResponse({"error": "viewer.html not found"}, status_code=500)
        return FileResponse(f, headers=_no_cache)

    @app.get("/")
    def root() -> Response:
        index = WEB_DIR / "index.html"
        if not index.exists():
            return JSONResponse(
                {"error": f"web/index.html not found at {index}"},
                status_code=500,
            )
        return FileResponse(index, headers=_no_cache)

    app.include_router(_sessions)

    # ── Panel templates persistence ──────────────────────────────────────────
    def _templates_path() -> Path:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) / "dedal-studio" if xdg else Path.home() / ".config" / "dedal-studio"
        base.mkdir(parents=True, exist_ok=True)
        return base / "panel_templates.json"

    @app.get("/api/panel-templates")
    def get_panel_templates() -> JSONResponse:
        p = _templates_path()
        if not p.exists():
            return JSONResponse([])
        try:
            return JSONResponse(json.loads(p.read_text()))
        except Exception:
            return JSONResponse([])

    @app.put("/api/panel-templates")
    async def put_panel_templates(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            if not isinstance(data, list):
                return JSONResponse({"error": "expected array"}, status_code=400)
            p = _templates_path()
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            os.replace(tmp, p)
            return JSONResponse({"ok": True})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # ── Layout templates persistence ─────────────────────────────────────────

    def _layout_templates_path() -> Path:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) / "dedal-studio" if xdg else Path.home() / ".config" / "dedal-studio"
        base.mkdir(parents=True, exist_ok=True)
        return base / "layout_templates.json"

    @app.get("/api/layout-templates")
    def get_layout_templates() -> JSONResponse:
        p = _layout_templates_path()
        if not p.exists():
            return JSONResponse([])
        try:
            return JSONResponse(json.loads(p.read_text()))
        except Exception:
            return JSONResponse([])

    @app.put("/api/layout-templates")
    async def put_layout_templates(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            if not isinstance(data, list):
                return JSONResponse({"error": "expected array"}, status_code=400)
            p = _layout_templates_path()
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            os.replace(tmp, p)
            return JSONResponse({"ok": True})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    if WEB_DIR.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(WEB_DIR), html=False),
            name="static",
        )

    return app
