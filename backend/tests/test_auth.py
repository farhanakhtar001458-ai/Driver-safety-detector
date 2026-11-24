"""Authentication, registration and token lifecycle tests."""

from __future__ import annotations

import uuid

import pytest


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_root_redirects_to_docs(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@meridian.demo", "password": "Demo@12345"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["role"] == "org_admin"
    assert "vehicles:read" in body["user"]["permissions"]


def test_login_wrong_password_is_generic(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@meridian.demo", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["error"]["message"]


def test_login_unknown_user_same_response(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_org_and_usage(client, admin_headers):
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["organisation"]["slug"] == "meridian-logistics"
    assert body["subscription"]["plan"]["code"] in {"professional", "enterprise"}
    assert body["usage"]["vehicles"] >= 1


def test_refresh_token_rotation(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "fleet@meridian.demo", "password": "Demo@12345"},
    ).json()
    refresh = login["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]

    # Old refresh token must now be rejected (rotation, not reuse).
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401

    second = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert second.status_code == 200


def test_logout_revokes_refresh(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "safety@meridian.demo", "password": "Demo@12345"},
    ).json()
    refresh = login["refresh_token"]
    response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert response.status_code == 200
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401


def test_logout_revokes_session_row(client, db):
    """Logout must revoke the matching user_sessions row, not just the token hash."""
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "safety@meridian.demo", "password": "Demo@12345"},
    ).json()
    refresh = login["refresh_token"]

    from app.core.security import decode_token
    from app.models import UserSession

    jti = decode_token(refresh, expected_type="refresh")["jti"]
    session = db.query(UserSession).filter(UserSession.refresh_jti == jti).first()
    assert session is not None and session.revoked_at is None

    client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    db.expire_all()
    session = db.query(UserSession).filter(UserSession.refresh_jti == jti).first()
    assert session is not None and session.revoked_at is not None


def test_refresh_rotation_keeps_one_live_session(client, db):
    """Refreshing must not retarget other sessions' jti."""
    from app.core.security import decode_token
    from app.models import UserSession

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "safety@meridian.demo", "password": "Demo@12345"},
    ).json()
    first_jti = decode_token(login["refresh_token"], expected_type="refresh")["jti"]

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    ).json()
    second_jti = decode_token(refreshed["refresh_token"], expected_type="refresh")["jti"]

    db.expire_all()
    first = db.query(UserSession).filter(UserSession.refresh_jti == first_jti).first()
    second = db.query(UserSession).filter(UserSession.refresh_jti == second_jti).first()
    assert first is not None and first.revoked_at is not None
    assert second is not None and second.revoked_at is None


def test_register_creates_isolated_organisation(client):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"owner-{suffix}@example.com",
        "password": "StrongPass!2026",
        "full_name": "Fleet Owner",
        "organisation_name": f"Test Fleet {suffix}",
        "accept_monitoring_policy": True,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"]["access_token"]
    assert body["user"]["role"] == "org_admin"
    assert body["organisation"]["name"].startswith("Test Fleet")

    headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
    vehicles = client.get("/api/v1/vehicles", headers=headers)
    assert vehicles.status_code == 200
    # New tenant must see none of the demo organisation's vehicles.
    assert vehicles.json()["total"] == 0

    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["usage"]["plan_code"] == "professional"  # trial plan
    assert me["usage"]["trial_days_left"] is not None


def test_register_rejects_duplicate_email(client):
    payload = {
        "email": "admin@meridian.demo",
        "password": "StrongPass!2026",
        "full_name": "Duplicate User",
        "organisation_name": "Another Fleet",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_register_rejects_weak_password(client):
    payload = {
        "email": "weak@example.com",
        "password": "password",
        "full_name": "Weak Password",
        "organisation_name": "Weak Fleet",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_change_password(client):
    email = "changepass@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "OriginalPass!1",
            "full_name": "Change Pass",
            "organisation_name": "Change Pass Fleet",
        },
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "OriginalPass!1"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OriginalPass!1", "new_password": "NewStrongPass!2"},
        headers=headers,
    )
    assert response.status_code == 200
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "NewStrongPass!2"}).status_code
        == 200
    )
