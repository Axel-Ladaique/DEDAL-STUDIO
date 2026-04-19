"""FastAPI app factory."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from queue import Empty, Queue

from fastapi import APIRouter, FastAPI, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .sessions import (
    create_empty_session,
    delete_session,
    get_session,
    import_log,
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


_sessions = APIRouter(prefix="/api/sessions", tags=["sessions"])


@_sessions.get("")
def sessions_list(request: Request) -> JSONResponse:
    items = scan_sessions(request.app.state.cfg.flights_root)
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
    return JSONResponse({"ok": True, "frames": len(data.get("frames", []))})


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


class _HudParams(BaseModel):
    fps: int = 25
    width: int = 1920
    height: int = 1080
    cells: int = 6
    min_gps_sats: int = 0


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

    output_dir = s.dir_path / "hud_output"
    q: Queue = Queue()

    def _progress(current: int, total: int) -> None:
        q.put(("progress", current, total))

    def _run() -> None:
        try:
            n = generate_hud(
                pack_file, output_dir,
                fps=body.fps, width=body.width, height=body.height,
                cells=body.cells, min_gps_sats=body.min_gps_sats,
                progress_cb=_progress,
            )
            q.put(("done", n))
        except Exception as exc:
            q.put(("error", str(exc)))

    async def _stream():
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, _run)

        # Emit started event once generator is kicked off
        yield _sse({"status": "started"})

        while True:
            await asyncio.sleep(0.05)
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
                    yield _sse({"status": "done", "frames": msg[1], "output_dir": "hud_output/"})
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

    @app.get("/viewer.html")
    def viewer() -> Response:
        f = WEB_DIR / "viewer.html"
        if not f.exists():
            return JSONResponse({"error": "viewer.html not found"}, status_code=500)
        return FileResponse(f)

    @app.get("/")
    def root() -> Response:
        index = WEB_DIR / "index.html"
        if not index.exists():
            return JSONResponse(
                {"error": f"web/index.html not found at {index}"},
                status_code=500,
            )
        return FileResponse(index)

    app.include_router(_sessions)

    if WEB_DIR.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(WEB_DIR), html=False),
            name="static",
        )

    return app
