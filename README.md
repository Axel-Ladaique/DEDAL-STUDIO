# DEDAL Studio

Desktop application unifying flight log analysis, HUD generation and
video synchronisation for the DEDAL experimental VTOL.

Built on:

- **FastAPI** — local HTTP server on `127.0.0.1`.
- **PyWebView** — native window (uses WebKit on macOS, no Chromium).
- **HTML viewer** — the existing `vtol_viewer` HTML, embedded as the
  analysis UI. It stays the source of truth for calculations.

The Python side handles file I/O (sessions, videos, HUD generation).
The JS side handles interactive visualisation. They exchange data
through JSON endpoints and a per-session `flight_pack.json` cache.


## Quickstart

```bash
# (first time) install dependencies in a virtualenv
python -m venv .venv
source .venv/bin/activate           # macOS / Linux
pip install -r requirements.txt

# launch — opens a native window
python app.py

# alternative launches
python app.py --browser              # open in default browser instead
python app.py --no-window            # server only, open URL manually
python app.py --port 8000            # custom port
```

On first launch the app creates:

- `~/.config/dedal-studio/config.json` — user preferences
- `~/DEDAL/flights/` — default sessions root (configurable)


## Project layout

```
dedal-studio/
├── app.py                  # launcher (server + window)
├── requirements.txt
├── dedal/                  # Python backend
│   ├── __init__.py
│   ├── config.py           # user config load/save
│   ├── server.py           # FastAPI app factory + routes
│   └── hud/                # (step 5) HUD rendering — reuses web/ calcs
├── web/                    # served static content
│   ├── index.html          # landing page (temporary)
│   └── assets/             # images, fonts
└── flights/                # (optional) default sessions root if
                            #  ~/DEDAL/flights is not desired
```


## Roadmap

| Step | Goal                                             | Status |
| ---- | ------------------------------------------------ | ------ |
| 1    | Skeleton: server + window + static HTML          | ✅ done |
| 2    | Sessions: folder model, LID, import, home page   | next   |
| 3    | Video player + manual sync (2-cursor UI)         |        |
| 4    | Flight pack JSON (HTML → server cache)           |        |
| 5    | HUD generator refactor (reads flight pack)       |        |
| 6    | Interactive map on home page                     |        |
| 7    | Automatic video sync (metadata / audio)          |        |
