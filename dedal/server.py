"""FastAPI app factory."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .session import Session, _parse_log_meta, delete_session, get_session, list_sessions


WEB_DIR = Path(__file__).resolve().parents[1] / "web"


# ── sessions router ───────────────────────────────────────────────────────


class _SessionCreate(BaseModel):
    name: str = ""


class _SessionPatch(BaseModel):
    name: str | None = None
    notes: str | None = None


_sessions = APIRouter(prefix="/api/sessions", tags=["sessions"])


@_sessions.get("")
def sessions_list(request: Request) -> JSONResponse:
    items = list_sessions(request.app.state.cfg.flights_root)
    return JSONResponse([s.to_dict() for s in items])


@_sessions.post("", status_code=201)
def session_create(body: _SessionCreate, request: Request) -> JSONResponse:
    s = Session.create(request.app.state.cfg.flights_root, name=body.name)
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
    if body.name is not None:
        s.name = body.name
    if body.notes is not None:
        s.notes = body.notes
    s.save(cfg.flights_root)
    return JSONResponse(s.to_dict())


@_sessions.delete("/{lid}", status_code=204)
def session_delete(lid: str, request: Request) -> Response:
    found = delete_session(request.app.state.cfg.flights_root, lid)
    if not found:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    return Response(status_code=204)


@_sessions.post("/{lid}/log")
async def session_import_log(lid: str, file: UploadFile, request: Request) -> JSONResponse:
    cfg = request.app.state.cfg
    s = get_session(cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    dest = s.folder(cfg.flights_root) / (file.filename or "flight_log.csv")
    content = await file.read()
    dest.write_bytes(content)
    s.log = _parse_log_meta(dest)
    s.save(cfg.flights_root)
    return JSONResponse(s.to_dict())


# ── app factory ───────────────────────────────────────────────────────────


def create_app(cfg: Config) -> FastAPI:
    """Build the FastAPI application bound to the given config."""
    app = FastAPI(title="DEDAL Studio", version="0.1.0")
    app.state.cfg = cfg

    @app.get("/api/health")
    def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "version": app.version,
            "flights_root": str(cfg.flights_root),
        })

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
