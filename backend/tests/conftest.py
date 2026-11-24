"""Shared pytest fixtures.

The suite runs against an isolated SQLite database with the simulator disabled.
Environment variables are set *before* importing the application so settings
are baked in consistently.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_suite.db"

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB}")
os.environ.setdefault("SEED_DEMO_DATA", "true")
os.environ.setdefault("SIMULATOR_ENABLED", "false")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

if TEST_DB.exists():
    TEST_DB.unlink()

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    init_db(seed_demo=True)
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _login(client, "admin@meridian.demo", "Demo@12345")


@pytest.fixture(scope="session")
def driver_headers(client):
    return _login(client, "rajesh@meridian.demo", "Demo@12345")


@pytest.fixture(scope="session")
def superadmin_headers(client):
    return _login(client, "superadmin@safeway.demo", "Super@12345")


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
