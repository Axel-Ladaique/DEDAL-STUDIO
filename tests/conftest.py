"""Shared fixtures for DEDAL Studio tests."""
from __future__ import annotations

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
def client(cfg: Config) -> TestClient:
    app = create_app(cfg)
    return TestClient(app, raise_server_exceptions=True)
