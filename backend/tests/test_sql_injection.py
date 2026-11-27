"""Regression checks for SQL-like input against an isolated test database.

These tests exercise representative endpoints; they do not prove every possible
query is immune to SQL injection. Values must remain data, not SQL syntax.
"""

import pytest

from app.core.rate_limit import limiter


SQL_LIKE_VALUES = [
    "' OR 1=1 --",
    "' UNION SELECT NULL --",
    "x'; DROP TABLE users; --",
]


@pytest.mark.parametrize("path", ["/api/v1/vehicles", "/api/v1/drivers"])
@pytest.mark.parametrize("value", SQL_LIKE_VALUES)
def test_search_treats_sql_like_input_as_data(client, admin_headers, path, value):
    response = client.get(path, params={"search": value}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    # The table is still usable after the query.
    assert client.get(path, headers=admin_headers).status_code == 200


@pytest.mark.parametrize("value", SQL_LIKE_VALUES)
def test_login_does_not_accept_sql_like_email(client, value):
    limiter.reset()  # Isolate this test from login attempts in the rest of the suite.
    response = client.post("/api/v1/auth/login", json={"email": value, "password": "not-a-password"})
    assert response.status_code in (401, 422)
    assert "access_token" not in response.json()


def test_sql_like_vehicle_id_is_rejected(client, admin_headers):
    response = client.get("/api/v1/vehicles/1%20OR%201%3D1", headers=admin_headers)
    assert response.status_code == 422
