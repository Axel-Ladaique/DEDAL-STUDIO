"""FastAPI app factory.

At step 1 the server has a single job: serve the files in ``web/`` so the
PyWebView window can load them. Domain routes (sessions, HUD, video) will be
added in later steps — keep them in their own modules under this package.

The app holds a reference to the ``Config`` so routes can access the flights
root without importing the config module directly (easier to test).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .session import Session, get_session, list_sessions


# web/ is alongside the dedal/ package at the repo root.
# __file__  = .../dedal-studio/dedal/server.py
# parents[1] = .../dedal-studio
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


# ── sessions router ───────────────────────────────────────────────────────


class _SessionBody(BaseModel):
    name: str = ""


_sessions = APIRouter(prefix="/api/sessions", tags=["sessions"])


@_sessions.get("")
def sessions_list(request: Request) -> JSONResponse:
    items = list_sessions(request.app.state.cfg.flights_root)
    return JSONResponse([s.to_dict() for s in items])


@_sessions.get("/{lid}")
def session_get(lid: str, request: Request) -> JSONResponse:
    s = get_session(request.app.state.cfg.flights_root, lid)
    if s is None:
        return JSONResponse({"error": f"session '{lid}' not found"}, status_code=404)
    return JSONResponse(s.to_dict())


@_sessions.post("", status_code=201)
def session_create(body: _SessionBody, request: Request) -> JSONResponse:
    s = Session.create(request.app.state.cfg.flights_root, name=body.name)
    return JSONResponse(s.to_dict(), status_code=201)


# ── app factory ───────────────────────────────────────────────────────────


def create_app(cfg: Config) -> FastAPI:
    """Build the FastAPI application bound to the given config."""
    app = FastAPI(title="DEDAL Studio", version="0.1.0")

    # Stash config on app.state so routes can reach it via request.app.state.cfg
    # (standard FastAPI pattern, avoids global state).
    app.state.cfg = cfg

    # ── health ────────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health() -> JSONResponse:
        """Sanity endpoint. Returns config + a version tag."""
        return JSONResponse({
            "status": "ok",
            "version": app.version,
            "flights_root": str(cfg.flights_root),
        })

    # ── root → web/index.html ─────────────────────────────────────────────
    @app.get("/")
    def root() -> Response:
        index = WEB_DIR / "index.html"
        if not index.exists():
            return JSONResponse(
                {"error": f"web/index.html not found at {index}"},
                status_code=500,
            )
        return FileResponse(index)

    # ── sessions ──────────────────────────────────────────────────────────
    app.include_router(_sessions)

    # ── static files under /static/* ──────────────────────────────────────
    # Everything in web/ is reachable at /static/... — assets, the viewer
    # HTML (viewer.html), etc. Keep this AFTER any explicit /api/* routes.
    if WEB_DIR.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(WEB_DIR), html=False),
            name="static",
        )

    return app
