"""Shared fixtures for DEDAL Studio tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dedal.config import Config
from dedal.server import create_app


@pytest.fixture()
def flights_root(tmp_path: Path) -> Path:
    root = tmp_path / "flights"
    root.mkdir()
    return root


@pytest.fixture()
def cfg(flights_root: Path) -> Config:
    return Config(flights_root=flights_root)


@pytest.fixture()
def client(cfg: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    app = create_app(cfg)
    return TestClient(app, raise_server_exceptions=True)
