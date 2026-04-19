"""DEDAL Studio — launcher.

Starts a local FastAPI server in a background thread and opens a PyWebView
window pointing at it. Falls back to a plain browser tab if PyWebView is not
available (e.g. during headless development).

Usage:
    python app.py                 # native window
    python app.py --no-window     # server only (open in browser manually)
    python app.py --port 7861     # custom port

Keep this file THIN. All HTTP / domain logic lives in `dedal.server`.
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from dedal.config import load_config
from dedal.server import create_app


# ── defaults ──────────────────────────────────────────────────────────────
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7860
WINDOW_TITLE = "DEDAL Studio"
WINDOW_SIZE = (1400, 900)


def _port_available(host: str, port: int) -> bool:
    """Return True if we can bind to (host, port) right now."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _pick_port(host: str, preferred: int) -> int:
    """Return `preferred` if free, else the first free port above it."""
    port = preferred
    while port < preferred + 20:
        if _port_available(host, port):
            return port
        port += 1
    raise RuntimeError(
        f"No free port in range {preferred}..{preferred + 19} on {host}"
    )


def _run_server(app, host: str, port: int) -> None:
    """Run uvicorn in the current thread. Called from a background thread."""
    # log_level="warning" keeps stdout clean; bump to "info" when debugging.
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> bool:
    """Poll the TCP port until it accepts connections, or until timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.08)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="DEDAL Studio")
    parser.add_argument(
        "--host", default=DEFAULT_HOST,
        help=f"Bind address (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Preferred port (default: {DEFAULT_PORT}, auto-increments if taken)"
    )
    parser.add_argument(
        "--no-window", action="store_true",
        help="Don't open a native window — run server only, print URL to stdout"
    )
    parser.add_argument(
        "--browser", action="store_true",
        help="Open the default browser instead of a native PyWebView window"
    )
    args = parser.parse_args()

    # 1. Load / create user config (creates ~/DEDAL/flights on first run).
    cfg = load_config()
    print(f"[DEDAL] flights root: {cfg.flights_root}")

    # 2. Find a free port.
    port = _pick_port(args.host, args.port)
    if port != args.port:
        print(f"[DEDAL] port {args.port} busy → using {port}")

    # 3. Build the FastAPI app (it holds a reference to the config).
    app = create_app(cfg)
    url = f"http://{args.host}:{port}/"

    # 4. Start server in a daemon thread so Ctrl+C cleanly tears everything down.
    t = threading.Thread(
        target=_run_server, args=(app, args.host, port), daemon=True
    )
    t.start()

    # 5. Wait for it to be reachable before opening any window.
    if not _wait_for_server(args.host, port):
        print(f"[DEDAL] ERROR: server did not start on {url}", file=sys.stderr)
        return 1
    print(f"[DEDAL] server ready at {url}")

    # 6. Open a window (or not).
    if args.no_window:
        print("[DEDAL] --no-window: server running, open the URL manually")
        print("[DEDAL] Ctrl+C to quit")
        try:
            t.join()
        except KeyboardInterrupt:
            pass
        return 0

    if args.browser:
        webbrowser.open(url)
        print("[DEDAL] browser opened — Ctrl+C here to quit the server")
        try:
            t.join()
        except KeyboardInterrupt:
            pass
        return 0

    # Try PyWebView for the native experience.
    try:
        import webview  # pywebview
    except ImportError:
        print(
            "[DEDAL] pywebview not installed — falling back to default browser.\n"
            "        Install with:  pip install pywebview"
        )
        webbrowser.open(url)
        try:
            t.join()
        except KeyboardInterrupt:
            pass
        return 0

    # webview.start() blocks until the window is closed, then we exit cleanly.
    webview.create_window(
        WINDOW_TITLE, url,
        width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
        resizable=True,
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
