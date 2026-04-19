"""User configuration.

The config is a small JSON file at ``~/.config/dedal-studio/config.json``
(or the platform equivalent). It currently holds just one field:

    flights_root : str — where sessions are stored.

If the file doesn't exist it's created with defaults. If any field is missing
from an older file, we fall back to defaults without crashing — this keeps
upgrades painless.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path


DEFAULT_FLIGHTS_ROOT = Path.home() / "DEDAL" / "flights"


def _config_dir() -> Path:
    """Platform-appropriate per-user config directory."""
    # Respect XDG on Linux/Mac (Mac users often have XDG_CONFIG_HOME set).
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "dedal-studio"
    # Standard user config location — works on macOS, Linux, Windows alike.
    return Path.home() / ".config" / "dedal-studio"


def _config_path() -> Path:
    return _config_dir() / "config.json"


@dataclass
class Config:
    flights_root: Path

    def save(self) -> None:
        """Persist to disk. Creates parent dirs as needed."""
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Serialize Path as string — JSON can't handle Path natively.
        payload = {**asdict(self), "flights_root": str(self.flights_root)}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_config() -> Config:
    """Load config from disk, or create a fresh one with defaults.

    Side effects:
      - Creates the config file if missing.
      - Creates the flights_root directory if missing.
    """
    path = _config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupted config — don't block the app, reset to defaults.
            data = {}
    else:
        data = {}

    flights_root = Path(data.get("flights_root") or DEFAULT_FLIGHTS_ROOT).expanduser()
    cfg = Config(flights_root=flights_root)

    # Ensure the flights directory exists so downstream code can assume it.
    cfg.flights_root.mkdir(parents=True, exist_ok=True)

    # Write the config back — this materialises the file on first run and also
    # heals a corrupted config on the next startup.
    cfg.save()
    return cfg
