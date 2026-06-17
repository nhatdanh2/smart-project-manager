"""Sample tests to keep the CI pipeline honest."""
from __future__ import annotations


def test_health_endpoint(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_register_and_login(client) -> None:
    r = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "Alice", "password": "secret123"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == "alice@example.com"

    r2 = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    assert r2.status_code == 200
    assert "access_token" in r2.json()


def test_presence_snapshot_unauth(client) -> None:
    """The presence REST endpoint requires a token."""
    r = client.get("/api/ws/projects/abc/presence")
    assert r.status_code == 422 or r.status_code == 401  # missing token
